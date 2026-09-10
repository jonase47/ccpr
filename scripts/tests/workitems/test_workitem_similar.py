"""test_workitem_similar.py -- Tests for `workitems.py similar` (CCP-1172): a
read-only ranked TEXT search over every item's title+description, built so a
`create` cannot be filed without a cheap way to check the corpus first (ADR-0004
settled dedup for `lift`; this is the same principle for `create`/a human operator).

Every test here runs against a fixture, never against a live tracker: the real
`local` backend rooted at a fresh temp directory. No network, no token, no
`.claude/settings.json` of this repo.

The KNOWN-NEIGHBOUR case (CCP-1172 acceptance criterion 2) uses the real, frozen
text of CCP-1167/CCP-1136/CCP-1124 from `similar_fixture_texts.py` -- a search that
cannot reproduce a confirmed hit is not a search, and synthetic stand-in text would
not prove that.
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

from workitems import WorkItemError  # noqa: E402
from workitems import local  # noqa: E402
from workitems import similar as similar_module  # noqa: E402

from . import similar_fixture_texts as fixtures  # noqa: E402

# Distractor items: distinct vocabulary from the absence-only-scanner class the three
# fixture items share, so a test asserting CCP-1136/CCP-1124 rank highly is not
# trivially true of "the only other items in a 3-item corpus".
DISTRACTOR_ITEMS = [
    {
        "title": "Dark mode toggle does not persist across browser sessions",
        "description": (
            "The theme preference resets to light mode on every page reload. "
            "Store the choice in localStorage and read it back on mount."
        ),
    },
    {
        "title": "Add a retry queue for failed Stripe webhook deliveries",
        "description": (
            "A webhook delivery that times out is currently dropped. Persist "
            "failed deliveries and retry with exponential backoff."
        ),
    },
    {
        "title": "GDPR data export endpoint should stream instead of buffering",
        "description": (
            "Large accounts time out the export request because the full "
            "JSON payload is built in memory before it is sent."
        ),
    },
]


class LocalFixtureTestCase(unittest.TestCase):
    def setUp(self):
        self.workitems_dir = tempfile.mkdtemp(prefix="ccpr-similar-")
        self.addCleanup(shutil.rmtree, self.workitems_dir, ignore_errors=True)
        self.backend = local.create({"workitems_dir": self.workitems_dir})

    def plant(self, title, description):
        return self.backend.create(title=title, description=description)["id"]


class _UnreachableBackend:
    """Stands in for any backend that cannot be reached -- same shape as
    test_workitem_lint.py's own fixture of the same name (CCP-1171)."""

    def list(self):
        raise WorkItemError("YouTrack request failed for GET /api/issues: connection refused")


class ScopeStatementTest(unittest.TestCase):
    """CCP-1172 acceptance 3: `similar` matches TEXT, so it must say -- in its own
    output, not only in the item that commissioned it -- that a paraphrase of the
    same behaviour stays invisible. ADR-0004's 'deduplicate by behaviour
    described' is the goal; a text search only approximates it."""

    def setUp(self):
        self.workitems_dir = tempfile.mkdtemp(prefix="ccpr-similar-scope-")
        self.addCleanup(shutil.rmtree, self.workitems_dir, ignore_errors=True)
        self.backend = local.create({"workitems_dir": self.workitems_dir})

    def test_the_report_states_the_text_versus_behaviour_limit(self):
        self.backend.create(title="Some existing item")

        report = similar_module.similar(self.backend, "a query")

        limit_statements = " ".join(report["scope"]["not_reached"])
        self.assertIn("different words", limit_statements)
        self.assertIn("VOCABULARY", limit_statements)
        self.assertIn("MEANING", limit_statements)
        self.assertIn("ADR-0004", limit_statements)

    def test_the_report_names_the_fields_it_scored(self):
        report = similar_module.similar(self.backend, "a query")

        self.assertEqual(report["scope"]["fields_scanned"], ["title", "description"])

    def test_a_could_not_run_refusal_carries_no_scope_statement_to_hide_behind(self):
        """A refusal is not a place the text/behaviour limit could quietly stand
        in for the real one -- 'could not run' has NO scope key at all, so a
        caller cannot mistake it for a completed, merely-limited search."""
        report = similar_module.refusal("unreachable")

        self.assertNotIn("scope", report)


class VerdictTest(unittest.TestCase):
    """An unreachable backend must refuse, never report 'ran, found nothing
    similar' -- 'could not run' and 'no-results' are different observations
    (CCP-1172 acceptance 1's could-not-run half; mirrors lint's VerdictTest,
    CCP-1171)."""

    def setUp(self):
        # Fixture, not a repository measurement -- mirrors test_workitem_lint.py's
        # own LocalFixtureTestCase.setUp(), which routes the same fake through
        # self.unreachable_backend rather than constructing it inline at the
        # call site.
        self.unreachable_backend = _UnreachableBackend()

    def test_an_unreachable_backend_is_a_refusal_never_a_silent_no_results(self):
        report = similar_module.similar(self.unreachable_backend, "some query text")

        self.assertEqual(report["verdict"], "could-not-run")
        self.assertNotEqual(report["verdict"], "no-results")
        self.assertIsNone(report["items_scanned"])
        self.assertEqual(report["results"], [])
        self.assertIn("connection refused", report["reason"])
        self.assertIn("NOT the same as 'no similar items'", report["message"])


class SingleItemCorpusTest(LocalFixtureTestCase):
    """Regression pin, found during CCP-1172's own build: with EXACTLY one item in
    the corpus, plain TF-IDF's `idf = log((N+1)/(df+1))` is 0 for every term of
    that one item (df == N == 1), so its vector goes entirely to zero and it can
    never be found -- silently, for every query, however similar. This is the
    case a fresh CCPR project hits on its very first `similar` call, once a
    single item already exists. Fixed with a +1-smoothed IDF (`_tfidf_vector`);
    this test pins the fix, not just the shape of the corpus."""

    def test_a_lone_existing_item_is_still_found(self):
        target_id = self.plant(
            "Dark mode toggle does not persist across browser sessions",
            "The theme preference resets to light mode on every page reload.",
        )

        report = similar_module.similar(
            self.backend, "Dark mode toggle resets on every reload",
        )

        result_ids = [r["id"] for r in report["results"]]
        self.assertIn(
            target_id, result_ids,
            "the sole existing item must be findable, not zeroed out by its own "
            "IDF weight in a one-item corpus",
        )


class LimitTest(LocalFixtureTestCase):
    """Code-review finding (Important): the verdict used to be derived from the
    ALREADY-SLICED `results` list, so `--limit 0` against a corpus with real
    matches reported `no-results` -- "found, but truncated" read as "nothing
    found", the same confusion the three-verdict form exists to prevent, one
    level deeper. No test exercised `--limit` at all before this class -- not
    the default, not an explicit value, not 0."""

    def _plant_matching_items(self, count):
        return [
            self.plant(
                f"Dark mode toggle variant {n} does not persist across sessions",
                "The theme preference resets to light mode on every page reload.",
            )
            for n in range(count)
        ]

    def test_limit_zero_still_reports_results_when_matches_exist(self):
        self._plant_matching_items(2)

        report = similar_module.similar(
            self.backend, "Dark mode toggle resets on reload", limit=0,
        )

        self.assertEqual(
            report["verdict"], "results",
            "truncated to zero results is not the same observation as no "
            "matching vocabulary at all -- the verdict must come from the "
            "ranked list BEFORE the --limit slice",
        )
        self.assertEqual(report["results"], [])
        self.assertEqual(report["items_scanned"], 2)

    def test_an_explicit_limit_truncates_the_ranked_list(self):
        self._plant_matching_items(5)

        report = similar_module.similar(
            self.backend, "Dark mode toggle resets on reload", limit=2,
        )

        self.assertEqual(report["verdict"], "results")
        self.assertEqual(len(report["results"]), 2)
        self.assertEqual(report["items_scanned"], 5)

    def test_default_limit_returns_at_most_ten(self):
        self._plant_matching_items(12)

        report = similar_module.similar(self.backend, "Dark mode toggle resets on reload")

        self.assertEqual(report["verdict"], "results")
        self.assertEqual(len(report["results"]), 10)
        self.assertEqual(report["items_scanned"], 12)


class UnicodeTokenizationTest(LocalFixtureTestCase):
    """Code-review finding: `TOKEN_PATTERN` was ASCII-only (`[a-zA-Z']+`), so an
    accented word broke at every non-ASCII letter. CCPR ships to projects that
    do not write their items in English. Two concrete failure shapes measured
    against the pre-fix pattern: 'Größe' produced NO token at all (both
    fragments 'Gr'/'e' are <=2 chars and get filtered), and 'Überprüfung'
    produced two meaningless fragments ('berpr', 'fung') that could spuriously
    match unrelated text."""

    def test_an_accented_word_is_tokenized_whole_not_fragmented(self):
        self.assertIn("größe", similar_module._tokenize("Größe"))
        self.assertIn("überprüfung", similar_module._tokenize("Überprüfung nötig"))

    def test_a_shared_accented_term_contributes_to_the_score(self):
        # Deliberately disjoint everywhere else (including no shared German
        # function word like "der"/"des"/"ein", which this project's English-
        # only STOPWORDS list does not filter): the only word the query and the
        # item have in common is "Größe" itself, so a match here can only come
        # from that term, not from an incidental overlap elsewhere.
        self.plant("Kontrastproblem im Nachtmodus", "Größe wirkt verschoben.")

        report = similar_module.similar(self.backend, "Größe")

        self.assertEqual(
            report["verdict"], "results",
            "the accented term 'Größe', the only word query and item share, "
            "must contribute to the match",
        )


class KnownNeighbourTest(LocalFixtureTestCase):
    """CCP-1172 acceptance 2: the CCP-1167 text must surface CCP-1136 and
    CCP-1124, its human-confirmed true neighbours."""

    def setUp(self):
        super().setUp()
        self.ccp_1136_id = self.plant(fixtures.CCP_1136_TITLE, fixtures.CCP_1136_DESCRIPTION)
        self.ccp_1124_id = self.plant(fixtures.CCP_1124_TITLE, fixtures.CCP_1124_DESCRIPTION)
        for distractor in DISTRACTOR_ITEMS:
            self.plant(distractor["title"], distractor["description"])

    def test_a_known_neighbourhood_is_reproduced_and_ranked_above_distractors(self):
        query_text = f"{fixtures.CCP_1167_TITLE}\n\n{fixtures.CCP_1167_DESCRIPTION}"

        report = similar_module.similar(self.backend, query_text)

        result_ids = [r["id"] for r in report["results"]]
        self.assertIn(
            self.ccp_1136_id, result_ids,
            f"expected the CCP-1136 stand-in ({self.ccp_1136_id}) among the "
            f"results, got {result_ids}",
        )
        self.assertIn(
            self.ccp_1124_id, result_ids,
            f"expected the CCP-1124 stand-in ({self.ccp_1124_id}) among the "
            f"results, got {result_ids}",
        )

        # Not just present -- ranked ABOVE every distractor, since those share
        # none of the absence-only-scanner vocabulary with the query.
        distractor_ids = {r["id"] for r in report["results"]} - {
            self.ccp_1136_id, self.ccp_1124_id,
        }
        rank_of = {r["id"]: i for i, r in enumerate(report["results"])}
        for distractor_id in distractor_ids:
            self.assertLess(
                rank_of[self.ccp_1136_id], rank_of[distractor_id],
                "CCP-1136 stand-in must outrank an unrelated distractor",
            )
            self.assertLess(
                rank_of[self.ccp_1124_id], rank_of[distractor_id],
                "CCP-1124 stand-in must outrank an unrelated distractor",
            )


UNREACHABLE_PROVIDER_SOURCE = (
    "from workitems import WorkItemError\n\n"
    "def create(config):\n"
    "    return _Backend()\n\n"
    "class _Backend:\n"
    "    def list(self, **kwargs):\n"
    "        raise WorkItemError('request failed: connection refused')\n"
)

# A provider whose backend cannot even be CONSTRUCTED -- the shape a remote backend
# takes when no token resolves. Same refusal as UNREACHABLE_PROVIDER_SOURCE, a
# different code path (mirrors test_workitem_lint.py's identically-named constant).
UNCONSTRUCTABLE_PROVIDER_SOURCE = (
    "from workitems import WorkItemError\n\n"
    "def create(config):\n"
    "    raise WorkItemError('no token available: set the env var named by tokenEnv')\n"
)


class SimilarCliTest(unittest.TestCase):
    """End-to-end through the real entry point, so provider resolution, JSON-on-
    stdout and the EXIT CODE are covered -- the exit code is the part a caller
    acts on and a report field alone cannot prove (mirrors LintCliTest, CCP-1171)."""

    def setUp(self):
        self.project_dir = Path(tempfile.mkdtemp(prefix="ccpr-similar-cli-"))
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

    def run_similar(self, *extra_args):
        return subprocess.run(
            [
                sys.executable, str(SCRIPT_PATH), "similar", *extra_args,
                "--project", str(self.project_dir),
            ],
            capture_output=True, text=True,
        )

    def test_a_matching_corpus_exits_zero_and_names_the_provider_it_read(self):
        self.backend.create(title="Dark mode toggle resets on reload")

        result = self.run_similar("Dark mode toggle does not persist")

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["verdict"], "results")
        self.assertEqual(report["provider"], "local")

    def test_the_limit_flag_reaches_the_lib_function(self):
        for n in range(5):
            self.backend.create(title=f"Dark mode toggle variant {n} resets on reload")

        result = self.run_similar("Dark mode toggle does not persist", "--limit", "2")

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["verdict"], "results")
        self.assertEqual(len(report["results"]), 2)

    def test_an_empty_corpus_is_no_results_not_a_refusal(self):
        result = self.run_similar("Nothing has been filed yet")

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["verdict"], "no-results")
        self.assertEqual(report["results"], [])

    def test_an_unreachable_backend_exits_three_and_says_so_on_stderr(self):
        provider = self.write_provider(
            "_test_similar_unreachable_provider", UNREACHABLE_PROVIDER_SOURCE,
        )
        self.write_settings({"workitems": {"provider": provider}})

        result = self.run_similar("anything")

        self.assertEqual(result.returncode, 3)
        self.assertIn("COULD NOT RUN", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["verdict"], "could-not-run")
        self.assertEqual(report["provider"], provider)

    def test_a_backend_that_cannot_be_constructed_exits_three(self):
        """A remote provider with no resolvable token fails in `create(config)`,
        BEFORE `list()` -- nothing was compared there either (mirrors lint's
        identically-named test, CCP-1171)."""
        provider = self.write_provider(
            "_test_similar_unconstructable_provider", UNCONSTRUCTABLE_PROVIDER_SOURCE,
        )
        self.write_settings({"workitems": {"provider": provider}})

        result = self.run_similar("anything")

        self.assertEqual(result.returncode, 3)
        report = json.loads(result.stdout)
        self.assertEqual(report["verdict"], "could-not-run")
        self.assertIn("no token available", report["reason"])

    def test_an_unknown_provider_is_a_refusal_not_an_exit_zero(self):
        self.write_settings({"workitems": {"provider": "does-not-exist"}})

        result = self.run_similar("anything")

        self.assertEqual(result.returncode, 3)
        report = json.loads(result.stdout)
        self.assertEqual(report["verdict"], "could-not-run")
        self.assertIn("does-not-exist", report["reason"])
        self.assertIn("COULD NOT RUN", result.stderr)


if __name__ == "__main__":
    unittest.main()
