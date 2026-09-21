"""test_workitems_template.py – CCP-1146: templates/workitems.example.json is the only
copyable source for `.claude/settings.json`'s `workitems` block (that file is gitignored,
so nothing else ships a working starting point -- see templates/memory-sync.example.json
for the same pattern applied to a different gitignored settings file).

The risk this guards against isn't "the template is missing a key" alone -- it's the
template silently DRIFTING from what the loader actually reads: a stale key that used to
matter, a typo nobody notices because the youtrack backend just treats it as absent, or a
newly-added config field the template never picked up. Either direction is silent: an
extra key does nothing (no error, just dead documentation); a missing key looks configured
but isn't. So this test derives the accepted keys from the CODE that reads them --
`workitems.youtrack.create(config)`'s own `config.get(...)` calls, read via
`inspect.getsource` rather than copied by hand -- instead of a second hardcoded list that
could drift from the loader exactly the same way the template could.
"""

import inspect
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from workitems import youtrack  # noqa: E402

TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "templates" / "workitems.example.json"

# create(config)'s own stale_after_seconds=config.get("stale_after_seconds") is NOT a
# `.claude/settings.json` key: resolve_provider_config() synthesizes it from
# `workitems.claiming.staleAfter` (a top-level sibling of `youtrack`, not one of its own
# keys) before create() ever sees it -- see resolve_provider_config's own docstring. The
# real settings.json key is asserted separately, under `claiming`, in the second test
# below.
_SYNTHESIZED_NOT_A_SETTINGS_KEY = "stale_after_seconds"


def _config_keys_read_by(func):
    """The set of `config.get("<key>")` string literals inside `func`'s own source --
    read directly off the function, not maintained as a parallel hand-copied list, so it
    cannot go stale independently of the code it describes."""
    source = inspect.getsource(func)
    return set(re.findall(r'config\.get\(\s*"([^"]+)"', source))


class WorkitemsTemplateYouTrackKeysTest(unittest.TestCase):
    def test_template_youtrack_block_has_exactly_the_keys_create_reads(self):
        template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))

        template_keys = set(template["workitems"]["youtrack"].keys())
        accepted_keys = _config_keys_read_by(youtrack.create) - {_SYNTHESIZED_NOT_A_SETTINGS_KEY}

        self.assertEqual(template_keys, accepted_keys)


class WorkitemsTemplateShapeTest(unittest.TestCase):
    """The two levels _config_keys_read_by can't reach without over-fitting the regex to
    unrelated code (resolve_provider/resolve_provider_config read these by a mix of
    `.get("provider", ...)`/`.get("workitems", ...)`/`.get("claiming")` -- not the uniform
    `config.get("KEY")` shape _config_keys_read_by targets), so they're asserted directly
    against handbook/WORKITEMS.md §3's own documented shape instead."""

    def setUp(self):
        self.template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))

    def test_workitems_block_has_exactly_provider_youtrack_and_claiming(self):
        self.assertEqual(set(self.template["workitems"].keys()), {"provider", "youtrack", "claiming"})

    def test_provider_is_set_to_youtrack(self):
        self.assertEqual(self.template["workitems"]["provider"], "youtrack")

    def test_claiming_block_has_exactly_staleafter_and_heartbeatinterval(self):
        # heartbeatInterval is deliberately NOT consumed by any loader code (see
        # resolve_provider_config's own comment: "advisory for whatever schedules a
        # runner's heartbeat calls") -- still a valid, documented key, not a typo.
        self.assertEqual(
            set(self.template["workitems"]["claiming"].keys()),
            {"staleAfter", "heartbeatInterval"},
        )


class WorkitemsTemplateNoRealValuesTest(unittest.TestCase):
    """PO decision (CCP-1146, 11.09.2026): instance address, project short name and token
    path must not appear -- placeholders only, so the template never becomes a second
    place carrying real deployment values."""

    def test_baseurl_is_a_placeholder_not_a_real_url(self):
        template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))

        base_url = template["workitems"]["youtrack"]["baseUrl"]

        self.assertNotRegex(base_url, r"^https?://\d")  # no bare IP literal
        self.assertIn("<", base_url)

    def test_project_is_a_placeholder_not_a_real_short_name(self):
        template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))

        project = template["workitems"]["youtrack"]["project"]

        self.assertIn("<", project)

    def test_tokenfile_is_a_placeholder_not_a_real_path(self):
        template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))

        token_file = template["workitems"]["youtrack"]["tokenFile"]

        self.assertIn("<", token_file)


if __name__ == "__main__":
    unittest.main()
