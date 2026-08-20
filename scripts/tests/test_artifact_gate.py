"""test_artifact_gate.py – End-to-end tests for scripts/artifact-gate.sh.

The gate makes the Constitution's Inviolable "No personal or tenant data in
shipped artifacts" machine-checkable. It reuses the discipline-gate patterns
that `scripts/memory-sync.sh` already ships, so the tests come in two halves
that must be read together:

* **artifact profile** – what a *shipped artifact* may not contain. Secrets,
  session hashes / home paths / real email addresses, network literals, and a
  deny-list of tenant and project names sourced from personal config. The
  memory-only checks (work-item content shapes, `type: user`, the personal
  colour-vision markers) are deliberately NOT part of this profile.
* **memory profile (characterisation)** – `memory-sync.sh gate` must keep
  behaving exactly as before the pattern definitions moved into the shared
  library. Those tests are a refactor safety net, not new behaviour.

Every run redirects HOME to an empty throwaway directory: both entry points
resolve their personal config from `$HOME/.claude/memory-sync.json`, and a
developer's real config (deny-list entries, IP allowlist) would otherwise leak
into the findings and into the exit code.

The false-positive corpus is not decorative. Each `test_fp_*` case is one of the
27 non-content findings the unmodified gate produced over this repository's
tracked files, reduced to its shape. They exist so that "the repo is clean" can
never again be achieved by weakening a pattern into uselessness.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

def leak(*parts):
    """Assemble a leak-shaped fixture from fragments that are harmless apart.

    This suite has to feed the gate the exact strings the gate exists to find.
    Spelled out, they would make the suite itself a finding on every sweep of
    this repository, and the only ways out would be to exclude scripts/tests/**
    from the scan (a real tenant name in a fixture would then ship just the same)
    or to weaken the patterns until the fixtures slip through. Assembling them at
    call time keeps the source clean by *content* rather than by exception: no
    line of this file carries a leak shape, while the bytes written to the file
    under test are byte-for-byte the shape being asserted on.

    Each split is placed so that no single fragment matches on its own -- inside
    the keyword, inside the `/Users/` prefix, inside the `://` of a connection
    string, and below the length threshold of every blob shape.
    """
    return "".join(parts)


# The leak shapes, each below its own detection threshold per fragment.
CREDENTIAL = leak('api', '_key = "', 'A1b2C3d4E5f6G7h8I9j0K1l2M3"')
HEX_DIGEST = leak("9f86d081884c7d659a2fea", "a0c55ad015a3bf4f1b2b0", "b822cd15d6c15b0f00a08")
# The exact hex-length boundary GATE_RE_SECRET_BLOB's `{32,}` floor draws: 31
# characters must stay silent, 32 must fire.
HEX_31_CHARS = leak("9f86d081884c7d6", "59a2fea0c55ad015")
HEX_32_CHARS = leak("9f86d081884c7d65", "9a2fea0c55ad015a")
JWT = leak("eyJ", "hbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.", "eyJ", "zdWIiOiIxMjM0NTY3ODkwIn0.",
           "dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk")
BASE64_BLOB = leak("VGhpc0lzQVZlcnlMb25nQmFzZTY0", "RW5jb2RlZFNlY3JldFZhbHVlSGVyZQ==")
VENDOR_TOKEN = leak("ghp", "_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8")
PRIVATE_KEY = leak("-----BEGIN RSA ", "PRIVATE KEY-----")
HOME_PATH = leak("/Us", "ers/somebody/Workspace/notes.md")
LINUX_HOME_PATH = leak("/ho", "me/alice/Workspace/notes.md")
SESSION_HASH = leak("session", "_a1b2c3d4e5")
REAL_EMAIL = leak("firstname.lastname", "@somecompany.de")
NEAR_RESERVED_EMAIL = leak("person", "@mytest.de")
# A reserved domain used as a PREFIX, not as the whole domain -- the shape the
# terminal `$` anchor on GATE_RE_EMAIL_RESERVED exists to reject. Without that
# anchor, "@example.com" would match as a substring and this real,
# attacker-controlled address would go silent.
RESERVED_PREFIX_EMAIL = leak("person@example.com.", "attacker.io")
# A bearer token that is neither hex/JWT/padded-base64 (so GATE_RE_SECRET_BLOB
# cannot see it) nor written as keyword[:=]value (so GATE_RE_SECRET_KV cannot
# see it either) -- the exact shape only GATE_RE_SECRET_BEARER catches.
BEARER_TOKEN = leak("Authorization: Bearer ", "9Kx2QmZ7vB4nR8jH1pL6wA3cF5tY0dE9r")
# The env-var assignment form of the same header: the anchor that makes
# GATE_RE_SECRET_BEARER require `[:=]` immediately before "bearer" must accept
# `=` and a quote, not just the `Authorization:` colon form above -- otherwise
# the anchor would silently narrow the check to one of its two real shapes.
BEARER_ENV_VAR = leak('AUTH_HEADER="Bearer ', '9Kx2QmZ7vB4nR8jH1pL6wA3cF5tY0dE9r"')
IPV4 = leak("198.51.", "100.7")
ALLOWLISTED_IPV4 = leak("192.0.", "2.5")
CONNECTION_STRING = leak("postgres:/", "/admin:s3cr3tpassphrase@db.example/app")
# Real credentials that happen to contain one of the characters a placeholder is
# built from. `%` is the sharp one: percent-encoding is the CORRECT way to put a
# reserved character into a URL password, so writing the credential properly must
# not be what silences the gate.
PCT_ENCODED_CONNSTRING = leak("postgresql:/", "/svc:p%40ss@dbhost/prod")
PCT_ENCODED_DOLLAR = leak("mongodb:/", "/admin:Pa%24%24w0rd9@host/db")
STAR_CONNSTRING = leak("https:/", "/deploy:pw*7Kq2mnR4@registryhost/x")
BRACE_CONNSTRING = leak("amqp:/", "/svc:a{b}c9XyZq@broker/vh")
ANGLE_CONNSTRING = leak("redis:/", "/default:p<3wine9Q@cache/0")
# A slot that is part literal credential, part variable. This is the shape that
# separates "the slot IS a placeholder" from "the slot CONTAINS one": the real
# secret is right there in the clear, next to an interpolation.
SUFFIXED_CONNSTRING = leak("https:/", "/svc:R7kQm2Xp9${env}@host/p")
PREFIXED_CONNSTRING = leak("https:/", "/svc:${env}R7kQm2Xp9@host/p")
# Credentials written the way a config file actually writes them: the key is
# quoted, so the `[:=]` no longer sits flush against the keyword. None of these
# carries a vendor prefix, a hex/JWT/padded-base64 shape or any other blob
# signature -- check 1a is the only rule that can see them, which is exactly the
# role the design comment assigns it.
JSON_TOKEN = leak('{ "to', 'ken": "ghs9wTq3xL8vNb2ZcRmKdE7fYpA4uHjX6sQwVr1t" }')
JSON_SPACED_SECRET = leak('{ "sec', 'ret" : "Xy7Qm2Rt9Lp4Vn8Kd3Fs6Bw1Zc5Hj0" }')
PY_DICT_API_KEY = leak("{'api", "_key': 'A1b2C3d4E5f6G7h8I9j0K1l2M3'}")
# The pattern-source self-exemption marker, spelled out here so the suite can
# prove it has no effect outside the file that defines the patterns.
EXEMPT_MARKER = leak("gate-", "pattern-source")
# WI-0035: the two false positives measured 19.08.2026 -- a documentation
# placeholder written in capitals behind a real "Authorization: Bearer"
# header. It opens with a plain alphanumeric, so it is NOT excluded by the
# GATE_RE_PLACEHOLDER_SLOT shapes (those all open with a non-alnum character).
PLACEHOLDER_BEARER_1 = leak("Authorization: Bearer ", "YOUR_TOKEN_HERE_REPLACE_ME")
PLACEHOLDER_BEARER_2 = leak("Authorization: Bearer ", "TODO_INSERT_YOUR_TOKEN_HERE")
# Same placeholder-word shape, reached through 1a (GATE_RE_SECRET_KV) instead
# of 1a' -- the filter is scoped to both rules, not just the bearer one.
PLACEHOLDER_KV = leak("token: ", "YOUR_TOKEN_HERE_REPLACE_ME")
# Lower-case spelling of the same word list -- pins the case-insensitive
# design decision; a case-sensitive filter would let this one through.
PLACEHOLDER_BEARER_LOWERCASE = leak("Authorization: Bearer ", "your_token_here_replace_me")
# A value that is credential-shaped (mixed-case, no dictionary word other than
# the one under test) and merely CONTAINS a listed word mid-string, not
# prefixed/suffixed by it the way the two reported cases are. Pins the PO
# decision that "contains" -- not "is" -- is what the filter checks.
PLACEHOLDER_WORD_MID_VALUE_KV = leak("token: aB3d", "EXAMPLE", "f9K2mN4pQ7rS0tU1vW")
# AWS's own documentation access key. Contains EXAMPLE, and must still fire --
# but only GATE_RE_SECRET_VENDOR (AKIA[0-9A-Z]{16}, no placeholder filter) may
# be the source: this fixture carries no keyword/`[:=]` context, so neither 1a
# nor 1a' can match it in the first place.
AWS_DOC_EXAMPLE_KEY = leak("AKIA", "IOSFODNN7EXAMPLE")


REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "scripts" / "artifact-gate.sh"
MEMORY_SYNC = REPO_ROOT / "scripts" / "memory-sync.sh"
LIB = REPO_ROOT / "scripts" / "lib" / "discipline_gate.sh"
CI_TEMPLATE = REPO_ROOT / "templates" / "ci" / "artifact-gate.ci.sh"

# A file body that must never produce a finding: ordinary prose plus the two
# structural shapes (heading, checkbox) that the memory profile flags and the
# artifact profile must not.
CLEAN_TEXT = """# Title

Some ordinary prose about a skill prompt.

## Next Steps

- [ ] an unchecked box
- [x] a checked box

TODO: this is a work-item marker and is none of the artifact gate's business.
"""


# The same idea for the memory profile, which flags the work-item shapes that
# CLEAN_TEXT carries on purpose: a body that is clean under BOTH profiles, so a
# memory-side test can assert on the configuration defect and nothing else.
MEMORY_CLEAN_TEXT = "# Rule\n\nA durable piece of knowledge.\n"


class GateTestBase(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="ccpr-artifact-gate-home-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        (self.home / ".claude").mkdir(parents=True)

        self.work = Path(tempfile.mkdtemp(prefix="ccpr-artifact-gate-"))
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)

    # --- helpers ---------------------------------------------------------
    def write(self, name, text):
        p = self.work / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def env(self, **extra):
        e = {"HOME": str(self.home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}
        e.update(extra)
        return e

    def write_config(self, **gate_keys):
        cfg = {
            "repoUrl": "https://git.invalid/org/repo.git",
            "namespace": "XX",
            "gate": gate_keys,
        }
        (self.home / ".claude" / "memory-sync.json").write_text(
            json.dumps(cfg), encoding="utf-8"
        )

    def run_gate(self, *args, **extra_env):
        return subprocess.run(
            ["bash", str(GATE), *[str(a) for a in args]],
            capture_output=True, text=True, env=self.env(**extra_env),
        )

    def run_memory_gate(self, path):
        return subprocess.run(
            ["bash", str(MEMORY_SYNC), "gate", str(path)],
            capture_output=True, text=True, env=self.env(),
        )

    @staticmethod
    def categories(result):
        """The set of category tags in a gate run's findings, e.g. {'secret'}."""
        out = set()
        for line in (result.stdout + result.stderr).splitlines():
            if "] " in line and "[" in line:
                tag = line.split("[", 1)[1].split("]", 1)[0]
                if tag in {"secret", "personal", "network", "denylist",
                           "content", "context"}:
                    out.add(tag)
        return out

    def assert_silent(self, text, name="sample.md"):
        p = self.write(name, text)
        r = self.run_gate(p)
        self.assertEqual(
            r.returncode, 0,
            f"expected no finding, got:\n{r.stdout}\n{r.stderr}",
        )
        self.assertEqual(self.categories(r), set())

    def assert_fires(self, text, category, name="sample.md"):
        p = self.write(name, text)
        r = self.run_gate(p)
        self.assertEqual(r.returncode, 1, f"expected a finding, got:\n{r.stdout}")
        self.assertIn(category, self.categories(r))


# ---------------------------------------------------------------------------
# 1. Baseline: a clean file, and the three adopted categories firing.
# ---------------------------------------------------------------------------
class AdoptedCategoriesTest(GateTestBase):
    def test_a_clean_file_reports_no_findings_and_exits_zero(self):
        self.assert_silent(CLEAN_TEXT)

    def test_a_credential_assignment_fires_as_secret(self):
        self.assert_fires(CREDENTIAL + "\n", "secret")

    def test_a_hex_digest_fires_as_secret(self):
        self.assert_fires("digest " + HEX_DIGEST + "\n", "secret")

    def test_a_31_character_hex_string_is_below_the_blob_floor(self):
        self.assert_silent("checksum " + HEX_31_CHARS + "\n")

    def test_a_32_character_hex_string_reaches_the_blob_floor(self):
        self.assert_fires("checksum " + HEX_32_CHARS + "\n", "secret")

    def test_a_jwt_fires_as_secret(self):
        self.assert_fires("auth " + JWT + "\n", "secret")

    def test_a_padded_base64_blob_fires_as_secret(self):
        self.assert_fires("blob " + BASE64_BLOB + "\n", "secret")

    def test_a_vendor_prefixed_token_fires_as_secret(self):
        self.assert_fires("key " + VENDOR_TOKEN + "\n", "secret")

    def test_a_private_key_block_fires_as_secret(self):
        self.assert_fires(PRIVATE_KEY + "\nMIIB\n", "secret")

    def test_a_real_home_path_fires_as_personal(self):
        self.assert_fires("see " + HOME_PATH + "\n", "personal")

    def test_a_linux_home_path_fires_as_personal_too(self):
        # GATE_RE_PERSONAL covers both /Users/... and /home/...; only the
        # /Users/ arm had a fixture before this test.
        self.assert_fires("see " + LINUX_HOME_PATH + "\n", "personal")

    def test_a_session_hash_fires_as_personal(self):
        self.assert_fires("resumed from " + SESSION_HASH + "\n", "personal")

    def test_a_real_email_address_fires_as_personal(self):
        self.assert_fires("contact " + REAL_EMAIL + "\n", "personal")

    def test_an_ipv4_literal_fires_as_network(self):
        self.assert_fires("the box answers on " + IPV4 + " today\n", "network")

    def test_the_memory_only_content_check_is_not_part_of_this_profile(self):
        # Skill prompts legitimately carry "Next Steps" headings and checkboxes.
        self.assert_silent("## Next Steps\n\n- [ ] do the thing\n\nTODO: later\n")

    def test_the_memory_only_type_user_check_is_not_part_of_this_profile(self):
        self.assert_silent("---\ntype: user\n---\n\nA schema example.\n")


# ---------------------------------------------------------------------------
# 2. The false-positive corpus — every shape the unmodified gate flagged over
#    this repository, with zero true positives among them.
# ---------------------------------------------------------------------------
class FalsePositiveCorpusTest(GateTestBase):
    def test_fp_a_markdown_table_separator_row_is_not_a_token_blob(self):
        self.assert_silent(
            "| a | b |\n"
            "|" + "-" * 60 + "|" + "-" * 55 + "|\n"
        )

    def test_fp_a_shell_comment_rule_is_not_a_token_blob(self):
        self.assert_silent("# --- discipline gate " + "-" * 60 + "\n", "sample.sh")

    def test_fp_a_long_snake_case_test_name_is_not_a_token_blob(self):
        self.assert_silent(
            "def test_a_directory_link_without_a_trailing_slash_resolves(self):\n"
            "    pass\n",
            "sample.py",
        )

    def test_fp_a_long_camel_case_class_name_is_not_a_token_blob(self):
        # 41 characters, no separator at all — the shape that killed every
        # length-plus-entropy heuristic and forced the switch to explicit shapes.
        self.assert_silent(
            "class LocalBackendAppendResultWithoutSectionTest(unittest.TestCase):\n"
            "    pass\n",
            "sample.py",
        )

    def test_fp_a_long_upper_snake_env_var_name_is_not_a_token_blob(self):
        self.assert_silent(
            'os.environ["CCPR_TEST_YOUTRACK_TOKEN_FILE_EXPANDVARS"] = "x"\n',
            "sample.py",
        )

    def test_fp_the_tdd_cycle_name_is_not_personal_data(self):
        self.assert_silent("TDD Workflow (Red-Green-Refactor)\n")

    def test_fp_red_green_colour_vision_wording_in_an_a11y_skill_is_not_personal_data(self):
        self.assert_silent(
            "Use a colour-blind-friendly palette; red-green combinations fail.\n"
        )

    def test_fp_an_rfc2606_example_email_is_not_a_real_address(self):
        self.assert_silent(
            "INDEX = '- [Alpha](a.md) — someone@example.com'\n"
            "OTHER = 'test@example.org'\n"
            "THIRD = 'x@sub.example.net'\n",
            "sample.py",
        )

    def test_fp_a_reserved_tld_email_is_not_a_real_address(self):
        self.assert_silent(
            "a@host.invalid b@host.test c@box.localhost d@thing.example\n"
        )

    def test_fp_a_placeholder_credential_in_a_url_template_is_not_a_connection_string(self):
        self.assert_silent(
            'sed -E "s#^https://#https://oauth2:${tok}@#"\n'
            "url = 'https://user:<your-token>@host/path'\n"
            'other = "https://user:{{PASSWORD}}@host/path"\n',
            "sample.sh",
        )

    def test_fp_bearer_used_as_an_ordinary_noun_is_not_a_token_header(self):
        # "bearer" is ordinary English vocabulary. An unanchored "bearer <word>"
        # match lands in exactly the false-positive class the 40-character rule
        # was retired for in WI-0004 -- a long identifier following a trigger
        # word, not a credential. None of these three sentences carries a `:`
        # or `=` before "bearer", so the anchored pattern must stay silent.
        self.assert_silent(
            "The bearer authentication_mechanism_documented_below is standard.\n"
            "See the bearer token_handling_and_refresh_strategy section.\n"
            "A bearer instrument_transfers_ownership_on_delivery in finance.\n"
        )

    def test_a_real_connection_string_still_fires(self):
        self.assert_fires("db = '" + CONNECTION_STRING + "'\n", "secret")

    def test_a_domain_that_merely_ends_in_test_is_still_a_real_address(self):
        self.assert_fires("mail " + NEAR_RESERVED_EMAIL + "\n", "personal")

    def test_a_reserved_domain_used_as_a_prefix_is_still_a_real_address(self):
        # GATE_RE_EMAIL_RESERVED anchors on `$`. Without it, "@example.com"
        # would match as a substring of the extracted email and suppress a
        # real, attacker-controlled address.
        self.assert_fires("mail " + RESERVED_PREFIX_EMAIL + "\n", "personal")


# ---------------------------------------------------------------------------
# 2b. The credential slot of a connection string.
#
# The placeholder exemption is the one place where the gate deliberately stays
# silent on a shape that otherwise looks exactly like a leak. That makes it the
# most dangerous rule in the file: every character it treats as "this is only a
# template" is a character an attacker -- or an ordinary careless commit -- can
# put inside a real password to turn the check off.
# ---------------------------------------------------------------------------
class CredentialSlotTest(GateTestBase):
    def test_a_percent_encoded_password_is_not_a_placeholder(self):
        # `p%40ss` is the correct URL encoding of `p@ss`.
        self.assert_fires('db = "' + PCT_ENCODED_CONNSTRING + '"\n', "secret")

    def test_a_percent_encoded_dollar_in_a_password_is_not_a_placeholder(self):
        self.assert_fires("uri = '" + PCT_ENCODED_DOLLAR + "'\n", "secret")

    def test_a_star_inside_a_password_is_not_a_mask(self):
        self.assert_fires("registry = '" + STAR_CONNSTRING + "'\n", "secret")

    def test_a_brace_inside_a_password_is_not_a_template(self):
        self.assert_fires("broker = '" + BRACE_CONNSTRING + "'\n", "secret")

    def test_an_angle_bracket_inside_a_password_is_not_a_template(self):
        self.assert_fires("cache = '" + ANGLE_CONNSTRING + "'\n", "secret")

    def test_a_literal_credential_with_a_variable_suffix_is_not_a_template(self):
        self.assert_fires("u = '" + SUFFIXED_CONNSTRING + "'\n", "secret", "s.sh")

    def test_a_literal_credential_with_a_variable_prefix_is_not_a_template(self):
        self.assert_fires("u = '" + PREFIXED_CONNSTRING + "'\n", "secret", "s.sh")

    # --- the shapes that must stay silent ---------------------------------
    def test_a_shell_variable_slot_is_still_a_template(self):
        self.assert_silent(
            'sed -E "s#^https://#https://oauth2:${tok}@#"\n'
            'bare = "https://oauth2:$TOKEN@host/path"\n',
            "sample.sh",
        )

    def test_an_angle_placeholder_slot_is_still_a_template(self):
        self.assert_silent("url = 'https://user:<your-token>@host/path'\n", "sample.sh")

    def test_a_mustache_slot_is_still_a_template(self):
        self.assert_silent('u = "https://user:{{PASSWORD}}@host/path"\n', "sample.sh")

    def test_a_printf_format_slot_is_still_a_template(self):
        self.assert_silent('printf "https://user:%s@host/path" "$pw"\n', "sample.sh")

    def test_a_masked_slot_is_still_a_template(self):
        self.assert_silent("log: https://user:****@host/path\n")


# ---------------------------------------------------------------------------
# 2c. The keyword-assignment backstop.
#
# Dropping the generic length rule was right, but it moved weight onto check 1a:
# the library's own comment names it "the backstop for that, and it is how a
# credential normally appears in a config or a doc". A backstop that cannot read
# the most common configuration format on earth is not a backstop.
# ---------------------------------------------------------------------------
class KeywordAssignmentBackstopTest(GateTestBase):
    def test_a_json_quoted_key_still_reaches_the_backstop(self):
        self.assert_fires(JSON_TOKEN + "\n", "secret", "config.json")

    def test_a_quoted_key_with_space_before_the_colon_reaches_the_backstop(self):
        self.assert_fires(JSON_SPACED_SECRET + "\n", "secret", "config.json")

    def test_a_single_quoted_key_reaches_the_backstop(self):
        self.assert_fires(PY_DICT_API_KEY + "\n", "secret", "settings.py")

    # --- what the quote must NOT drag in ----------------------------------
    def test_a_keyword_pointing_at_a_path_is_still_a_location_not_a_secret(self):
        # The value must start alphanumeric; a path is where a credential lives,
        # not the credential. Quoting the key must not change that.
        self.assert_silent(
            'token: ~/.claude/youtrack-token\n'
            'secret = /root/.config/private/value-store\n'
            '{ "token": "~/.claude/youtrack-token" }\n',
            "config.yml",
        )

    def test_a_quoted_key_naming_a_file_is_not_an_assignment(self):
        self.assert_silent('{ "tokenFile": "somewhere/under/a/long/path/x" }\n', "config.json")


# ---------------------------------------------------------------------------
# 2d. Bearer-token headers (WI-0013 point 1).
#
# "bearer" is already a keyword in check 1a's alternation, but 1a requires the
# keyword immediately before `[:=]`. An HTTP header writes
# `Authorization: Bearer <token>` -- the colon belongs to "Authorization", and
# "Bearer" is followed by whitespace, not `:` or `=` -- so the header falls
# through 1a unless the token happens to be hex/JWT/padded base64 and lands in
# check 1b' instead. This is new detection, not a repair of 1a.
# ---------------------------------------------------------------------------
class BearerTokenTest(GateTestBase):
    def test_a_bearer_header_with_an_opaque_token_fires_as_secret(self):
        self.assert_fires(BEARER_TOKEN + "\n", "secret")

    def test_a_bearer_env_var_assignment_still_fires_as_secret(self):
        # The colon form above is not the only real shape: an env-var
        # assignment anchors on `=` and a quote instead of `:`. If the anchor
        # narrowed to `:` only, this would go silent and the check would have
        # traded one false-positive class for a false-negative one.
        self.assert_fires(BEARER_ENV_VAR + "\n", "secret", "sample.sh")

    def test_a_bearer_token_too_short_to_reach_the_floor_stays_silent(self):
        self.assert_silent("Authorization: Bearer short-lived\n")

    # --- placeholder shapes must stay silent, same vocabulary as check 1c ---
    def test_a_bearer_angle_placeholder_is_still_a_template(self):
        self.assert_silent("Authorization: Bearer <token>\n")

    def test_a_bearer_shell_variable_is_still_a_template(self):
        self.assert_silent('auth = "Bearer $TOKEN"\n', "sample.sh")

    def test_a_bearer_braced_shell_variable_is_still_a_template(self):
        self.assert_silent('auth = "Bearer ${TOKEN}"\n', "sample.sh")

    def test_a_bearer_python_fstring_slot_is_still_a_template(self):
        self.assert_silent(
            'req.add_header("Authorization", f"Bearer {token}")\n', "sample.py"
        )

    def test_a_bearer_mustache_slot_is_still_a_template(self):
        self.assert_silent('auth = "Bearer {{TOKEN}}"\n')

    def test_a_bearer_printf_format_slot_is_still_a_template(self):
        self.assert_silent('printf "Bearer %s" "$tok"\n', "sample.sh")

    def test_a_bearer_masked_slot_is_still_a_template(self):
        self.assert_silent("log: Bearer ****************\n")


# ---------------------------------------------------------------------------
# 2e. Placeholder WORDS in a 1a/1a' value (WI-0035).
#
# GATE_RE_PLACEHOLDER_SLOT (2b, above) stays silent on '${...}', '<...>',
# '{{...}}', a '%'-format slot and '***' because every one of those shapes
# opens with a character outside [A-Za-z0-9+] -- the same class the 1a/1a'
# value itself must start with. 'YOUR_TOKEN_HERE_REPLACE_ME' opens with a
# plain alphanumeric, so none of that reasoning reaches it; a documentation
# placeholder written in screaming-snake-case still reads as a real
# credential to the keyword-assignment and bearer-header rules.
#
# Scoped to 1a (GATE_RE_SECRET_KV) and 1a' (GATE_RE_SECRET_BEARER) only. The
# vendor/blob/private-key/connection-string rules get no placeholder-word
# filter and must not: WI-0035 measured that the shape-based alternative this
# item considered and rejected (dropping values of only capitals, digits and
# underscores) is congruent with GATE_RE_SECRET_VENDOR's own AWS Access Key
# ID shape. AWS's own documentation access key (AWS_DOC_EXAMPLE_KEY below) is
# proof: it contains a listed word (EXAMPLE) and must still fire, via the
# vendor rule, which carries no such filter.
# ---------------------------------------------------------------------------
class PlaceholderWordInKeywordOrBearerValueTest(GateTestBase):
    def test_the_first_reported_bearer_placeholder_goes_silent(self):
        self.assert_silent(PLACEHOLDER_BEARER_1 + "\n")

    def test_the_second_reported_bearer_placeholder_goes_silent(self):
        self.assert_silent(PLACEHOLDER_BEARER_2 + "\n")

    def test_a_keyword_assignment_placeholder_goes_silent_too(self):
        # Same filter, the other rule it is scoped to -- 1a, not just 1a'.
        self.assert_silent(PLACEHOLDER_KV + "\n")

    def test_a_lowercase_placeholder_word_goes_silent_too(self):
        # Case-insensitive by design: WI-0035's word list is spelled in caps
        # because both reported cases were, but the filter must not become a
        # letter-case check by the back door -- that is exactly the shape the
        # PO decision rejected for the OTHER half of this item.
        self.assert_silent(PLACEHOLDER_BEARER_LOWERCASE + "\n")

    def test_a_value_that_merely_contains_a_placeholder_word_goes_silent(self):
        # Decided: the filter checks CONTAINS, not IS -- an otherwise
        # credential-shaped value with a listed word sitting mid-string is
        # dropped too. Be precise about which direction that fails in, since
        # this test pins a SILENCED credential-shaped value: it is the list's
        # INCOMPLETENESS that fails safely (an unlisted word still fires).
        # A listed word landing inside a genuinely real value IS a missed
        # leak -- accepted because the odds of a random credential carrying
        # one of these words are negligible, not because it cannot happen.
        self.assert_silent(PLACEHOLDER_WORD_MID_VALUE_KV + "\n")

    def test_a_mixed_case_credential_without_a_placeholder_word_still_fires(self):
        # Regression guard: the filter must not over-match on mixed case or
        # on credential-shaped values that carry no listed word.
        self.assert_fires(CREDENTIAL + "\n", "secret")

    def test_a_real_credential_still_fires_when_the_LINE_says_example(self):
        # The one that makes `-o` load-bearing rather than cosmetic. The
        # filter drops a candidate whose MATCH contains a listed word; the
        # match is the keyword + separator + value, not the whole line. Prose
        # elsewhere on the line must not silence a real credential.
        #
        # Measured: with `-o` removed (filtering line-wise instead), this
        # input yields 0 findings while the whole suite stays green -- a
        # genuine credential silenced by an unrelated word, the one direction
        # this gate must not fail in. Nothing else pins it.
        self.assert_fires("For example, see the docs: " + CREDENTIAL + "\n", "secret")

    def test_two_candidates_on_one_line_are_reported_separately(self):
        # Second consequence of `-o`, pinned so the granularity change is a
        # decision rather than a side effect: line-wise extraction reported
        # such a line once, match-wise reports it twice.
        text = CREDENTIAL + " and " + leak("to", "ken = ") + "Z9y8X7w6V5u4T3s2R1q0P9\n"
        r = self.run_gate(self.write("sample.md", text))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(
            (r.stdout + r.stderr).count("[secret]"), 2, r.stdout + r.stderr
        )

    def test_aws_doc_example_key_still_fires_via_the_vendor_rule(self):
        self.assert_fires(
            "AWS docs use " + AWS_DOC_EXAMPLE_KEY + " as the demo access key.\n",
            "secret",
        )


# ---------------------------------------------------------------------------
# 3. The deny-list — the check that would actually have caught the breach.
# ---------------------------------------------------------------------------
class DenyListTest(GateTestBase):
    def test_a_configured_name_is_reported(self):
        self.write_config(denyNames=["Zorblatt"])
        self.assert_fires("The Zorblatt rollout taught us to check earlier.\n", "denylist")

    def test_matching_is_case_insensitive(self):
        self.write_config(denyNames=["Zorblatt"])
        self.assert_fires("the zorblatt migration\n", "denylist")

    def test_a_name_embedded_in_an_identifier_is_reported(self):
        self.write_config(denyNames=["Zorblatt"])
        self.assert_fires("class ZorblattBackend:\n    pass\n", "denylist")

    def test_a_configured_name_is_never_echoed_into_the_output(self):
        self.write_config(denyNames=["Zorblatt"])
        p = self.write("sample.md", "The Zorblatt rollout.\n")
        r = self.run_gate(p)
        self.assertNotIn("Zorblatt", r.stdout + r.stderr)
        self.assertNotIn("zorblatt", (r.stdout + r.stderr).lower())

    def test_a_name_is_matched_literally_not_as_a_regex(self):
        self.write_config(denyNames=["a.c"])
        self.assert_silent("abc is not the configured name\n")

    def test_an_unrelated_file_stays_clean_with_a_configured_list(self):
        self.write_config(denyNames=["Zorblatt", "Quuxcorp"])
        self.assert_silent(CLEAN_TEXT)

    def test_an_absent_config_reports_not_configured_and_does_not_pass_silently(self):
        p = self.write("sample.md", CLEAN_TEXT)
        r = self.run_gate(p)
        self.assertIn("NOT CONFIGURED", r.stdout + r.stderr)

    def test_an_empty_deny_list_also_reports_not_configured(self):
        self.write_config(denyNames=[])
        p = self.write("sample.md", CLEAN_TEXT)
        r = self.run_gate(p)
        self.assertIn("NOT CONFIGURED", r.stdout + r.stderr)

    def test_require_denylist_turns_a_missing_configuration_into_a_failure(self):
        p = self.write("sample.md", CLEAN_TEXT)
        r = self.run_gate("--require-denylist", p)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_require_denylist_is_satisfied_by_a_configured_list(self):
        self.write_config(denyNames=["Zorblatt"])
        p = self.write("sample.md", CLEAN_TEXT)
        r = self.run_gate("--require-denylist", p)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    # --- the path is content too ------------------------------------------
    def test_a_tenant_name_in_the_file_name_is_a_finding_even_when_the_content_is_clean(self):
        # A file called after a tenant carries the name into every directory
        # listing, index and CI log that mentions it. Reading only the bytes
        # inside misses the most visible copy.
        self.write_config(denyNames=["Zorblatt"])
        p = self.write("zorblatt-rollout.md", "Nothing sensitive inside at all.\n")
        r = self.run_gate(p)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("denylist", self.categories(r))

    def test_a_tenant_name_in_a_parent_directory_is_a_finding_too(self):
        self.write_config(denyNames=["Zorblatt"])
        p = self.write("zorblatt/notes.md", "Nothing sensitive inside at all.\n")
        r = self.run_gate(p)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_the_finding_line_does_not_leak_the_name_through_the_path(self):
        # The old output printed `<tenant>-rollout.md:1: ... (name redacted)` --
        # a line that names the tenant while claiming it did not.
        self.write_config(denyNames=["Zorblatt"])
        p = self.write("zorblatt-rollout.md", "The Zorblatt rollout.\n")
        r = self.run_gate(p)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotIn("zorblatt", (r.stdout + r.stderr).lower())

    def test_path_redaction_is_case_insensitive_like_the_content_match(self):
        self.write_config(denyNames=["zorblatt"])
        p = self.write("ZorBlatt-Rollout.md", "clean prose\n")
        r = self.run_gate(p)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotIn("zorblatt", (r.stdout + r.stderr).lower())

    def test_a_secret_in_a_tenant_named_file_reports_without_leaking_the_path(self):
        # The content finding's own path prefix is the leak, so every line for
        # that file has to be redacted -- not just the deny-list one.
        self.write_config(denyNames=["Zorblatt"])
        p = self.write("zorblatt-config.md", "see " + HOME_PATH + "\n")
        r = self.run_gate(p)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("personal", self.categories(r))
        self.assertNotIn("zorblatt", (r.stdout + r.stderr).lower())

    def test_a_tenant_name_in_a_binary_file_name_is_still_a_finding(self):
        # A binary's bytes are skipped, but its NAME ships exactly like a text
        # file's: an image called after a tenant is in the repository index, in
        # the checkout, and in every log line that mentions it.
        self.write_config(denyNames=["Zorblatt"])
        p = self.work / "zorblatt-logo.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        r = self.run_gate(p)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("denylist", self.categories(r))
        self.assertNotIn("zorblatt", (r.stdout + r.stderr).lower())

    def test_a_binary_with_a_clean_name_is_still_only_skipped(self):
        # The bytes stay out of scope; adding the name check must not start
        # reporting binary content.
        self.write_config(denyNames=["Zorblatt"])
        repo = self.work / "brepo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=self.env())
        (repo / "a.md").write_text(CLEAN_TEXT, encoding="utf-8")
        (repo / "logo.png").write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00" + b"Zorblatt".upper() + b"\x00")
        env = self.env(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@host.invalid",
                       GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@host.invalid")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
        subprocess.run(["git", "commit", "-qm", "x"], cwd=repo, check=True, env=env)
        r = self.run_gate("--repo", repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_an_unrelated_path_is_printed_unchanged(self):
        self.write_config(denyNames=["Zorblatt"])
        p = self.write("ordinary-notes.md", "see " + HOME_PATH + "\n")
        r = self.run_gate(p)
        self.assertIn("ordinary-notes.md", r.stdout)

    def test_an_environment_supplied_list_works_without_a_config_file(self):
        # CI has no personal config file; a secret store can supply the names.
        p = self.write("sample.md", "The Zorblatt rollout.\n")
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES="Zorblatt\nQuuxcorp")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("denylist", self.categories(r))

    # --- a list that is quietly shorter than configured --------------------
    def test_a_name_containing_a_tab_is_actually_checked(self):
        # Names arrive over a tab-delimited transport, but only the FIRST tab
        # separates the record key from the value, so an interior tab survives
        # it intact. Dropping such a name was a precaution against a problem the
        # transport does not have.
        self.write_config(denyNames=["Zorb\tlatt"])
        p = self.write("sample.md", "The Zorb\tlatt rollout.\n")
        r = self.run_gate(p)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("denylist", self.categories(r))

    def test_a_tab_bearing_name_is_not_dropped_behind_a_deny_list_active_banner(self):
        # The dangerous shape: one good name makes the run announce the list as
        # active while a second one is never checked.
        self.write_config(denyNames=["Quuxcorp", "Zorb\tlatt"])
        p = self.write("sample.md", "The Zorb\tlatt rollout.\n")
        r = self.run_gate(p)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_name_containing_a_newline_is_rejected_loudly(self):
        # This one the transport genuinely cannot carry -- it would silently
        # become two shorter names, each matching far more than intended. The
        # answer is to refuse the configuration, not to shorten the list.
        self.write_config(denyNames=["Quuxcorp", "Zorb\nlatt"])
        p = self.write("sample.md", CLEAN_TEXT)
        r = self.run_gate(p)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_the_rejection_names_the_offending_entry_by_index(self):
        self.write_config(denyNames=["Quuxcorp", "Zorb\nlatt"])
        p = self.write("sample.md", CLEAN_TEXT)
        r = self.run_gate(p)
        self.assertIn("#2", r.stdout + r.stderr)

    def test_the_rejection_does_not_echo_the_offending_name(self):
        self.write_config(denyNames=["Quuxcorp", "Zorb\nlatt"])
        p = self.write("sample.md", CLEAN_TEXT)
        r = self.run_gate(p)
        self.assertNotIn("zorb", (r.stdout + r.stderr).lower())

    def test_an_unusable_entry_is_refused_before_any_scanning_happens(self):
        # Reporting it at the end would mean the findings were produced by the
        # shortened list the run is complaining about.
        self.write_config(denyNames=["Zorb\nlatt"])
        p = self.write("sample.md", CLEAN_TEXT)
        r = self.run_gate(p)
        self.assertNotIn("scanned", r.stdout)

    def test_a_blank_deny_name_entry_is_rejected_loudly(self):
        # An empty pattern matches every line; it cannot be honoured either.
        self.write_config(denyNames=["Quuxcorp", "   "])
        p = self.write("sample.md", CLEAN_TEXT)
        r = self.run_gate(p)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# 3b. WI-0028 — gate_path_deny_index / gate_redact_path exercised through
# artifact-gate.sh's own call site (artifact-gate.sh:159-160), including the
# non-ASCII / NFC-NFD folding escalation (WI-0014's B2/B3).
#
# DenyListTest above already proves plain-ASCII path matching through this
# entry point. The Unicode escalation shared with it (gate_path_deny_index /
# gate_redact_path in lib/discipline_gate.sh) was, until this class, only
# ever exercised through the OTHER caller -- memory-sync.sh promote's
# destination check (test_memory_sync_promote.py, NonAsciiDenyNameTest). The
# underlying function is unchanged and already proven correct there; what was
# unverified is whether THIS call site invokes and redacts correctly, e.g. on
# a repo file whose name carries a deny-listed name in NFD.
#
# The deny name is fictional and supplied only via CCPR_GATE_DENY_NAMES, per
# the same isolation DenyListTest already uses -- never the real, personal
# gate config.
# ---------------------------------------------------------------------------
class NonAsciiPathDenyTest(GateTestBase):
    # Fictional, non-ASCII on purpose -- the same fixture shape as
    # NonAsciiDenyNameTest in test_memory_sync_promote.py, which exercises the
    # identical shared library function through the other entry point.
    NAME = "Quüxcorp"

    @staticmethod
    def nfd(s):
        import unicodedata
        return unicodedata.normalize("NFD", s)

    @staticmethod
    def nfc(s):
        import unicodedata
        return unicodedata.normalize("NFC", s)

    def test_a_decomposed_filename_matches_a_composed_deny_entry(self):
        p = self.write(self.nfd(self.NAME) + "-notes.md", "clean prose\n")
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES=self.nfc(self.NAME))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("denylist", self.categories(r))

    def test_a_composed_filename_matches_a_decomposed_deny_entry(self):
        # Both sides are normalised, not just the one the operator typed.
        p = self.write(self.nfc(self.NAME) + "-notes.md", "clean prose\n")
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES=self.nfd(self.NAME))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("denylist", self.categories(r))

    def test_an_upper_cased_non_ascii_filename_is_reported(self):
        # `grep -Fi` under LC_ALL=C folds ASCII case only; the upper-cased ü
        # needs the python3 escalation to be recognised at all.
        p = self.write(self.NAME.upper() + "-notes.md", "clean prose\n")
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES=self.NAME)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("denylist", self.categories(r))

    def test_the_non_ascii_name_is_never_echoed_into_the_output(self):
        # The matcher and the mask must agree: a matcher that folds more than
        # the mask does turns every catch into a disclosure.
        p = self.write(self.NAME.upper() + "-notes.md", "clean prose\n")
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES=self.NAME)
        out = r.stdout + r.stderr
        for spelling in (self.NAME, self.NAME.upper(), self.nfd(self.NAME),
                         self.nfd(self.NAME).upper()):
            self.assertNotIn(spelling.lower(), out.lower(), out)
        self.assertIn("<redacted>", out, out)

    def test_an_unrelated_non_ascii_filename_stays_clean(self):
        # Folding wider must not mean matching wider: a diacritic is not a
        # wildcard, and "grün" is not "Quüxcorp".
        p = self.write("grün-notes.md", "clean prose\n")
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES=self.NAME)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# 3c. WI-0049 — a fatally broken python3 must not read as "no match".
#
# gate_path_deny_index's python escalation signalled "no match" with the same
# exit status (1) a broken interpreter produces on start-up failure (measured:
# `PYTHONHOME=/nonexistent python3 -c pass` exits 1). The `*)` case arm written
# to catch "the comparison did not happen" and fall back to the ASCII matcher
# was therefore unreachable for the most likely fault, and a dead matcher read
# as a clean path. PO decision (WI-0049, 20.08.2026): keep the existing
# fail-warn-and-fall-back shape, make the arm it was written for reachable —
# not a hard abort, not a third verdict.
#
# The function-level tests below (UnicodePyIndexExitContractTest,
# GatePathDenyIndexBrokenInterpreterTest) pin the internal python<->shell
# signalling contract the fix changes. BrokenInterpreterEndToEndTest proves the
# regression itself through the same entry point WI-0049 measured it through.
# All of them break python3 with PYTHONHOME=/nonexistent, the way the item
# measured it — a fake python3 planted on PATH proves less (see the item's
# second, downgraded finding) and is deliberately not used here.
# ---------------------------------------------------------------------------
class UnicodePyIndexExitContractTest(GateTestBase):
    """Direct pin on _gate_unicode_py's exit-status contract in index mode:
    0 = match (stdout carries the 1-based index), a dedicated sentinel = no
    match, anything else = the helper did not run to completion. This is the
    signal gate_path_deny_index's case arms are keyed on."""

    NAME = "Quüxcorp"
    NO_MATCH_SENTINEL = 2

    def call(self, subject, names, python_home=None):
        # GATE_DENY_NAMES is reset to "" on every source of the library (see
        # discipline_gate.sh:182), so it is populated the way every real
        # caller populates it: via gate_load_config reading CCPR_GATE_DENY_NAMES.
        script = (
            f"source {shlex.quote(str(LIB))}; gate_load_config; "
            f"_gate_unicode_py index {shlex.quote(subject)}"
        )
        extra = {"CCPR_GATE_DENY_NAMES": names}
        if python_home is not None:
            extra["PYTHONHOME"] = python_home
        return subprocess.run(
            ["bash", "-c", script], capture_output=True, text=True,
            env=self.env(**extra),
        )

    def test_a_match_exits_zero_and_prints_the_one_based_index(self):
        r = self.call(self.NAME + "-notes.md", self.NAME)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "1")

    def test_a_healthy_no_match_exits_with_the_dedicated_sentinel_not_one(self):
        # The regression: the old no-match signal (1) collides with a broken
        # interpreter's start-up exit status. Pinning it away from 1 is the
        # fix.
        r = self.call("grün-notes.md", self.NAME)
        self.assertEqual(r.returncode, self.NO_MATCH_SENTINEL, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "")

    def test_a_broken_interpreter_exits_one_distinct_from_the_no_match_sentinel(self):
        r = self.call(self.NAME + "-notes.md", self.NAME, python_home="/nonexistent")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotEqual(r.returncode, self.NO_MATCH_SENTINEL)


class GatePathDenyIndexBrokenInterpreterTest(GateTestBase):
    """gate_path_deny_index's own external return contract (0/idx on match, 1
    and no stdout on no match) must survive a broken interpreter — the fix
    only changes the INTERNAL python<->shell signal, per WI-0049."""

    NAME = "Quüxcorp"

    def call(self, subject, names, python_home=None):
        script = (
            f"source {shlex.quote(str(LIB))}; gate_load_config; "
            f"gate_path_deny_index {shlex.quote(subject)}"
        )
        extra = {"CCPR_GATE_DENY_NAMES": names}
        if python_home is not None:
            extra["PYTHONHOME"] = python_home
        return subprocess.run(
            ["bash", "-c", script], capture_output=True, text=True,
            env=self.env(**extra),
        )

    def test_healthy_interpreter_no_match_returns_one_silently(self):
        # The path most likely to break by this fix: a genuine no-match with a
        # working interpreter must still say "no match", not "matcher failed".
        r = self.call("grün-notes.md", self.NAME)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertNotIn("unicode matcher failed", r.stderr)

    def test_broken_interpreter_falls_back_and_still_finds_a_literal_match(self):
        # Same casing/normalisation on both sides means the ASCII fallback's
        # plain byte-literal grep still finds it once the warning fires.
        r = self.call(self.NAME + "-notes.md", self.NAME, python_home="/nonexistent")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "1")
        self.assertIn("unicode matcher failed", r.stderr)

    def test_broken_interpreter_does_not_silently_report_a_clean_path(self):
        # The regression itself, at function level: a subject the ASCII
        # fallback also cannot see (case-folding only reachable via python)
        # must NOT come back as "no match" without the warning that says the
        # comparison did not fully happen.
        r = self.call(self.NAME.upper() + "-notes.md", self.NAME, python_home="/nonexistent")
        self.assertIn("unicode matcher failed", r.stderr)
        # Pinned deliberately, and it is NOT a 0: this is the residual cost the
        # PO accepted when choosing warn-and-fall-back over a hard abort. The
        # ASCII fallback cannot fold a non-ASCII letter's case, so it reports
        # "no match" (1) on a subject that genuinely carries the name. What the
        # fix bought is that it can no longer happen SILENTLY -- the warning
        # above is the whole difference. Asserting the 1 here keeps the test
        # from reading as proof of something stronger than it shows.
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)


class GateRedactPathBrokenInterpreterTest(GateTestBase):
    """gate_redact_path (the fail-closed sibling call site) is untouched by
    this fix — pinned so a future change to the shared python block cannot
    silently regress it."""

    NAME = "Quüxcorp"

    def call(self, subject, names, python_home=None):
        script = (
            f"source {shlex.quote(str(LIB))}; gate_load_config; "
            f"gate_redact_path {shlex.quote(subject)}"
        )
        extra = {"CCPR_GATE_DENY_NAMES": names}
        if python_home is not None:
            extra["PYTHONHOME"] = python_home
        return subprocess.run(
            ["bash", "-c", script], capture_output=True, text=True,
            env=self.env(**extra),
        )

    def test_result_is_unchanged_by_a_broken_interpreter(self):
        subject = self.NAME + "-notes.md"
        healthy = self.call(subject, self.NAME)
        broken = self.call(subject, self.NAME, python_home="/nonexistent")
        self.assertEqual(healthy.stdout, broken.stdout)
        self.assertIn("<redacted>", healthy.stdout)
        self.assertIn("unicode masker failed", broken.stderr)


class BrokenInterpreterEndToEndTest(GateTestBase):
    """The regression as WI-0049 measured it: through artifact-gate.sh itself,
    on the entry point a CI job actually calls."""

    NAME = "Quüxcorp"

    def test_a_broken_interpreter_does_not_report_a_clean_pass(self):
        p = self.write(self.NAME + "-notes.md", "clean prose\n")
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES=self.NAME, PYTHONHOME="/nonexistent")

        # Assert the verdict AND the warning text, not just a non-zero exit —
        # a non-zero exit alone could equally mean the gate crashed for an
        # unrelated reason.
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("denylist", self.categories(r))
        self.assertIn("unicode matcher failed", r.stdout + r.stderr)
        self.assertNotIn("scanned 1 files, 0 findings", r.stdout)

    def test_an_ascii_only_subject_never_invokes_python_at_all(self):
        # _gate_needs_unicode's ASCII fast path means a broken interpreter
        # changes nothing here — python3 is never started.
        p = self.write("acme-notes.md", "clean prose\n")
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES="acme", PYTHONHOME="/nonexistent")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("denylist", self.categories(r))
        out = r.stdout + r.stderr
        self.assertNotIn("unicode matcher failed", out)
        self.assertNotIn("Fatal Python error", out)


# ---------------------------------------------------------------------------
# 3d. WI-0017 part (2) — content-side deny matching escalates to python3, but
# ONLY when the configured NAME is non-ASCII, never on the file content.
#
# Gating on subject-or-name the way the path side does was measured and
# rejected (WI-0017, 20.08.2026): 257 of this repo's own 271 tracked files
# carry a non-ASCII byte (em dashes, umlauts in prose), so that gate would
# fire on 94% of files and add ~41% to every sweep even with a pure-ASCII
# deny list. Gating on the name alone costs zero extra process starts
# whenever the deny list is pure ASCII, which
# AnAsciiDenyNameNeverInvokesPython3Test proves rather than asserts.
#
# For an ASCII name the ASCII matcher is provably safe without escalation:
# it can only OVER-report relative to python's NFC view (AsciiOverReport...
# below), never miss what python would find, so LC_ALL=C is not needed at
# that line either — the PO decision this item's history shows was added,
# then shelved, then finally dropped for this reason.
# ---------------------------------------------------------------------------
class ContentDenyEscalationTest(GateTestBase):
    # Fictional, non-ASCII on purpose — same fixture shape as
    # NonAsciiPathDenyTest above, which exercises the sibling path-side
    # escalation.
    NAME = "Quüxcorp"

    def test_a_non_ascii_name_differing_only_in_case_is_found_in_content(self):
        # The defect this item exists for: content-side matching was
        # ASCII-only, so a configured name that differs from the content
        # only in a non-ASCII letter's case slipped through.
        p = self.write("sample.md", "See " + self.NAME.upper() + " rollout notes.\n")
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES=self.NAME)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("denylist", self.categories(r))

    def test_a_decomposed_non_ascii_name_in_content_matches_a_composed_deny_entry(self):
        # The item's own other named failure mode, alongside the case
        # difference above: "a tenant name written in NFD inside a file's
        # CONTENT... still passes the content gate". Both sides are
        # normalised to NFC before comparison, mirroring the path side.
        import unicodedata
        p = self.write("sample.md", "See " + unicodedata.normalize("NFD", self.NAME) + " rollout notes.\n")
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES=self.NAME)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("denylist", self.categories(r))

    def test_the_non_ascii_name_is_never_echoed_into_the_content_finding(self):
        p = self.write("sample.md", "See " + self.NAME.upper() + " rollout notes.\n")
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES=self.NAME)
        out = r.stdout + r.stderr
        self.assertNotIn(self.NAME.lower(), out.lower())
        self.assertIn("name redacted", out)

    def test_the_match_carries_the_correct_line_number(self):
        text = "line one\nline two\nSee " + self.NAME.upper() + " here\nline four\n"
        p = self.write("sample.md", text)
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES=self.NAME)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(":3:", r.stdout, r.stdout)

    def test_a_file_larger_than_an_env_var_could_carry_is_scanned_without_error(self):
        # ARG_MAX is 1 MiB on this machine (measured in the item); content now
        # travels on stdin, not through the environment the way the path
        # subject does. A few hundred KB is enough to prove the stdin route
        # without generating a full ARG_MAX+ fixture.
        filler = "ordinary prose line without a match.\n" * 8000  # ~300 KB
        text = filler + "See " + self.NAME.upper() + " rollout notes.\n"
        p = self.write("sample.md", text)
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES=self.NAME)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("denylist", self.categories(r))
        self.assertIn("scanned 1 files", r.stdout)

    def test_an_ascii_deny_name_never_invokes_python3(self):
        # Proof, not assertion: a python3 that shadows this run's PATH and
        # exits non-zero must not change the outcome for an ASCII name. If
        # python were invoked, the run would warn ("unicode content matcher
        # failed") and fall back instead of answering directly.
        stub_dir = Path(tempfile.mkdtemp(prefix="ccpr-fake-python3-"))
        self.addCleanup(shutil.rmtree, stub_dir, ignore_errors=True)
        stub = stub_dir / "python3"
        stub.write_text("#!/bin/sh\nexit 7\n")
        stub.chmod(0o755)
        p = self.write("sample.md", "The Zorblatt rollout.\n")
        r = self.run_gate(
            p, CCPR_GATE_DENY_NAMES="Zorblatt",
            PATH=f"{stub_dir}:/usr/bin:/bin:/usr/sbin:/sbin",
        )
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("denylist", self.categories(r))
        out = r.stdout + r.stderr
        self.assertNotIn("unicode content matcher failed", out)
        self.assertNotIn("falling back", out)

    def test_the_path_side_escalation_is_unchanged(self):
        # Pin: this item touches content matching only.
        p = self.write(self.NAME.upper() + "-notes.md", "clean prose\n")
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES=self.NAME)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("denylist", self.categories(r))

    def test_ascii_name_over_reports_on_nfd_decomposed_content_rather_than_missing_it(self):
        # Pinned exactly as measured in the item: an ASCII name against
        # NFD-decomposed content is found by the byte-literal ASCII matcher
        # even though NFC-normalised python would not — over-reporting is the
        # safe direction for this gate, and it is why an ASCII name needs no
        # escalation at all.
        import unicodedata
        decomposed = unicodedata.normalize("NFD", "café") + " rollout notes\n"
        p = self.write("sample.md", decomposed)
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES="cafe")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("denylist", self.categories(r))

    def test_an_unrelated_file_with_a_non_ascii_deny_name_stays_clean(self):
        # Scope check: "no findings" must mean the file was actually
        # scanned, not that nothing ran.
        p = self.write("sample.md", "grün prose, unrelated content\n")
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES=self.NAME)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("scanned 1 files", r.stdout)

    def test_a_file_larger_than_arg_max_is_still_matched(self):
        # Pins the STDIN route as load-bearing, not a style preference. The
        # content reaches python on stdin; carrying it in an environment
        # variable instead works only until the file exceeds ARG_MAX (1 MB
        # here), and then it does not fail loudly -- it fails into a WRONG
        # ANSWER.
        #
        # Measured on a 2.2 MB fixture with the deny name planted near the
        # end: stdin route -> exit 1, one denylist finding. Env-var route ->
        # "unicode content matcher failed (status 126)" on stderr, then
        # "scanned 1 files, 0 findings" and exit 0. A configured tenant name
        # in an ordinary large file would ship, with the only warning on a
        # stream CI does not gate on. The mutation that swapped stdin for an
        # env var survived the whole suite before this test existed.
        filler = "a line of ordinary prose that is long enough to matter"
        lines = [filler] * 40000
        lines[39000] = "the " + self.NAME.upper() + " rollout note"
        p = self.write("big.md", "\n".join(lines) + "\n")
        self.assertGreater(p.stat().st_size, 1048576, "fixture must exceed ARG_MAX")
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES=self.NAME)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("denylist", self.categories(r))
        self.assertNotIn("matcher failed", r.stdout + r.stderr)

    def test_a_healthy_no_match_stays_silent_about_the_matcher(self):
        # The genuine no-match case with a working interpreter must not be
        # misread as "the helper did not run" -- that would print the
        # fallback warning on every clean file with a non-ASCII deny name.
        p = self.write("sample.md", "grün prose, unrelated content\n")
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES=self.NAME)
        self.assertNotIn("unicode content matcher failed", r.stdout + r.stderr)


class ContentDenyBrokenInterpreterTest(GateTestBase):
    """Mirrors GatePathDenyIndexBrokenInterpreterTest (WI-0049) for the
    content-side escalation this item adds: fail-warn-and-fall-back, never a
    silent clean read."""

    NAME = "Quüxcorp"

    def test_a_broken_interpreter_does_not_silently_report_a_clean_file(self):
        # The ASCII fallback cannot fold this non-ASCII letter's case, so —
        # same residual WI-0049 accepted on the path side — a subject the
        # fallback genuinely cannot see comes back as "no match" (0). What
        # the fix buys is that it can no longer happen SILENTLY: the warning
        # below is the whole difference, so it must be present even though
        # the verdict itself stays "clean".
        p = self.write("sample.md", "See " + self.NAME.upper() + " here\n")
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES=self.NAME, PYTHONHOME="/nonexistent")
        out = r.stdout + r.stderr
        self.assertIn("unicode content matcher failed", out)
        self.assertEqual(r.returncode, 0, out)

    def test_a_broken_interpreter_still_finds_a_literal_match(self):
        # Same casing on both sides means the ASCII fallback's plain
        # byte-literal grep still finds it once the warning fires.
        p = self.write("sample.md", "See " + self.NAME + " here\n")
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES=self.NAME, PYTHONHOME="/nonexistent")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("denylist", self.categories(r))
        self.assertIn("unicode content matcher failed", r.stdout + r.stderr)

    def test_an_ascii_only_deny_list_never_starts_python_even_with_a_broken_interpreter(self):
        p = self.write("sample.md", "The acme rollout.\n")
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES="acme", PYTHONHOME="/nonexistent")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        out = r.stdout + r.stderr
        self.assertNotIn("unicode content matcher failed", out)
        self.assertNotIn("Fatal Python error", out)


# ---------------------------------------------------------------------------
# 4. The self-match case — the file that defines the patterns.
# ---------------------------------------------------------------------------
class SelfMatchTest(GateTestBase):
    def test_the_pattern_source_file_does_not_report_itself(self):
        r = self.run_gate(LIB)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_gate_entry_point_does_not_report_itself(self):
        r = self.run_gate(GATE)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_memory_sync_entry_point_is_clean(self):
        r = self.run_gate(MEMORY_SYNC)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_pattern_source_exemption_is_reported_not_silent(self):
        r = self.run_gate(LIB)
        self.assertIn("pattern-source", r.stdout + r.stderr)

    def test_the_exemption_marker_does_not_work_in_an_ordinary_file(self):
        # A line-scoped exemption that any file could claim would be a
        # suppression backdoor. It is honoured only inside the pattern source.
        self.assert_fires(
            "leak = '" + HOME_PATH + "'  # " + EXEMPT_MARKER + "\n", "personal", "sample.py"
        )


# ---------------------------------------------------------------------------
# 4b. gate_scan_file's own return-code contract (WI-0013 point 2).
#
# Neither entry point reads this value: artifact-gate.sh and memory-sync.sh
# both capture the function's stdout with `|| true` and derive their own exit
# code by parsing the emitted records instead. The contract the header
# comment documents -- "returns 1 when there was at least one [finding], 0
# otherwise" -- is therefore only observable by calling the function directly,
# which is what this test does; it cannot be pinned through either shell
# entry point's exit code.
# ---------------------------------------------------------------------------
class ScanFileReturnContractTest(GateTestBase):
    def call_gate_scan_file(self, path, profile="artifact"):
        script = (
            f"source {shlex.quote(str(LIB))}; "
            f"gate_scan_file {shlex.quote(str(path))} {shlex.quote(profile)} >/dev/null"
        )
        return subprocess.run(
            ["bash", "-c", script], capture_output=True, text=True, env=self.env()
        )

    def test_a_clean_scan_returns_zero(self):
        p = self.write("clean.md", CLEAN_TEXT)
        r = self.call_gate_scan_file(p)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_dirty_scan_returns_one(self):
        p = self.write("dirty.md", CREDENTIAL + "\n")
        r = self.call_gate_scan_file(p)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# 4b'. run_gate (scripts/memory-sync.sh) must be a real customer of the
# contract pinned above (WI-0036), not just a second independent re-derivation
# of "clean vs. dirty" from the same $out records gate_scan_file also prints.
#
# Proof this is not cosmetic: inverting gate_scan_file's own return statement
# (the library's OWN contract, unrelated to what it prints) must now flip
# memory-sync.sh's `gate` exit code too. Before WI-0036, `run_gate` discarded
# the return value with `|| true` and re-derived its own verdict by parsing
# $out, so this exact mutation left every era test green — it is measured here
# through a scratch copy of the shipped scripts (never the tracked files) so
# the mutation can never leak into a real run.
# ---------------------------------------------------------------------------
class RunGateConsumesScanFileReturnContractTest(GateTestBase):
    def setUp(self):
        super().setUp()
        self.write_config(ipAllowlist="")

    RETURN_TAIL = '[ "$found" -eq 0 ] || return 1\n  return 0\n}'
    INVERTED_TAIL = '[ "$found" -eq 0 ] || return 0\n  return 1\n}'

    def copied_memory_sync(self, lib_text=None):
        """Copies memory-sync.sh + lib/discipline_gate.sh into an isolated scratch
        tree, preserving the relative layout memory-sync.sh's own $HERE lookup
        needs, so a mutated library is exercised without ever touching the
        tracked file discipline_gate.sh."""
        scratch = Path(tempfile.mkdtemp(prefix="ccpr-run-gate-mutation-"))
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        (scratch / "lib").mkdir()
        shutil.copy(MEMORY_SYNC, scratch / "memory-sync.sh")
        text = lib_text if lib_text is not None else LIB.read_text(encoding="utf-8")
        (scratch / "lib" / "discipline_gate.sh").write_text(text, encoding="utf-8")
        return scratch / "memory-sync.sh"

    def run_copied(self, script, *args):
        return subprocess.run(
            ["bash", str(script), *[str(a) for a in args]],
            capture_output=True, text=True, env=self.env(),
        )

    def test_inverting_gate_scan_files_return_value_flips_run_gates_exit_code(self):
        lib_text = LIB.read_text(encoding="utf-8")
        assert self.RETURN_TAIL in lib_text, (
            "mutation target not found — gate_scan_file's final return sequence "
            "moved or was reworded"
        )
        inverted = lib_text.replace(self.RETURN_TAIL, self.INVERTED_TAIL, 1)
        script = self.copied_memory_sync(lib_text=inverted)
        dirty = self.write("dirty.md", CREDENTIAL + "\n")

        r = self.run_copied(script, "gate", dirty)

        # gate_scan_file now (falsely) claims "clean" via its return value while
        # still emitting the finding record on stdout -- run_gate must follow
        # the return value, the same way ScanFileReturnContractTest measures
        # gate_scan_file's own contract directly.
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_an_unmutated_library_still_reports_the_same_dirty_verdict(self):
        """Companion pin: the mutation harness itself must reproduce today's real
        exit code on the unmutated library, or the flip above would not mean
        anything."""
        script = self.copied_memory_sync()
        dirty = self.write("dirty.md", CREDENTIAL + "\n")

        r = self.run_copied(script, "gate", dirty)

        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# 4c. The pattern-source exemption suppresses something today (WI-0013 pt. 3).
#
# WI-0014 planted three connection-string-shaped examples into this file's own
# comments (documenting why the placeholder-slot rule must test "is" and not
# "contains" -- see the lines around GATE_RE_PLACEHOLDER_SLOT). Those comments
# are what make the exemption load-bearing: a byte-identical copy of this file
# at an unexempted path must report them, or the exemption has never been
# proven to suppress anything at all.
# ---------------------------------------------------------------------------
class PatternSourceExemptionIsLoadBearingTest(GateTestBase):
    def test_an_unexempted_copy_of_the_pattern_source_reports_findings(self):
        copy = self.write("discipline_gate_copy.sh", LIB.read_text(encoding="utf-8"))
        r = self.run_gate(copy)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        # Measured, not assumed: this count tracks the current comment body of
        # discipline_gate.sh, not a fixed contract of the gate itself.
        finding_lines = [
            line for line in r.stdout.splitlines() if "] " in line and "[" in line
        ]
        self.assertEqual(len(finding_lines), 3, r.stdout)
        # Line numbers as of this test, not the {95, 96, 104} the work item
        # names: adding the bearer-token pattern block (WI-0013 point 1)
        # shifted these three comment lines down by 20, anchoring
        # GATE_RE_SECRET_BEARER against prose (WI-0013 blocker follow-up)
        # shifted them another 10, and adding the placeholder-word filter
        # (WI-0035) shifted them another 40.
        self.assertIn(":165:", r.stdout)
        self.assertIn(":166:", r.stdout)
        self.assertIn(":174:", r.stdout)
        self.assertEqual(self.categories(r), {"secret"})

    # -----------------------------------------------------------------------
    # WI-0023: an INSTALLED copy of artifact-gate.sh (its own
    # _GATE_PATTERN_SOURCE bound to ~/.claude/scripts/lib/discipline_gate.sh)
    # sees a scanned repository's discipline_gate.sh as exactly this "foreign
    # copy" case -- the three findings above, unexplained. Widening the
    # exemption's file-identity check to recognise it would reopen the
    # "any file could then carry the marker under that name" hole the
    # line-scoped-AND-file-scoped design exists to close (see
    # test_the_exemption_marker_does_not_work_in_an_ordinary_file above), so
    # the finding itself must stay. What closes WI-0023 is a hint on it: a
    # human sees the marker named and understands why, instead of triaging a
    # secret finding that turns out to be the gate's own vocabulary.
    # -----------------------------------------------------------------------
    def test_an_unexempted_copy_names_the_marker_as_a_hint_not_a_silent_pass(self):
        copy = self.write("discipline_gate_copy.sh", LIB.read_text(encoding="utf-8"))
        r = self.run_gate(copy)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(EXEMPT_MARKER, r.stdout)
        self.assertIn("not recognised as the pattern-source file", r.stdout)

    def test_a_finding_with_no_marker_on_its_line_carries_no_hint(self):
        # The hint is keyed on the SPECIFIC finding line, not on "this file
        # happens to contain the marker somewhere" -- a real secret sitting
        # next to unrelated marker lines must not be talked out of looking
        # like one.
        copy = self.write(
            "mixed.sh",
            "# " + EXEMPT_MARKER + "\n" + CREDENTIAL + "\n",
        )
        r = self.run_gate(copy)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotIn("not recognised as the pattern-source file", r.stdout)

    def test_the_original_pattern_source_suppresses_those_same_findings(self):
        r = self.run_gate(LIB)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        match = re.search(r": (\d+) pattern-source lines exempted", r.stdout)
        self.assertIsNotNone(match, r.stdout)
        self.assertGreater(int(match.group(1)), 0)


# ---------------------------------------------------------------------------
# 5. Sweep mode over a repository.
# ---------------------------------------------------------------------------
class SweepTest(GateTestBase):
    def make_repo(self):
        repo = self.work / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=self.env())
        return repo

    def commit_all(self, repo):
        env = self.env(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@host.invalid",
                       GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@host.invalid")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
        subprocess.run(["git", "commit", "-qm", "x"], cwd=repo, check=True, env=env)

    def test_a_sweep_reports_the_number_of_scanned_files(self):
        repo = self.make_repo()
        (repo / "a.md").write_text(CLEAN_TEXT, encoding="utf-8")
        (repo / "b.md").write_text("more prose\n", encoding="utf-8")
        self.commit_all(repo)
        r = self.run_gate("--repo", repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("2 files", r.stdout)

    def test_a_sweep_finds_a_planted_secret_and_names_the_file_and_line(self):
        repo = self.make_repo()
        (repo / "a.md").write_text(CLEAN_TEXT, encoding="utf-8")
        (repo / "bad.md").write_text("ok\nleak " + HOME_PATH + "\n", encoding="utf-8")
        self.commit_all(repo)
        r = self.run_gate("--repo", repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn("bad.md:2:", r.stdout)

    def test_a_sweep_skips_untracked_files(self):
        repo = self.make_repo()
        (repo / "a.md").write_text(CLEAN_TEXT, encoding="utf-8")
        self.commit_all(repo)
        (repo / "scratch.md").write_text("leak " + HOME_PATH + "\n", encoding="utf-8")
        r = self.run_gate("--repo", repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_sweep_skips_binary_files(self):
        repo = self.make_repo()
        (repo / "a.md").write_text(CLEAN_TEXT, encoding="utf-8")
        (repo / "blob.bin").write_bytes(b"\x00\x01\x02" + HOME_PATH.encode() + b"\x00")
        self.commit_all(repo)
        r = self.run_gate("--repo", repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_sweep_says_how_much_of_the_scope_it_skipped(self):
        # "scanned 2 files" over a repo of five is a true statement about a
        # scope the reader cannot see. Since names are now checked on files
        # whose content is not, the summary has to say which is which.
        repo = self.make_repo()
        (repo / "a.md").write_text(CLEAN_TEXT, encoding="utf-8")
        (repo / "blob.bin").write_bytes(b"\x00\x01\x02binary\x00")
        self.commit_all(repo)
        r = self.run_gate("--repo", repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("1 binary", r.stdout)

    def test_a_sweep_with_no_binaries_does_not_mention_skipping(self):
        repo = self.make_repo()
        (repo / "a.md").write_text(CLEAN_TEXT, encoding="utf-8")
        self.commit_all(repo)
        r = self.run_gate("--repo", repo)
        self.assertNotIn("binary", r.stdout)

    def test_a_missing_file_argument_is_a_hard_error(self):
        r = self.run_gate(self.work / "does-not-exist.md")
        self.assertEqual(r.returncode, 2)

    # --- a run that checked nothing is not a clean run (KA-G-017) ---------
    def test_an_empty_scope_is_not_reported_as_a_pass(self):
        # Exit 0 here would announce "no findings" about a scope the gate never
        # looked at -- and a CI job would go green on it.
        repo = self.make_repo()
        r = self.run_gate("--repo", repo)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_an_empty_scope_says_why_rather_than_failing_mutely(self):
        repo = self.make_repo()
        r = self.run_gate("--repo", repo)
        self.assertIn("no files were scanned", r.stdout + r.stderr)

    def test_a_scope_of_only_binary_files_is_also_an_empty_scope(self):
        # Every candidate skipped is indistinguishable, from the outside, from
        # every candidate clean.
        repo = self.make_repo()
        (repo / "blob.bin").write_bytes(b"\x00\x01\x02" + HOME_PATH.encode() + b"\x00")
        self.commit_all(repo)
        r = self.run_gate("--repo", repo)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_an_empty_scope_fails_even_with_a_configured_deny_list(self):
        # A configured deny-list satisfies --require-denylist, which used to be
        # enough to reach exit 0 over zero files.
        self.write_config(denyNames=["Zorblatt"])
        repo = self.make_repo()
        r = self.run_gate("--require-denylist", "--repo", repo)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# 6. This repository must itself be clean — the point of the exercise.
# ---------------------------------------------------------------------------
class ShippedArtifactsAreCleanTest(GateTestBase):
    def test_every_tracked_non_binary_file_in_this_repo_passes_the_gate(self):
        r = self.run_gate("--repo", REPO_ROOT)
        self.assertEqual(
            r.returncode, 0,
            "shipped artifacts carry gate findings:\n" + r.stdout + r.stderr,
        )


# ---------------------------------------------------------------------------
# 7. Characterisation: the memory profile must not change.
# ---------------------------------------------------------------------------
class MemoryProfileUnchangedTest(GateTestBase):
    def setUp(self):
        super().setUp()
        self.write_config(ipAllowlist="")

    def test_a_clean_memory_file_is_still_clean(self):
        p = self.write("m.md", "# Rule\n\nA durable piece of knowledge.\n")
        r = self.run_memory_gate(p)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("gate: clean", r.stdout)

    def test_the_content_type_check_still_fires_for_memory(self):
        p = self.write("m.md", "## Next Steps\n\n- [ ] a work item\n")
        r = self.run_memory_gate(p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("content", self.categories(r))

    def test_the_personal_context_marker_still_fires_for_memory(self):
        p = self.write("m.md", "The user has red-green colour blindness.\n")
        r = self.run_memory_gate(p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("context", self.categories(r))

    def test_the_type_user_check_still_fires_for_memory(self):
        p = self.write("m.md", "type: user\n")
        r = self.run_memory_gate(p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("personal", self.categories(r))

    def test_a_secret_still_fires_for_memory(self):
        p = self.write("m.md", CREDENTIAL + "\n")
        r = self.run_memory_gate(p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("secret", self.categories(r))

    def test_the_ip_allowlist_config_is_still_honoured(self):
        # RFC 5737 TEST-NET-1. An address from a real internal range would be a
        # Constitution finding in this very file, and a developer whose own
        # allowlist happened to cover it would never see the sweep report it.
        self.write_config(ipAllowlist="^192\\.0\\.2\\.")
        p = self.write("m.md", "host " + ALLOWLISTED_IPV4 + " is the shared box\n")
        r = self.run_memory_gate(p)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_pattern_source_file_is_clean_under_the_memory_profile_too(self):
        # The memory profile runs two checks the artifact profile does not, and
        # both of them are spelled out in the library: the personal-context
        # marker appears in the profile table, and the work-item shapes appear in
        # the finding message itself. The exemption must cover those lines too,
        # or the file that defines the patterns fails its own gate.
        r = self.run_memory_gate(LIB)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_percent_encoded_credential_also_fires_on_the_promote_path(self):
        # Both blockers were in shared patterns, so both were also holes in the
        # path where memory leaves the machine. The artifact profile is the
        # cheaper place to notice them; promote is the more expensive place to
        # miss them.
        p = self.write("m.md", 'db = "' + PCT_ENCODED_CONNSTRING + '"\n')
        r = self.run_memory_gate(p)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("secret", self.categories(r))

    def test_a_json_quoted_credential_also_fires_on_the_promote_path(self):
        p = self.write("m.md", JSON_TOKEN + "\n")
        r = self.run_memory_gate(p)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("secret", self.categories(r))

    def test_a_placeholder_url_is_still_promotable(self):
        p = self.write("m.md", "clone via https://oauth2:${tok}@host/path\n")
        r = self.run_memory_gate(p)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_tab_bearing_deny_name_also_protects_the_promote_path(self):
        self.write_config(ipAllowlist="", denyNames=["Zorb\tlatt"])
        p = self.write("m.md", "The Zorb\tlatt rollout.\n")
        r = self.run_memory_gate(p)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("denylist", self.categories(r))

    def test_the_deny_list_also_protects_the_promote_path(self):
        self.write_config(denyNames=["Zorblatt"])
        p = self.write("m.md", "The Zorblatt rollout.\n")
        r = self.run_memory_gate(p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("denylist", self.categories(r))


# ---------------------------------------------------------------------------
# 8. Redaction is a property of the TOOL's output, not of its finding lines.
# ---------------------------------------------------------------------------
class EveryEmittedLineIsRedactedTest(GateTestBase):
    """A redaction that holds on most lines is not a redaction.

    The deny-list exists so a configured name never reaches an output, and a CI
    log is a shipped artifact like any other. Two lines bypassed the mask: the
    exemption-audit line, which printed the pattern-source file name verbatim on
    the same run where every finding above it redacted that identical string, and
    the hard-error path, which echoed the file name it could not find.
    """

    def test_the_exemption_audit_line_does_not_leak_a_configured_name(self):
        # "discipline" is a substring of the pattern-source file's own name, so
        # this run redacts that string in every finding line while the audit
        # line spells it out twice -- the run contradicting itself.
        self.write_config(denyNames=["discipline"])
        r = self.run_gate(LIB)
        self.assertNotIn(
            "discipline", (r.stdout + r.stderr).lower(),
            "a configured name reached the output:\n" + r.stdout + r.stderr,
        )

    def test_the_audit_line_still_says_how_many_lines_were_exempted(self):
        # Redacting must not cost the audit its information: the count and the
        # marker to grep for are what make the exemption visible rather than
        # silent.
        self.write_config(denyNames=["discipline"])
        r = self.run_gate(LIB)
        self.assertIn("pattern-source", r.stdout)
        self.assertIn("exempted", r.stdout)

    def test_the_file_not_found_error_does_not_leak_a_configured_name(self):
        # Reachable from the CI shape: the job passes a list of changed files
        # and one of them was deleted in the same push.
        self.write_config(denyNames=["Zorblatt"])
        r = self.run_gate(self.work / "Zorblatt-notes.md")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertNotIn("zorblatt", (r.stdout + r.stderr).lower())

    def test_the_file_not_found_error_still_names_the_problem(self):
        r = self.run_gate(self.work / "does-not-exist.md")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("does-not-exist.md", r.stderr)


# ---------------------------------------------------------------------------
# 9. The promote path must refuse the same broken configuration as the sweep.
# ---------------------------------------------------------------------------
class PromotePathConfigDefectTest(GateTestBase):
    """`memory-sync.sh` became a consumer of the shared library but ignored its
    configuration-defect signal. That is the worse half of the pair: the sweep
    reads artifacts that are already here, promote is the path on which memory
    leaves the machine, so a silently shortened deny-list there ships the name.
    """

    def test_an_unusable_deny_entry_is_refused_on_the_promote_path_too(self):
        self.write_config(denyNames=["Quuxcorp", "Zorb\nlatt"])
        p = self.write("m.md", MEMORY_CLEAN_TEXT)
        r = self.run_memory_gate(p)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_the_promote_side_rejection_names_the_entry_by_index_only(self):
        self.write_config(denyNames=["Quuxcorp", "Zorb\nlatt"])
        p = self.write("m.md", MEMORY_CLEAN_TEXT)
        r = self.run_memory_gate(p)
        self.assertIn("#2", r.stdout + r.stderr)
        self.assertNotIn("zorb", (r.stdout + r.stderr).lower())

    def test_a_blank_deny_entry_is_refused_on_the_promote_path_too(self):
        self.write_config(denyNames=["Quuxcorp", "   "])
        p = self.write("m.md", MEMORY_CLEAN_TEXT)
        r = self.run_memory_gate(p)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_both_entry_points_refuse_the_same_broken_configuration(self):
        # Measured side by side on one file and one config: the divergence was
        # artifact-gate exit 2 against `gate: clean` from memory-sync.
        self.write_config(denyNames=["Quuxcorp", "Zorb\nlatt"])
        p = self.write("m.md", MEMORY_CLEAN_TEXT)
        artifact = self.run_gate(p)
        memory = self.run_memory_gate(p)
        self.assertEqual(
            (artifact.returncode, memory.returncode), (2, 2),
            "artifact:\n" + artifact.stdout + artifact.stderr
            + "\nmemory:\n" + memory.stdout + memory.stderr,
        )

    def test_an_unconfigured_deny_list_is_reported_on_the_promote_path(self):
        # The library documents that saying so is the entry point's job, because
        # silence is what let the breach through. Promote said nothing.
        self.write_config(ipAllowlist="")
        p = self.write("m.md", MEMORY_CLEAN_TEXT)
        r = self.run_memory_gate(p)
        self.assertIn("NOT CONFIGURED", r.stdout + r.stderr)

    def test_reporting_an_unconfigured_deny_list_is_not_itself_a_failure(self):
        # Promote must stay usable without a personal deny-list; the notice is a
        # statement about scope, not a finding.
        self.write_config(ipAllowlist="")
        p = self.write("m.md", MEMORY_CLEAN_TEXT)
        r = self.run_memory_gate(p)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("gate: clean", r.stdout)


# ---------------------------------------------------------------------------
# 10. The exit-code contract is documented where the contract lives.
# ---------------------------------------------------------------------------
class UsageContractTest(GateTestBase):
    def test_the_help_text_states_why_require_denylist_exits_one(self):
        # 1 and 2 are both defensible for a missing deny-list. The point is that
        # the next reader must not have to re-derive the choice from the code.
        r = self.run_gate("--help")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("--require-denylist deliberately exits 1", r.stdout)
        # ... and says what it is being distinguished FROM, or the reader is
        # left re-deriving the sibling case from the code again.
        self.assertIn("not 2", r.stdout)

    def test_the_help_text_covers_the_whole_header_and_stops_at_the_code(self):
        # Regression guard, green before and after: the usage text is a slice of
        # this file's own header, so growing the header must not truncate it or
        # spill shell code into it.
        r = self.run_gate("--help")
        self.assertIn("Exit:", r.stdout)
        self.assertNotIn("set -euo pipefail", r.stdout)


# ---------------------------------------------------------------------------
# 11. A file whose bytes could not be read has not been verified.
# ---------------------------------------------------------------------------
class UnreadableFileTest(GateTestBase):
    """An unreadable file was counted as a binary skip, and a run of nothing but
    such files still exited 0. From the outside that is indistinguishable from a
    clean run -- the same failure shape as the empty scope (KA-G-017), one file
    at a time. The header already promised exit 2 for "unreadable input".
    """

    def setUp(self):
        super().setUp()
        if os.geteuid() == 0:
            self.skipTest("root reads every file regardless of mode")

    def unreadable(self, base, name="notes.md"):
        """A file that exists, has content, and cannot be opened.

        It is chmod-ed AFTER any git operation on purpose: `git add` cannot read
        mode-000 either, so locking it first would make the file untracked and
        the test would prove nothing about the sweep.
        """
        p = base / name
        p.write_text("leak " + HOME_PATH + "\n", encoding="utf-8")
        self.addCleanup(p.chmod, 0o600)
        return p

    def test_an_unreadable_file_is_a_hard_error_not_a_silent_skip(self):
        # Paired with a readable clean file on purpose. Alone, the unreadable
        # file already produced exit 2 -- but via the empty-scope rule, which
        # says nothing about it. One readable file next to it is enough to make
        # the scope non-empty and the run go green over bytes nobody read.
        clean = self.write("clean.md", CLEAN_TEXT)
        locked = self.unreadable(self.work)
        locked.chmod(0o000)
        r = self.run_gate(clean, locked)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_the_hard_error_says_the_file_could_not_be_read(self):
        # "no files were scanned" is a true sentence about the wrong subject.
        locked = self.unreadable(self.work)
        locked.chmod(0o000)
        r = self.run_gate(locked)
        self.assertIn("unreadable", (r.stdout + r.stderr).lower())

    def test_an_unreadable_tracked_file_does_not_let_a_sweep_pass(self):
        # The dangerous shape: a CI job goes green over a file it never opened.
        repo = self.work / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=self.env())
        (repo / "a.md").write_text(CLEAN_TEXT, encoding="utf-8")
        locked = self.unreadable(repo, name="locked.md")
        env = self.env(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@host.invalid",
                       GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@host.invalid")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
        subprocess.run(["git", "commit", "-qm", "x"], cwd=repo, check=True, env=env)
        locked.chmod(0o000)
        r = self.run_gate("--repo", repo)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# 9. templates/ci/artifact-gate.ci.sh (WI-0027) — the dormant CI template.
#    Unlike GATE and LIB, nothing else in this suite ever runs it: it is
#    shipped as a starting point for teams to copy into their own CI config,
#    not executed as part of this repository's own checks. These tests give
#    it its first execution: a syntax check plus a fixture-repo invocation
#    that proves it actually fails a dirty repo and passes a clean one.
# ---------------------------------------------------------------------------
class CiTemplateExecutionTest(GateTestBase):
    def make_fixture_repo(self):
        """A git repo carrying its own copy of the real gate.

        The template resolves `$REPO_ROOT/scripts/artifact-gate.sh` and that
        script in turn sources `scripts/lib/discipline_gate.sh` relative to
        its OWN location, not $REPO_ROOT -- so pointing REPO_ROOT at this
        suite's own checkout would not exercise the template's guard for "the
        gate is not installed here" at all. Copying the two real scripts into
        the fixture at the same relative paths lets REPO_ROOT drive a genuine,
        working gate invocation instead of a stub.
        """
        repo = self.work / "fixture-repo"
        (repo / "scripts" / "lib").mkdir(parents=True)
        gate_copy = repo / "scripts" / "artifact-gate.sh"
        shutil.copy2(GATE, gate_copy)
        gate_copy.chmod(gate_copy.stat().st_mode | 0o111)
        shutil.copy2(LIB, repo / "scripts" / "lib" / "discipline_gate.sh")
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=self.env())
        return repo

    def commit_all(self, repo):
        env = self.env(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@host.invalid",
                       GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@host.invalid")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
        subprocess.run(["git", "commit", "-qm", "x"], cwd=repo, check=True, env=env)

    def run_template(self, repo_root, template=CI_TEMPLATE, **extra_env):
        # REPO_ROOT is passed explicitly so the template never falls back to
        # `git rev-parse --show-toplevel` on this suite's own working tree.
        return subprocess.run(
            ["sh", str(template)],
            capture_output=True, text=True,
            env=self.env(REPO_ROOT=str(repo_root), **extra_env),
        )

    # --- the cheap floor: it must at least parse -----------------------------
    def test_the_template_is_syntactically_valid_posix_sh(self):
        # env=self.env() even though `sh -n` only parses and never executes:
        # every other subprocess in this class is HOME-sandboxed, and an
        # unsandboxed one here would go unnoticed if `-n` were ever dropped.
        r = subprocess.run(["sh", "-n", str(CI_TEMPLATE)],
                            capture_output=True, text=True, env=self.env())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    # --- the honest one: does it actually gate? -------------------------------
    def test_a_clean_fixture_repo_passes_through_the_template(self):
        fixture = self.make_fixture_repo()
        (fixture / "clean.md").write_text(CLEAN_TEXT, encoding="utf-8")
        self.commit_all(fixture)
        r = self.run_template(fixture)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_planted_finding_fails_through_the_template(self):
        fixture = self.make_fixture_repo()
        (fixture / "bad.md").write_text("leak " + HOME_PATH + "\n", encoding="utf-8")
        self.commit_all(fixture)
        r = self.run_template(fixture)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("bad.md", r.stdout + r.stderr)

    # --- the guard nobody has ever tripped ------------------------------------
    def test_a_missing_gate_installation_exits_2_with_its_own_message(self):
        not_ccpr = self.work / "not-a-ccpr-repo"
        not_ccpr.mkdir()
        r = self.run_template(not_ccpr)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("not found", r.stdout + r.stderr)

    # --- the branch nobody has ever tripped -----------------------------------
    def test_require_denylist_1_reaches_the_gate_as_the_require_denylist_flag(self):
        # An unconfigured deny-list only fails the run when --require-denylist
        # reaches the underlying gate -- so toggling REQUIRE_DENYLIST over the
        # same clean fixture, with no config written, is what makes the flag's
        # passthrough observable rather than merely read.
        fixture = self.make_fixture_repo()
        (fixture / "clean.md").write_text(CLEAN_TEXT, encoding="utf-8")
        self.commit_all(fixture)

        default_run = self.run_template(fixture)
        self.assertEqual(default_run.returncode, 0,
                          default_run.stdout + default_run.stderr)

        required_run = self.run_template(fixture, REQUIRE_DENYLIST="1")
        self.assertEqual(required_run.returncode, 1,
                          required_run.stdout + required_run.stderr)


# ---------------------------------------------------------------------------
# 12. Symlinks (WI-0015) — the gate's subject is the link's own NAME, never
#     its target. install.sh ships a symlink with `cp -R`, which preserves it
#     AS a link; the target's bytes never travel, so reading through it would
#     scan and report content that does not ship. The link's own filename is
#     deny-checked exactly like any other path, dangling or not.
# ---------------------------------------------------------------------------
class SymlinkTest(GateTestBase):
    def make_repo(self):
        repo = self.work / "symrepo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=self.env())
        return repo

    def commit_all(self, repo):
        env = self.env(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@host.invalid",
                       GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@host.invalid")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
        subprocess.run(["git", "commit", "-qm", "x"], cwd=repo, check=True, env=env)

    def test_a_dangling_symlink_whose_name_carries_a_deny_name_is_reported_and_counted(self):
        # The silent-scope-loss defect: a dangling link's own filename was
        # never deny-checked at all, so a tenant name sitting right there in
        # the tracked path went unreported.
        self.write_config(denyNames=["Zorblatt"])
        repo = self.make_repo()
        (repo / "clean.md").write_text(CLEAN_TEXT, encoding="utf-8")
        link = repo / "zorblatt-link.md"
        link.symlink_to(repo / "does-not-exist.md")
        self.commit_all(repo)
        r = self.run_gate("--repo", repo)
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 1, out)
        self.assertIn("denylist", self.categories(r))
        self.assertNotIn("zorblatt", out.lower())
        self.assertIn("1 symlink", out)

    def test_a_dangling_symlink_with_a_harmless_name_is_counted_not_a_finding(self):
        # Counted in its own summary line so the run cannot silently shrink,
        # but not reported: a harmless filename is not a finding. The other
        # tracked, regular file is unaffected -- still scanned normally.
        repo = self.make_repo()
        (repo / "clean.md").write_text(CLEAN_TEXT, encoding="utf-8")
        link = repo / "harmless-link.md"
        link.symlink_to(repo / "does-not-exist.md")
        self.commit_all(repo)
        r = self.run_gate("--repo", repo)
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, out)
        self.assertEqual(self.categories(r), set())
        self.assertIn("1 symlink", out)
        self.assertIn("scanned 1 files", out)

    def test_a_link_resolving_in_repo_scans_its_target_exactly_once(self):
        # Following the link would scan the target's bytes twice: once via
        # its own tracked entry, once again through the link. Not following
        # it must leave exactly one finding, from the real file.
        repo = self.make_repo()
        target = repo / "target.md"
        target.write_text("leak " + HOME_PATH + "\n", encoding="utf-8")
        link = repo / "alias.md"
        link.symlink_to(target)
        self.commit_all(repo)
        r = self.run_gate("--repo", repo)
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 1, out)
        personal_findings = [ln for ln in out.splitlines() if "[personal]" in ln]
        self.assertEqual(len(personal_findings), 1, out)
        self.assertIn("scanned 1 files", out)
        self.assertIn("1 symlink", out)

    def test_a_link_resolving_out_of_repo_never_ships_the_targets_content(self):
        # The accepted cost: a target outside the repo does not ship, so its
        # content is never scanned or reported -- even though it leaks.
        outside = Path(tempfile.mkdtemp(prefix="ccpr-artifact-gate-outside-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        target = outside / "secret.md"
        target.write_text("leak " + HOME_PATH + "\n", encoding="utf-8")
        repo = self.make_repo()
        (repo / "clean.md").write_text(CLEAN_TEXT, encoding="utf-8")
        link = repo / "outside-link.md"
        link.symlink_to(target)
        self.commit_all(repo)
        r = self.run_gate("--repo", repo)
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, out)
        self.assertEqual(self.categories(r), set())
        self.assertIn("1 symlink", out)
        self.assertIn("scanned 1 files", out)


# ---------------------------------------------------------------------------
# 8. WI-0051 — a crashing grep must abort the run, never read as "no findings".
#
# Before this item, every check in gate_scan_file (and gate_load_config's own
# deny-list parsing) routed its grep through a trailing `|| true`, which
# folded "no match" (grep exit 1, the ordinary empty-category case) and
# "grep did not run to completion" (exit >=2 -- a crash, a bad pattern, a
# locale/encoding fault on malformed multi-byte input) into the identical
# empty result. A fixture whose only finding lived behind the crashing check
# came back "0 findings", exit 0.
#
# Each case below injects a fake `grep` ahead of the real one on PATH that
# crashes (exit 2) only when one of ITS OWN arguments contains a marker
# string unique to the ONE GATE_RE_* pattern under test (never a whole
# pattern -- these are checked for cross-pattern collisions in
# CrashMarkersAreUniqueToOnePatternTest below) -- every OTHER check in the
# same run still calls the real grep, so a fixture carrying only the
# crash-triggering content proves the specific call site, not a general
# breakage.
# ---------------------------------------------------------------------------
class GrepCrashAbortsInsteadOfReadingAsCleanTest(GateTestBase):
    def grep_stub_dir(self, crash_on):
        stub_dir = Path(tempfile.mkdtemp(prefix="ccpr-fake-grep-"))
        self.addCleanup(shutil.rmtree, stub_dir, ignore_errors=True)
        stub = stub_dir / "grep"
        stub.write_text(
            "#!/bin/sh\n"
            f"marker={shlex.quote(crash_on)}\n"
            'for a in "$@"; do\n'
            '  case "$a" in\n'
            '    *"$marker"*) echo "fake-grep: simulated crash" >&2; exit 2 ;;\n'
            "  esac\n"
            "done\n"
            'exec /usr/bin/grep "$@"\n'
        )
        stub.chmod(0o755)
        return stub_dir

    def grep_stub(self, crash_on):
        return f"{self.grep_stub_dir(crash_on)}:/usr/bin:/bin:/usr/sbin:/sbin"

    def path_without_python3(self, stub_dir):
        """A PATH containing the grep stub plus every /usr/bin, /bin,
        /usr/sbin and /sbin entry EXCEPT python3 -- for the "no python3 at
        all" fallback branch, which cannot be reached by breaking python3
        (PYTHONHOME=/nonexistent still leaves `command -v python3` true)."""
        no_python = Path(tempfile.mkdtemp(prefix="ccpr-no-python3-"))
        self.addCleanup(shutil.rmtree, no_python, ignore_errors=True)
        for d in ("/usr/bin", "/bin", "/usr/sbin", "/sbin"):
            src = Path(d)
            if not src.is_dir():
                continue
            for entry in src.iterdir():
                if entry.name.startswith("python3"):
                    continue
                target = no_python / entry.name
                if target.exists():
                    continue
                try:
                    target.symlink_to(entry)
                except OSError:
                    pass
        return f"{stub_dir}:{no_python}"

    def run_memory_gate_with_env(self, path, **extra_env):
        return subprocess.run(
            ["bash", str(MEMORY_SYNC), "gate", str(path)],
            capture_output=True, text=True, env=self.env(**extra_env),
        )

    def assert_artifact_check_crash_aborts(self, path, marker, label, deny_names=None):
        extra = {"PATH": self.grep_stub(marker)}
        if deny_names is not None:
            extra["CCPR_GATE_DENY_NAMES"] = deny_names
        r = self.run_gate(path, **extra)
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 2, out)
        self.assertIn(label, out)
        self.assertIn("exited 2", out)
        self.assertNotIn("0 findings", out)

    def assert_memory_check_crash_aborts(self, path, marker, label, **extra_env):
        r = self.run_memory_gate_with_env(path, PATH=self.grep_stub(marker), **extra_env)
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 2, out)
        self.assertIn(label, out)
        self.assertIn("exited 2", out)

    # --- secrets, single-stage (the plain _gate_hits shape) ------------------
    def test_secret_vendor_token_check_crash_aborts(self):
        p = self.write("vendor.md", VENDOR_TOKEN + "\n")
        self.assert_artifact_check_crash_aborts(p, "gh[pousr]_", "secret/vendor-token")

    def test_secret_token_blob_check_crash_aborts(self):
        p = self.write("blob.md", JWT + "\n")
        self.assert_artifact_check_crash_aborts(p, "eyJ[A-Za-z0-9_-]{10,}", "secret/token-blob")

    def test_secret_private_key_check_crash_aborts(self):
        p = self.write("privkey.md", PRIVATE_KEY + "\n")
        self.assert_artifact_check_crash_aborts(p, "PRIVATE KEY-----", "secret/private-key")

    # --- secrets, two-stage through _gate_hits (extract, then a placeholder
    # filter -- WI-0035's shape) ----------------------------------------------
    def test_secret_credential_assignment_extract_crash_aborts(self):
        p = self.write("kv.md", CREDENTIAL + "\n")
        self.assert_artifact_check_crash_aborts(p, "passwd|bearer", "secret/credential-assignment extract")

    def test_secret_credential_assignment_placeholder_filter_crash_aborts(self):
        p = self.write("kv.md", CREDENTIAL + "\n")
        self.assert_artifact_check_crash_aborts(
            p, "REPLACE|CHANGEME", "secret/credential-assignment placeholder-filter"
        )

    def test_secret_bearer_token_extract_crash_aborts(self):
        p = self.write("bearer.md", BEARER_TOKEN + "\n")
        self.assert_artifact_check_crash_aborts(p, "bearer[[:space:]]+", "secret/bearer-token extract")

    def test_secret_bearer_token_placeholder_filter_crash_aborts(self):
        p = self.write("bearer.md", BEARER_TOKEN + "\n")
        self.assert_artifact_check_crash_aborts(
            p, "REPLACE|CHANGEME", "secret/bearer-token placeholder-filter"
        )

    # --- secrets, two-stage DIRECT (bypassed _gate_hits entirely before this
    # fix -- the connection-string/placeholder pair) -------------------------
    def test_secret_connection_string_extract_crash_aborts(self):
        p = self.write("conn.md", CONNECTION_STRING + "\n")
        self.assert_artifact_check_crash_aborts(p, "[^/[:space:]@]+@", "secret/connection-string extract")

    def test_secret_connection_string_placeholder_filter_crash_aborts(self):
        p = self.write("conn.md", CONNECTION_STRING + "\n")
        self.assert_artifact_check_crash_aborts(
            p, r"\{\{[^}]*\}\}", "secret/connection-string placeholder-filter"
        )

    # --- personal --------------------------------------------------------------
    def test_personal_session_home_check_crash_aborts(self):
        p = self.write("home.md", HOME_PATH + "\n")
        self.assert_artifact_check_crash_aborts(p, r"claude\.ai/code/session", "personal/session-home")

    def test_personal_email_extract_crash_aborts(self):
        p = self.write("email.md", REAL_EMAIL + "\n")
        self.assert_artifact_check_crash_aborts(p, "[[:alnum:]]([[:alnum:].-]", "personal/email extract")

    def test_personal_email_reserved_domain_filter_crash_aborts(self):
        p = self.write("email.md", REAL_EMAIL + "\n")
        self.assert_artifact_check_crash_aborts(
            p, r"example\.(com|net|org)", "personal/email reserved-domain-filter"
        )

    # --- network -----------------------------------------------------------
    def test_network_ipv4_check_crash_aborts(self):
        p = self.write("ip.md", IPV4 + "\n")
        self.assert_artifact_check_crash_aborts(p, r"{1,3}\.){3}", "network/ipv4")

    # --- deny-list (direct grep -nFi, the ASCII branch) ----------------------
    def test_denylist_name_check_crash_aborts(self):
        p = self.write("tenant.md", "mentions Zorblatt in prose\n")
        self.assert_artifact_check_crash_aborts(p, "Zorblatt", "denylist/name", deny_names="Zorblatt")

    def test_denylist_unicode_fallback_check_crash_aborts(self):
        # WI-0049 shape: python3 IS present but ITS OWN comparison crashes
        # (PYTHONHOME=/nonexistent breaks it without removing it from PATH),
        # so gate_scan_file falls back to a plain ASCII grep -nFi -- which is
        # a SEPARATE call site this item's fix must cover too, not just the
        # unicode/direct-ASCII paths above.
        name = "Quüxcorp"  # non-ASCII on purpose, forces the escalation
        p = self.write("tenant.md", f"mentions {name} in prose\n")
        r = self.run_gate(
            p, CCPR_GATE_DENY_NAMES=name, PYTHONHOME="/nonexistent",
            PATH=self.grep_stub(name),
        )
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 2, out)
        self.assertIn("denylist/name #1 (unicode-fallback)", out)
        self.assertIn("exited 2", out)

    def test_denylist_no_python3_fallback_check_crash_aborts(self):
        # The OTHER fallback branch: no python3 anywhere on PATH, so
        # gate_scan_file goes straight to the ASCII grep without ever trying
        # the unicode matcher -- it must also abort rather than read as
        # clean if IT crashes.
        name = "Quüxcorp"
        p = self.write("tenant.md", f"mentions {name} in prose\n")
        path_no_python3 = self.path_without_python3(self.grep_stub_dir(name))
        r = self.run_gate(p, CCPR_GATE_DENY_NAMES=name, PATH=path_no_python3)
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 2, out)
        self.assertIn("denylist/name #1 (ascii-only, no python3)", out)
        self.assertIn("exited 2", out)

    # --- memory-only categories (context, type: user, work-item markers) ----
    def test_context_marker_check_crash_aborts(self):
        # memory-sync.sh requires its config file to exist for every verb,
        # even "gate" -- gate_load_config itself does not need it (see the
        # config-parsing test below, which crashes before this check runs).
        self.write_config()
        p = self.write("ctx.md", "a note about Accessibility-Familien testing\n")
        self.assert_memory_check_crash_aborts(p, "Accessibility-Familien", "context/marker")

    def test_type_user_check_crash_aborts(self):
        self.write_config()
        p = self.write("tu.md", "type: user\nsome body\n")
        self.assert_memory_check_crash_aborts(p, "type:[[:space:]]*user", "personal/type-user")

    def test_content_marker_check_crash_aborts(self):
        self.write_config()
        p = self.write("wi.md", "# Next Steps\nTODO: something\n")
        self.assert_memory_check_crash_aborts(p, "Next Steps|N", "content/marker")

    # --- config parsing (gate_load_config, not gate_scan_file -- runs ONCE,
    # before any file is scanned; a crash here used to silently empty the
    # WHOLE run's deny-list, not just one file's worth of one category) ------
    def test_config_deny_names_blank_line_filter_crash_aborts(self):
        p = self.write("clean.md", CLEAN_TEXT)
        self.assert_memory_check_crash_aborts(
            p, "^$", "config/CCPR_GATE_DENY_NAMES blank-line-filter",
            CCPR_GATE_DENY_NAMES="some-tenant,other-tenant",
        )

    # --- companion pin: the stub harness itself must be inert when its
    # marker never matches -- otherwise the aborts above could just be an
    # artifact of shelling out through a stub, not of the crash. -------------
    def test_a_healthy_grep_is_unaffected_by_the_stub_harness(self):
        p = self.write("clean.md", CLEAN_TEXT)
        path = self.grep_stub("this-marker-never-occurs-anywhere")
        r = self.run_gate(p, PATH=path)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class CrashMarkersAreUniqueToOnePatternTest(unittest.TestCase):
    """Each marker GrepCrashAbortsInsteadOfReadingAsCleanTest uses to target
    one call site's grep must not also occur in any OTHER GATE_RE_* pattern
    this file defines -- otherwise a test believed to isolate one check would
    silently also be crashing others, and a failure could not be attributed."""

    # A list of (marker, pattern_name) pairs, not a dict literal: a dict
    # entry pairing a keyword-shaped marker with a long quoted value is
    # ITSELF shaped like GATE_RE_SECRET_KV's own credential-assignment
    # pattern (a keyword, an optional quote, a colon, a 16+ char value), and
    # the shipped-artifacts sweep correctly fires on this file's own source
    # over that shape -- so the pairs travel as tuples instead.
    MARKERS = [
        ("gh[pousr]_", "GATE_RE_SECRET_VENDOR"),
        ("eyJ[A-Za-z0-9_-]{10,}", "GATE_RE_SECRET_BLOB"),
        ("PRIVATE KEY-----", "GATE_RE_PRIVATE_KEY"),
        ("passwd|bearer", "GATE_RE_SECRET_KV"),
        ("REPLACE|CHANGEME", "GATE_RE_SECRET_PLACEHOLDER_WORD"),
        ("bearer[[:space:]]+", "GATE_RE_SECRET_BEARER"),
        ("[^/[:space:]@]+@", "GATE_RE_CONNSTRING"),
        (r"\{\{[^}]*\}\}", "GATE_RE_PLACEHOLDER"),
        (r"claude\.ai/code/session", "GATE_RE_PERSONAL"),
        ("[[:alnum:]]([[:alnum:].-]", "GATE_RE_EMAIL"),
        (r"example\.(com|net|org)", "GATE_RE_EMAIL_RESERVED"),
        (r"{1,3}\.){3}", "GATE_RE_IPV4"),
        ("Accessibility-Familien", "GATE_RE_CONTEXT"),
        ("type:[[:space:]]*user", "GATE_RE_TYPE_USER"),
        ("Next Steps|N", "GATE_RE_CONTENT"),
    ]

    # The RUNTIME value, not the static source line: GATE_RE_PLACEHOLDER is
    # built at source-time from GATE_RE_PLACEHOLDER_SLOT
    # ('...${GATE_RE_PLACEHOLDER_SLOT}...' as shell text), so its own source
    # line never literally contains the mustache-slot marker the way every
    # other pattern's does -- only the expanded shell variable does.
    ALL_PATTERN_NAMES = [
        "GATE_RE_SECRET_KV", "GATE_RE_SECRET_BEARER", "GATE_RE_SECRET_PLACEHOLDER_WORD",
        "GATE_RE_SECRET_VENDOR", "GATE_RE_SECRET_BLOB", "GATE_RE_PRIVATE_KEY",
        "GATE_RE_CONNSTRING", "GATE_RE_PLACEHOLDER", "GATE_RE_PERSONAL",
        "GATE_RE_EMAIL", "GATE_RE_EMAIL_RESERVED", "GATE_RE_TYPE_USER",
        "GATE_RE_IPV4", "GATE_RE_CONTENT", "GATE_RE_CONTEXT",
    ]

    @classmethod
    def setUpClass(cls):
        script = f"source {shlex.quote(str(LIB))}; " + "; ".join(
            f'printf "%s\\x1e" "${n}"' for n in cls.ALL_PATTERN_NAMES
        )
        r = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        values = r.stdout.split("\x1e")[:-1]
        assert len(values) == len(cls.ALL_PATTERN_NAMES), (
            f"expected {len(cls.ALL_PATTERN_NAMES)} pattern values, got {len(values)}"
        )
        cls.pattern_lines = dict(zip(cls.ALL_PATTERN_NAMES, values))

    def test_every_marker_is_present_in_its_own_pattern(self):
        for marker, pattern_name in self.MARKERS:
            with self.subTest(pattern=pattern_name):
                self.assertIn(pattern_name, self.pattern_lines,
                               f"{pattern_name} not found as a gate-pattern-source line")
                self.assertIn(marker, self.pattern_lines[pattern_name])

    def test_no_marker_occurs_in_a_different_pattern(self):
        for marker, owner in self.MARKERS:
            with self.subTest(marker=marker):
                collisions = [
                    name for name, text in self.pattern_lines.items()
                    if name != owner and marker in text
                ]
                self.assertEqual(collisions, [],
                                  f"marker {marker!r} for {owner} also occurs in {collisions}")


if __name__ == "__main__":
    unittest.main()
