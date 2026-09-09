"""test_workitem_lint.py – Tests for `workitems.py lint` (CCP-1171): resolves a work
item's OWN TEXT against its typed links (ADR-0008).

Every test here runs against a fixture, never against a live tracker: the real
`local` backend rooted at a fresh temp directory (so the real frontmatter read path
is exercised, not a stand-in for it), plus `FakeYouTrackTransport` for the remote
shape. No network, no token, no `.claude/settings.json` of this repo.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "workitems.py"
sys.path.insert(0, str(SCRIPT_PATH.parent / "lib"))

from workitems import WorkItemError, frontmatter  # noqa: E402
from workitems import lint as lint_module  # noqa: E402
from workitems import local, youtrack  # noqa: E402

from .fake_youtrack_transport import FakeYouTrackTransport


class _UnreachableBackend:
    """Stands in for any backend that cannot be reached: a remote one with no
    credentials, a refused connection, a DNS failure. All of them surface as a
    WorkItemError out of `list()` (see youtrack.py's _HttpTransport)."""

    def list(self):
        raise WorkItemError("YouTrack request failed for GET /api/issues: connection refused")


class LocalFixtureTestCase(unittest.TestCase):
    """A real `local` backend on a throwaway directory. Ids are captured from
    `create()` (never assumed to be WI-0001), matching contract.py's discipline."""

    def setUp(self):
        self.workitems_dir = tempfile.mkdtemp(prefix="ccpr-lint-")
        self.addCleanup(shutil.rmtree, self.workitems_dir, ignore_errors=True)
        self.backend = local.create({"workitems_dir": self.workitems_dir})
        # Built here rather than at the point of use so it is what it claims to be:
        # a fixture this test constructed, not a value reached out of the module
        # scope (which is also what scripts/tests/pin_registry.py's taint analysis
        # distinguishes -- a literal compared against a module-scope-derived value
        # is a pin under ADR-0012, and this assertion is not one).
        self.unreachable_backend = _UnreachableBackend()

    def kinds_of(self, report, kind):
        return [f for f in report["findings"] if f["kind"] == kind]

    def plant_raw_link(self, item_id, entry):
        """Write a raw `type:target` entry into an item's `links:` frontmatter,
        bypassing `add_link`'s existence validation -- the ONLY way to construct an
        edge with an unresolvable target, since both backends refuse to create one
        (which is also why this arm has never been exercised against real data).
        Asserts the plant landed before any measurement is taken."""
        path = Path(self.workitems_dir) / f"{item_id}.md"
        data, body = frontmatter.parse(path.read_text(encoding="utf-8"))
        data["links"] = list(data.get("links") or []) + [entry]
        path.write_text(frontmatter.render(data, body), encoding="utf-8")

        link_type, _, target = entry.partition(":")
        self.assertIn(
            {"type": link_type, "target": target}, self.backend.get(item_id)["links"],
            "fixture plant did not land -- the measurement below would be vacuous",
        )


class NamedWithoutLinkTest(LocalFixtureTestCase):
    def test_an_id_named_in_the_description_with_no_typed_link_is_reported(self):
        target = self.backend.create(title="The pinned entry")["id"]
        source = self.backend.create(
            title="Follow-up", description=f"Two of {target}'s pin entries are stale.",
        )["id"]

        report = lint_module.lint(self.backend)

        self.assertEqual(
            [(f["item"], f["target"]) for f in self.kinds_of(report, "named-without-link")],
            [(source, target)],
        )

    def test_an_id_named_in_the_description_with_a_typed_link_is_silent(self):
        """The counter-proof for the assertion above: same fixture, one edge added.
        A lint that reported unconditionally would fail here."""
        target = self.backend.create(title="The pinned entry")["id"]
        source = self.backend.create(
            title="Follow-up", description=f"Two of {target}'s pin entries are stale.",
        )["id"]
        self.backend.add_link(source, "relates-to", target)

        report = lint_module.lint(self.backend)

        self.assertEqual(self.kinds_of(report, "named-without-link"), [])


class DanglingLinkTest(LocalFixtureTestCase):
    def test_a_link_whose_target_does_not_exist_is_reported(self):
        source = self.backend.create(title="Follow-up")["id"]
        self.plant_raw_link(source, "relates-to:WI-9999")

        report = lint_module.lint(self.backend)

        self.assertEqual(
            [(f["item"], f["target"]) for f in self.kinds_of(report, "dangling-link")],
            [(source, "WI-9999")],
        )

    def test_a_link_whose_target_exists_is_silent(self):
        """Counter-proof: the same edge shape, target present."""
        target = self.backend.create(title="The pinned entry")["id"]
        source = self.backend.create(title="Follow-up")["id"]
        self.backend.add_link(source, "relates-to", target)

        report = lint_module.lint(self.backend)

        self.assertEqual(self.kinds_of(report, "dangling-link"), [])


class LinkOutsideProjectTest(LocalFixtureTestCase):
    """Not a nice-to-have: without this split, a legitimate cross-project edge
    (`CCP-1 -> OTHER-42`) would be reported as a dangling link, because a backend
    only ever lists its OWN project's items. The two verdicts must not be one."""

    def test_a_link_into_another_id_namespace_is_reported_as_its_own_kind(self):
        source = self.backend.create(title="Follow-up")["id"]
        self.plant_raw_link(source, "relates-to:OTHER-42")

        report = lint_module.lint(self.backend)

        self.assertEqual(
            [(f["item"], f["target"]) for f in self.kinds_of(report, "link-outside-project")],
            [(source, "OTHER-42")],
        )
        self.assertEqual(self.kinds_of(report, "dangling-link"), [])

    def test_a_missing_target_in_the_projects_own_namespace_stays_a_dangling_link(self):
        """Counter-proof for the classifier: same missing-target shape, own prefix."""
        source = self.backend.create(title="Follow-up")["id"]
        self.plant_raw_link(source, "relates-to:WI-9999")

        report = lint_module.lint(self.backend)

        self.assertEqual(self.kinds_of(report, "link-outside-project"), [])
        self.assertEqual(len(self.kinds_of(report, "dangling-link")), 1)


class _ItemsBackend:
    """Hands `lint()` exactly the item dicts a test constructs -- the only way to
    present a shape neither shipped backend can produce (both filter a link entry
    down to a `{type, target}` pair before lint ever sees it)."""

    def __init__(self, items):
        self.items = items

    def list(self):
        return [dict(item) for item in self.items]


class MalformedLinkEntryTest(unittest.TestCase):
    def setUp(self):
        self.typeless_link_backend = _ItemsBackend([
            {"id": "X-1", "title": "t", "description": "", "links": [{"target": "X-9"}]},
        ])

    def test_a_link_entry_with_no_type_does_not_render_the_word_none(self):
        """A finding's `detail` is read by a human. `link.get("type")` on an entry
        with no type interpolates the literal `None`, which reads as if the link's
        type were the string "None" rather than absent."""
        detail = lint_module.lint(self.typeless_link_backend)["findings"][0]["detail"]

        self.assertNotIn("None", detail)
        self.assertIn("X-9", detail)


class VerdictTest(LocalFixtureTestCase):
    def test_an_unreachable_backend_is_a_refusal_never_a_green_zero_findings(self):
        report = lint_module.lint(self.unreachable_backend)

        self.assertEqual(report["verdict"], "could-not-run")
        self.assertNotEqual(report["verdict"], "pass")
        self.assertIn("connection refused", report["reason"])
        # The trap this arm exists for: an empty findings list that READS like a pass.
        self.assertEqual(report["findings"], [])
        self.assertIsNone(report["items_scanned"])

    def test_a_reachable_backend_with_nothing_to_report_is_a_pass(self):
        """Counter-proof: an empty findings list from a backend that WAS read is the
        one case that legitimately passes."""
        self.backend.create(title="Standalone")

        report = lint_module.lint(self.backend)

        self.assertEqual(report["verdict"], "pass")
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["items_scanned"], 1)

    def test_a_reachable_backend_with_a_finding_is_neither_pass_nor_could_not_run(self):
        target = self.backend.create(title="The pinned entry")["id"]
        self.backend.create(title="Follow-up", description=f"See {target}.")

        report = lint_module.lint(self.backend)

        self.assertEqual(report["verdict"], "findings")


class ScopeStatementTest(LocalFixtureTestCase):
    """A comparison whose extent is not stated is not a result: the report must name
    what it read and what its id pattern does NOT reach (CCP-1171 acceptance 4)."""

    def test_the_report_names_the_fields_it_read(self):
        self.backend.create(title="Standalone")

        scope = lint_module.lint(self.backend)["scope"]

        self.assertEqual(scope["fields_scanned"], ["title", "description"])
        self.assertEqual(scope["id_pattern"], lint_module.ID_REFERENCE_PATTERN.pattern)

    def test_the_report_names_the_reference_classes_it_does_not_reach(self):
        self.backend.create(title="Standalone")

        not_reached = " ".join(lint_module.lint(self.backend)["scope"]["not_reached"])

        # The three classes CCP-1171 acceptance 4 names, by keyword rather than by
        # verbatim sentence -- a test quoting the prose word for word would only
        # prove the prose is a copy of itself.
        self.assertIn("comment", not_reached)
        self.assertIn("workitems-idmap.yml", not_reached)
        self.assertIn("without", not_reached)

    def test_a_reference_the_backend_does_not_list_is_counted_by_namespace(self):
        """Counted PER PREFIX, not as a flat sample: the excluded set is dominated
        by whole namespaces (legacy WI-NNNN ids, ADR references), and an
        alphabetical sample of a few hundred tokens names the first namespace and
        hides the rest -- which is the opposite of stating a scope."""
        self.backend.create(
            title="Follow-up",
            description="Rationale in ADR-0008 and ADR-0002, superseding WI-9999.",
        )

        unresolved = lint_module.lint(self.backend)["scope"]["unresolved_references"]

        self.assertEqual(unresolved["count"], 3)
        self.assertEqual(unresolved["by_namespace"], {"ADR": 2, "WI": 1})

    def test_a_reference_the_backend_does_list_is_not_counted_as_unresolved(self):
        """Counter-proof: a resolvable id is a comparison, not an exclusion."""
        target = self.backend.create(title="The pinned entry")["id"]
        source = self.backend.create(title="Follow-up", description=f"See {target}.")["id"]
        self.backend.add_link(source, "relates-to", target)

        unresolved = lint_module.lint(self.backend)["scope"]["unresolved_references"]

        self.assertEqual(unresolved["count"], 0)
        self.assertEqual(unresolved["by_namespace"], {})


class RefusalWordingTest(LocalFixtureTestCase):
    def test_the_refusal_uses_the_house_could_not_run_wording(self):
        """Same three-part wording install.sh's verify_cannot_run() established, so a
        reader (and check-all.sh's own matcher) sees the familiar shape."""
        message = lint_module.lint(self.unreachable_backend)["message"]

        self.assertIn("COULD NOT RUN", message)
        self.assertIn("Nothing was compared", message)
        self.assertIn("DID NOT RUN", message)
        self.assertIn("connection refused", message)


class UndirectedGraphTest(LocalFixtureTestCase):
    """`local` writes an edge on ONE side only: `add_link(B, relates-to, A)` touches
    B's file and nothing on A's. Reading the graph directionally would therefore
    report A as unlinked while the relation demonstrably exists -- a verdict that
    depends on which side happened to run `add-link`."""

    def test_an_edge_recorded_on_the_other_side_still_counts_as_linked(self):
        target = self.backend.create(title="The pinned entry")["id"]
        source = self.backend.create(title="Follow-up", description=f"See {target}.")["id"]
        self.backend.add_link(target, "relates-to", source)

        self.assertEqual(
            self.backend.get(source)["links"], [],
            "fixture precondition: the edge must NOT be on the naming item's own side",
        )
        report = lint_module.lint(self.backend)

        self.assertEqual(self.kinds_of(report, "named-without-link"), [])


class RemoteBackendShapeTest(unittest.TestCase):
    """The gap was measured against a remote tracker, so the arm is proven against a
    remote backend's own read path too -- via the in-memory fake transport, never a
    network. YouTrack derives BOTH sides of an edge from one shared link record,
    the opposite of `local`'s one-sided storage."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )

    def test_an_id_named_with_no_typed_link_is_reported(self):
        target = self.backend.create(title="The pinned entry")["id"]
        source = self.backend.create(
            title="Follow-up", description=f"Two of {target}'s pin entries are stale.",
        )["id"]

        report = lint_module.lint(self.backend, provider="youtrack")

        self.assertEqual(
            [(f["item"], f["target"]) for f in report["findings"]
             if f["kind"] == "named-without-link"],
            [(source, target)],
        )
        self.assertEqual(report["provider"], "youtrack")

    def test_the_same_pair_with_a_typed_link_is_silent(self):
        target = self.backend.create(title="The pinned entry")["id"]
        source = self.backend.create(
            title="Follow-up", description=f"Two of {target}'s pin entries are stale.",
        )["id"]
        self.backend.add_link(source, "relates-to", target)

        report = lint_module.lint(self.backend, provider="youtrack")

        self.assertEqual(report["verdict"], "pass")
        self.assertEqual(report["findings"], [])


UNREACHABLE_PROVIDER_SOURCE = (
    "from workitems import WorkItemError\n\n"
    "def create(config):\n"
    "    return _Backend()\n\n"
    "class _Backend:\n"
    "    def list(self, **kwargs):\n"
    "        raise WorkItemError('request failed: connection refused')\n"
)

# A provider whose backend cannot even be CONSTRUCTED -- the shape a remote backend
# takes when no token resolves (youtrack.create() raises before `list()` is ever
# reached). A separate code path from the one above, and the same refusal.
UNCONSTRUCTABLE_PROVIDER_SOURCE = (
    "from workitems import WorkItemError\n\n"
    "def create(config):\n"
    "    raise WorkItemError('no token available: set the env var named by tokenEnv')\n"
)


class LintCliTest(unittest.TestCase):
    """End-to-end through the real entry point, so provider resolution, JSON-on-
    stdout and the EXIT CODE are covered -- the exit code is the part a caller acts
    on, and it is the part a report field cannot prove."""

    def setUp(self):
        self.project_dir = Path(tempfile.mkdtemp(prefix="ccpr-lint-cli-"))
        self.addCleanup(shutil.rmtree, self.project_dir, ignore_errors=True)
        self.workitems_dir = self.project_dir / "docs" / "workitems"
        self.workitems_dir.mkdir(parents=True)
        self.write_settings({"workitems": {"provider": "local"}})
        self.backend = local.create({"workitems_dir": str(self.workitems_dir)})

    def write_settings(self, data):
        claude_dir = self.project_dir / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        (claude_dir / "settings.json").write_text(json.dumps(data), encoding="utf-8")

    def write_provider(self, provider_name, source):
        path = SCRIPT_PATH.parent / "lib" / "workitems" / f"{provider_name}.py"
        path.write_text(source, encoding="utf-8")
        self.addCleanup(path.unlink, missing_ok=True)
        return provider_name

    def run_lint(self):
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "lint", "--project", str(self.project_dir)],
            capture_output=True, text=True,
        )

    def test_a_clean_graph_exits_zero_and_names_the_provider_it_read(self):
        self.backend.create(title="Standalone")

        result = self.run_lint()

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["verdict"], "pass")
        self.assertEqual(report["provider"], "local")

    def test_a_finding_exits_one(self):
        target = self.backend.create(title="The pinned entry")["id"]
        self.backend.create(title="Follow-up", description=f"See {target}.")

        result = self.run_lint()

        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["verdict"], "findings")

    def test_a_backend_that_cannot_be_constructed_exits_three(self):
        """A remote provider with no resolvable token fails in `create(config)`,
        BEFORE `list()`. Nothing was compared there either, so it is the same
        refusal -- the guard has to cover construction, not just the read."""
        provider = self.write_provider(
            "_test_lint_unconstructable_provider", UNCONSTRUCTABLE_PROVIDER_SOURCE,
        )
        self.write_settings({"workitems": {"provider": provider}})

        result = self.run_lint()

        self.assertEqual(result.returncode, 3)
        report = json.loads(result.stdout)
        self.assertEqual(report["verdict"], "could-not-run")
        self.assertIn("no token available", report["reason"])

    def test_an_unknown_provider_is_a_refusal_not_an_exit_one(self):
        """`UnknownProviderError` is not a `WorkItemError`, so it used to escape the
        guard entirely: stderr only, NO json on stdout, and exit 1 -- the same code
        as "read the backend, found problems". A caller cannot tell a typo in
        `.claude/settings.json` from real findings, and `json.loads(stdout)` crashes.
        Nothing was compared, so it is exit 3 like every other refusal."""
        self.write_settings({"workitems": {"provider": "does-not-exist"}})

        result = self.run_lint()

        self.assertEqual(result.returncode, 3)
        report = json.loads(result.stdout)
        self.assertEqual(report["verdict"], "could-not-run")
        self.assertIn("does-not-exist", report["reason"])
        self.assertIn("COULD NOT RUN", result.stderr)

    def test_an_unreachable_backend_exits_three_and_says_so_on_stderr(self):
        provider = self.write_provider(
            "_test_lint_unreachable_provider", UNREACHABLE_PROVIDER_SOURCE,
        )
        self.write_settings({"workitems": {"provider": provider}})

        result = self.run_lint()

        self.assertEqual(result.returncode, 3)
        self.assertIn("COULD NOT RUN", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["verdict"], "could-not-run")
        self.assertEqual(report["provider"], provider)


if __name__ == "__main__":
    unittest.main()
