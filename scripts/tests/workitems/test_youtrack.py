"""test_youtrack.py – Wires the `youtrack` backend into the shared contract suite
(ADR-0002/ADR-0003), plus youtrack-specific tests for behaviour the backend-neutral
contract doesn't cover: stateMap remapping, the append-result comment-prefix
disambiguation, config validation in create(config), and the real urllib-based
transport's error translation.

No network, no live YouTrack instance anywhere in this file — see
fake_youtrack_transport.py for the in-memory stand-in used by the contract fixture,
and HttpTransportTest below for the urllib-level tests (mocking urllib.request.urlopen
directly, per the reviewer's second suggested option).
"""

import io
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from workitems import WorkItemError, youtrack  # noqa: E402

from .contract import WorkItemsContractTestCase
from .fake_youtrack_transport import FakeYouTrackTransport


class YouTrackBackendContractTest(WorkItemsContractTestCase, unittest.TestCase):
    """Proves the youtrack backend satisfies the SAME contract as local — the whole
    point of ADR-0002 §9 (`local` is the reference implementation and the fixture)."""

    def create_backend(self, workitems_dir):
        # workitems_dir is unused: YouTrack has no filesystem concept. Each test gets
        # its own fresh in-memory "project" instead.
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        return youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )


class YouTrackStateMapTest(unittest.TestCase):
    """stateMap lets a project whose State bundle doesn't name its values to match
    CCPR's vocabulary supply a name->name mapping (ADR-0003)."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST", token="fake-token",
            state_map={"Backlog": "Open", "In Progress": "Doing", "Done": "Closed"},
            transport=self.transport,
        )

    def test_set_status_sends_the_mapped_project_state_name(self):
        item = self.backend.create(title="New feature")

        self.backend.set_status(item["id"], "In Progress")

        self.assertIn("State Doing", self.transport.commands_received)

    def test_get_reports_back_the_ccpr_vocabulary_name_not_the_project_name(self):
        item = self.backend.create(title="New feature")

        self.backend.set_status(item["id"], "In Progress")
        fetched = self.backend.get(item["id"])

        self.assertEqual(fetched["status"], "In Progress")

    def test_create_maps_backlog_through_the_state_map_too(self):
        item = self.backend.create(title="New feature")

        self.assertEqual(item["status"], "Backlog")
        self.assertIn("State Open", self.transport.commands_received)


class YouTrackPaginationTest(unittest.TestCase):
    """A real YouTrack instance can silently cap GET /api/issues to a default page
    size unless $top=-1 is passed explicitly. FakeYouTrackTransport's page_size_cap
    simulates that default so list() is proven to send $top=-1, not rely on it."""

    def test_list_returns_everything_even_when_the_fake_caps_page_size(self):
        transport = FakeYouTrackTransport(project_short_name="TEST", page_size_cap=2)
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
        )
        for i in range(5):
            backend.create(title=f"Item {i}")

        items = backend.list()

        self.assertEqual(len(items), 5)


class YouTrackInvalidCommandTest(unittest.TestCase):
    """Verified against a real instance: an unresolvable Command API query (an
    unknown State/user name) returns HTTP 400 and leaves the issue UNCHANGED
    (atomic reject, no partial apply) — already surfaced as a WorkItemError by
    _HttpTransport's existing HTTPError handling. The gap was the FAKE transport,
    which accepted any string as a valid state/assignee; this makes it faithful."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(
            project_short_name="TEST",
            known_states={"Backlog", "In Progress", "Done"},
            known_users={"alice"},
        )
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )

    def test_set_status_with_unresolvable_state_raises_and_leaves_issue_unchanged(self):
        item = self.backend.create(title="New feature")  # create()'s own "Backlog" is known

        with self.assertRaises(WorkItemError):
            # Valid CCPR vocabulary, but not a state name this project's bundle has.
            self.backend.set_status(item["id"], "Waiting for Approval")

        fetched = self.backend.get(item["id"])
        self.assertEqual(fetched["status"], "Backlog")

    def test_claim_with_unresolvable_assignee_raises(self):
        item = self.backend.create(title="New feature")

        with self.assertRaises(WorkItemError):
            self.backend.claim(item["id"], owner="mallory")


class YouTrackAppendResultTest(unittest.TestCase):
    """append-result adds a comment; get/list must recognise ONLY comments carrying
    the result marker as result-link entries — an ordinary human comment on the
    issue must not be mistaken for one (ADR-0003 doesn't specify a disambiguation
    mechanism; this is this implementation's resolution of that gap)."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )

    def test_ordinary_comment_is_not_treated_as_a_result_link(self):
        item = self.backend.create(title="New feature")
        # Simulate a human leaving an unrelated comment directly via the transport.
        self.transport._require_issue(item["id"])["comments"].append(
            {"text": "Looks good, one nit though."}
        )

        self.backend.append_result(item["id"], "https://example.org/pr/1")
        fetched = self.backend.get(item["id"])

        self.assertEqual(fetched["result-link"], ["https://example.org/pr/1"])

    def test_human_comment_that_happens_to_start_with_the_word_result_is_not_picked_up(self):
        # A human writing prose ("Result: I don't think this fixed it...") must not be
        # mistaken for a result reference — this is exactly why an English prefix isn't
        # a safe marker; only a marker a human would never type naturally qualifies.
        item = self.backend.create(title="New feature")
        self.transport._require_issue(item["id"])["comments"].append(
            {"text": "Result: I don't think this fixed it, reverting."}
        )

        fetched = self.backend.get(item["id"])

        self.assertEqual(fetched["result-link"], [])


class YouTrackCreateFactoryTest(unittest.TestCase):
    """create(config) — the factory the CLI dispatcher calls — validates its own
    config and never reads the token from settings.json (ADR-0002 §3)."""

    def test_missing_required_config_keys_raises(self):
        with self.assertRaises(WorkItemError):
            youtrack.create({})

    def test_missing_token_env_var_raises(self):
        config = {"baseUrl": "https://faketrack.example.org", "project": "TEST",
                   "tokenEnv": "CCPR_TEST_YOUTRACK_TOKEN_DOES_NOT_EXIST"}
        os.environ.pop("CCPR_TEST_YOUTRACK_TOKEN_DOES_NOT_EXIST", None)

        with self.assertRaises(WorkItemError):
            youtrack.create(config)

    def test_happy_path_reads_token_from_environment_not_config(self):
        env_var = "CCPR_TEST_YOUTRACK_TOKEN"
        os.environ[env_var] = "secret-value"
        self.addCleanup(os.environ.pop, env_var, None)
        config = {"baseUrl": "https://faketrack.example.org", "project": "TEST", "tokenEnv": env_var}

        backend = youtrack.create(config)

        self.assertEqual(backend.token, "secret-value")
        self.assertNotIn("secret-value", repr(config))


class HttpTransportTest(unittest.TestCase):
    """Direct urllib-level tests for the real transport (mocking urllib.request.urlopen,
    per the reviewer's alternative to the fake-transport approach above) — the fake
    transport bypasses _HttpTransport entirely, so these are the only tests that
    exercise its actual header/error-handling code."""

    def test_sends_bearer_auth_header_and_returns_parsed_json(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

            def read(self):
                return b'{"ok": true}'

        def fake_urlopen(req, timeout=None):
            captured["auth_header"] = req.get_header("Authorization")
            return FakeResponse()

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            transport = youtrack._HttpTransport()
            result = transport.request("GET", "https://example.org/api/issues", "secret-token")

        self.assertEqual(captured["auth_header"], "Bearer secret-token")
        self.assertEqual(result, {"ok": True})

    def test_http_error_is_translated_into_workitemerror(self):
        def fake_urlopen(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url, 404, "Not Found", None, io.BytesIO(b'{"error":"not found"}'),
            )

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            transport = youtrack._HttpTransport()
            with self.assertRaises(WorkItemError):
                transport.request("GET", "https://example.org/api/issues/PROJ-1", "secret-token")

    def test_read_timeout_is_translated_into_workitemerror_not_a_raw_exception(self):
        # A stall during resp.read() raises a bare TimeoutError (an OSError subclass
        # NOT a urllib.error.URLError subclass) — it must not bypass the except clause
        # and surface as an unhandled traceback to the CLI user.
        class StallingResponse:
            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

            def read(self):
                raise TimeoutError("timed out")

        def fake_urlopen(req, timeout=None):
            return StallingResponse()

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            transport = youtrack._HttpTransport()
            with self.assertRaises(WorkItemError):
                transport.request("GET", "https://example.org/api/issues", "secret-token")

    def test_invalid_json_response_is_translated_into_workitemerror(self):
        class GarbageResponse:
            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

            def read(self):
                return b"not json at all"

        def fake_urlopen(req, timeout=None):
            return GarbageResponse()

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            transport = youtrack._HttpTransport()
            with self.assertRaises(WorkItemError):
                transport.request("GET", "https://example.org/api/issues", "secret-token")


if __name__ == "__main__":
    unittest.main()
