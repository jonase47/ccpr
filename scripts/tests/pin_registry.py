r"""pin_registry.py -- WI-0133 T1: the shared vocabulary for ADR-0012 pins.

Deliberately NOT named `test_*`: `unittest discover` must not collect it. It
sits directly under `scripts/tests/` rather than in a subpackage so that it
stays inside test_absence_only_assertions.py's existing `TESTS_DIR.glob("*.py")`
scan -- a helper in a new subpackage would be a new blind spot in the very
corpus this round exists to enumerate.

Three things live here:

* `PIN_GROUPS` + `MARKER_RE` -- the marker vocabulary a pin uses to name
  itself at its own site, per ADR-0012 obligation 1.
* `find_candidates` -- the AST-derived population of assertions that LOOK like
  pins, so a pin that never named itself can still be found and reported.
* `assert_set_matches` -- the house set-comparison idiom, generalised.

## The marker

    # pin: <group> <id>

`<group>` must be a key of `PIN_GROUPS`; `<id>` is a short stable slug. The
shape is copied from test_external_tool_exit_status.py:229's
`# exit-status: exempt <reason>` and its `EXEMPTION_REASONS` registry (:234).
Copying rather than inventing keeps one marker dialect in this corpus instead
of two.

One of that precedent's two guards is carried over and one is not, on purpose.
"Every marker names a registered group" IS enforced
(`PinMarkerInventoryTest.test_every_marker_names_a_registered_group`). "Every
registered group is used" is NOT: `PIN_GROUPS` is a vocabulary declared ahead
of the classification work, so `derived` and `anchor` legitimately have no
marker yet while T1 can only write two sites. Enforcing it today would mean
either deleting groups the later tranches need or planting markers to satisfy a
test, and both are worse than the gap. It becomes enforceable once PENDING is
empty; the test that would carry it belongs to the tranche that empties it.

## assert_set_matches

Lifted verbatim in behaviour from test_bsd_gnu_portability.py:1888-1901 and
:1967-1982, which both spell out the same message inline. A count comparison
cannot distinguish "one added" from "one added, one gone" (ADR-0012, obligation
2); a set comparison names both directions in the failure message, which is
where a bump's set proof should come from.
"""

import ast
import re
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# The marker vocabulary
# ---------------------------------------------------------------------------

PIN_GROUPS = {
    "derived": (
        "The value follows from a source this repository holds; it is "
        "generated, not maintained. The pin exists so that regenerating it "
        "is a deliberate act with a recorded reason rather than a silent "
        "edit."
    ),
    "floor": (
        "A lower bound. It protects against one thing only -- a scanner "
        "going blind (an empty or truncated scope reported as a pass) -- and "
        "is silent while the subject grows. Admissible ONLY where the same "
        "subject also carries a `set` pin, because a floor structurally "
        "cannot see a swap: one entry out, one entry in, count unchanged."
    ),
    "set": (
        "A real membership guard. The pinned value is the collection itself, "
        "so a swap changes the assertion and the failure message names what "
        "arrived and what left. This is the shape ADR-0012 obligation 2 asks "
        "a bump to be proven in."
    ),
    "anchor": (
        "A historical anchor -- a pinned commit SHA. It goes red when the "
        "history it names becomes unreachable, NOT when the working tree "
        "drifts; that difference is the whole point of anchoring to a commit "
        "rather than to the current state."
    ),
}

MARKER_RE = re.compile(r"#\s*pin:\s*([A-Za-z0-9_-]+)\s+([A-Za-z0-9_-]+)")


class Marker:
    """A `# pin:` marker found in a source file."""

    __slots__ = ("rel", "lineno", "group", "pin_id")

    def __init__(self, rel, lineno, group, pin_id):
        self.rel = rel
        self.lineno = lineno
        self.group = group
        self.pin_id = pin_id

    def key(self):
        """Line-free identity -- see find_candidates' docstring."""
        return (self.rel, self.group, self.pin_id)

    def __repr__(self):
        return "Marker{}".format((self.rel, self.lineno, self.group, self.pin_id))


class PinCandidate:
    """An assertion shaped like a pin, identified WITHOUT a line number.

    A line-bearing identity turns every insertion above a site into one removal
    plus one addition; the same change measured both ways gave 7 additions and
    4 removals line-bearing versus 3 and 0 line-free (recorded in
    test_external_tool_exit_status.py:1173-1178). `lineno`/`end_lineno` are
    kept for matching a marker to the method that carries it, and are never
    part of `key()`.
    """

    __slots__ = ("rel", "class_name", "method_name", "lineno", "end_lineno",
                 "assert_linenos")

    def __init__(self, rel, class_name, method_name, lineno, end_lineno,
                 assert_linenos):
        self.rel = rel
        self.class_name = class_name
        self.method_name = method_name
        self.lineno = lineno
        self.end_lineno = end_lineno
        self.assert_linenos = tuple(assert_linenos)

    def key(self):
        return (self.rel, self.class_name, self.method_name)

    def __repr__(self):
        return "PinCandidate{}".format(self.key())


# ---------------------------------------------------------------------------
# assert_set_matches -- the house idiom, generalised
# ---------------------------------------------------------------------------

def assert_set_matches(testcase, expected, actual, subject):
    """Set equality with a two-directional failure message.

    Generalises the message spelled out inline at
    test_bsd_gnu_portability.py:1888-1901 (`KnownFindingsMatchTheCurrentScan
    Test`) and :1967-1982 (`ExemptedSitesArePinnedTest`). `subject` names what
    drifted, so one helper can serve several registers without the message
    going vague.
    """
    expected = set(expected)
    actual = set(actual)
    testcase.assertEqual(
        expected, actual,
        "{} drifted from its recorded baseline.\n  new:  {}\n  gone: {}".format(
            subject, sorted(actual - expected), sorted(expected - actual)),
    )


# ---------------------------------------------------------------------------
# Marker discovery
# ---------------------------------------------------------------------------

def find_markers(path, rel=None):
    """Every `# pin:` marker in one file, with its line, group and id."""
    rel = rel or path.name
    out = []
    text = path.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.split("\n"), start=1):
        m = MARKER_RE.search(line)
        if m:
            out.append(Marker(rel, lineno, m.group(1), m.group(2)))
    return out


def floors_without_a_set(markers):
    """Every `floor` marker whose subject carries no `set` marker.

    Makes `PIN_GROUPS["floor"]`'s admissibility sentence enforceable: a floor
    is a lower bound and structurally cannot see a SWAP (one entry out, one
    entry in, count unchanged), so on its own it is not a membership guard.
    Until WI-0133 T2 that rule was prose in a dict value -- a stated obligation
    with no mechanism, the same shape ADR-0012 obligation 1 had before T1.

    THE RULE IS ASYMMETRIC ON PURPOSE, AND THE ASYMMETRY IS A DECISION
    (WI-0133 T2, PO). A `floor` requires a `set`. A `set` does NOT require a
    `floor`: most membership guards need no lower bound, and demanding one
    would force a coupling nobody asked for onto every set pin in the corpus.
    Do not "complete" this into a symmetric check -- that is a scope change,
    not a tidy-up, and
    `FloorRequiresASetTest.test_a_set_without_a_floor_is_silent` fails if it
    happens.

    The subject is (file, id), not the bare id. Pin ids are short slugs and
    nothing enforces uniqueness across the corpus, so a bare-id match would let
    an unrelated pin in another module satisfy the rule by coincidence.

    Returns a sorted list of (rel, lineno, pin_id) -- the line is carried for
    the failure message only, never for identity.
    """
    subjects_with_a_set = {(m.rel, m.pin_id) for m in markers if m.group == "set"}
    return sorted((m.rel, m.lineno, m.pin_id) for m in markers
                  if m.group == "floor"
                  and (m.rel, m.pin_id) not in subjects_with_a_set)


# ---------------------------------------------------------------------------
# Candidate discovery
# ---------------------------------------------------------------------------

# Equality-family assertions only. `assertNotEqual` is deliberately absent: a
# negative equality cannot store a derived value, and including it would report
# every red-proof in the corpus (e.g. test_conformance_run.py:1921) as a pin.
EQUALITY_ASSERTS = frozenset({
    "assertEqual", "assertCountEqual", "assertSetEqual", "assertListEqual",
    "assertDictEqual", "assertTupleEqual",
    "assertGreaterEqual", "assertLessEqual", "assertGreater", "assertLess",
})

# `set()`, `dict()`, ... with no arguments are empty-collection literals that
# ast.literal_eval refuses; they appear on the declared side of registry-drift
# assertions (`assertEqual(set(), new)`).
EMPTY_COLLECTION_BUILTINS = frozenset({"set", "frozenset", "dict", "list", "tuple"})

# Standard-library imports can never make an expression repository-derived.
# Anything else imported at module level can (a sibling test module, the
# shipped script loaded as a module, a `lib/` helper), so the default is to
# treat an import as repo-derived and subtract the stdlib rather than to
# enumerate what counts.
STDLIB_IMPORT_NAMES = frozenset({
    "ast", "base64", "collections", "contextlib", "copy", "csv", "datetime",
    "difflib", "errno", "fnmatch", "functools", "glob", "gzip", "hashlib",
    "importlib", "io", "itertools", "json", "math", "os", "pathlib", "platform",
    "pty", "queue", "random", "re", "select", "shlex", "shutil", "signal",
    "socket", "sqlite3", "stat", "string", "struct", "subprocess", "sys",
    "tempfile", "textwrap", "threading", "time", "traceback", "types",
    "typing", "unittest", "urllib", "uuid", "warnings", "zipfile",
    # Names imported FROM the stdlib that are used bare.
    "Path", "patch", "mock", "dataclass", "namedtuple", "contextmanager",
    "defaultdict", "OrderedDict", "suppress", "redirect_stdout",
    "redirect_stderr", "StringIO", "BytesIO", "TestCase", "SkipTest",
})


def _literal_shape(node):
    """(is_literal, is_collection, is_nonzero_scalar) for an AST expression."""
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in EMPTY_COLLECTION_BUILTINS and not node.keywords):
        # `set()`/`dict()` -- an empty collection literal ast.literal_eval
        # refuses. `frozenset({...})`/`tuple([...])` -- a literal collection
        # behind a constructor, the shape this repository writes its registries
        # in (test_bsd_gnu_portability.py's EXEMPTED_SITES, this module's own
        # PIN_GROUPS consumers).
        if not node.args:
            return True, True, False
        if len(node.args) == 1:
            inner_literal, inner_collection, _ = _literal_shape(node.args[0])
            if inner_literal and inner_collection:
                return True, True, False
        return False, False, False
    try:
        value = ast.literal_eval(node)
    except Exception:
        return False, False, False
    if isinstance(value, (list, tuple, set, dict, frozenset)):
        return True, True, False
    if isinstance(value, bool) or value is None:
        return True, False, False
    if isinstance(value, (int, float)):
        # 0 carries no derived information: "no findings" is a claim about the
        # present, not a stored measurement that ages.
        return True, False, value != 0
    if isinstance(value, str):
        return True, False, bool(value)
    return True, False, False


def _is_nonempty_collection_literal(node):
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in EMPTY_COLLECTION_BUILTINS
            and len(node.args) == 1):
        return _is_nonempty_collection_literal(node.args[0])
    try:
        return len(ast.literal_eval(node)) > 0
    except Exception:
        return False


def _bound_names(target):
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        out = []
        for element in target.elts:
            out.extend(_bound_names(element))
        return out
    return []


def _names_used(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _module_scope(tree):
    """(repo_derived_names, declared_constant_names) at module level.

    `declared` = bound to a literal. An EMPTY collection literal still counts:
    `KNOWN_FINDINGS = set()` (test_bsd_gnu_portability.py:1065) is a declared
    registry whose current content happens to be nothing -- the declaration is
    the name, not the size.

    `repo_derived` = transitively reachable from `__file__` or from a non-stdlib
    import. Computed to a fixpoint over module-level assignments and function
    definitions.
    """
    assignments = {}
    functions = {}
    imported = set()
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                for name in _bound_names(target):
                    assignments[name] = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            for name in _bound_names(stmt.target):
                assignments[name] = stmt.value
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[stmt.name] = stmt
        elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
            for alias in stmt.names:
                imported.add(alias.asname or alias.name.split(".")[0])

    declared = set()
    for name, value in assignments.items():
        is_literal, is_collection, is_nonzero_scalar = _literal_shape(value)
        if is_literal and (is_collection or is_nonzero_scalar):
            declared.add(name)

    repo = {name for name in imported if name not in STDLIB_IMPORT_NAMES}
    changed = True
    while changed:
        changed = False
        for name, value in assignments.items():
            if name in repo:
                continue
            used = _names_used(value)
            if "__file__" in used or (used & repo):
                repo.add(name)
                changed = True
        for name, function in functions.items():
            if name in repo:
                continue
            used = _names_used(function)
            if "__file__" in used or (used & repo):
                repo.add(name)
                changed = True
    return repo - declared, declared


def _class_attribute_roots(class_def, repo):
    """Class-body names that are NOT fixtures: (declared_literals, repo_derived).

    Two shapes, both reached through `self` and neither built in `setUp`:

    * a literal -- `self.INJECTIONS` (test_check_all.py:1197) is a declared
      constant, `self.tmpdir` is a fixture. Without this distinction the
      `self`-taint rule below drops NoteColumnQuantityRedProofTest, a real pin
      against the shipped baseline.
    * a REPO-DERIVED expression -- `FIXTURE = FIXTURES_DIR / "...txt"`
      (test_absence_only_assertions.py:754) is a checked-in file, so a pin
      measured through it ages with the repository exactly as one measured
      through a module-level constant does. The same `repo` fixpoint that
      classifies module-level names decides this, rather than a second rule.
      Found by code review after the first version dropped
      ParentStateDiscriminationTest, a real pin, without reporting it as a gap.
    """
    literals = set()
    repo_derived = set()
    for stmt in class_def.body:
        if not isinstance(stmt, ast.Assign):
            continue
        is_literal, is_collection, is_nonzero_scalar = _literal_shape(stmt.value)
        names = _bound_names_of_targets(stmt.targets)
        if is_literal and (is_collection or is_nonzero_scalar):
            literals.update(names)
            continue
        used = _names_used(stmt.value)
        if used and used <= repo:
            repo_derived.update(names)
    return literals, repo_derived


def _bound_names_of_targets(targets):
    out = set()
    for target in targets:
        out.update(_bound_names(target))
    return out


def _local_sources(function):
    """local name -> the expressions it can carry.

    Loop and comprehension targets take their iterable as a source, and an
    assignment INSIDE a loop body additionally takes that loop's iterable: the
    counter in test_handover_epilogue_bullet.py:112-119 is `bare_count = 0`
    plus `bare_count += 1` inside `for path in COMMANDS_DIR.glob(...)`, so
    without the control-dependence edge it looks like a pure literal.
    """
    sources = {}

    def record(name, node):
        sources.setdefault(name, []).append(node)

    def walk(node, guards):
        if isinstance(node, (ast.For, ast.AsyncFor)):
            for name in _bound_names(node.target):
                record(name, node.iter)
            inner = guards + [node.iter]
            for child in node.body + node.orelse:
                walk(child, inner)
            return
        if isinstance(node, ast.Assign):
            for target in node.targets:
                for name in _bound_names(target):
                    record(name, node.value)
                    for guard in guards:
                        record(name, guard)
        elif isinstance(node, ast.AugAssign):
            for name in _bound_names(node.target):
                record(name, node.value)
                for guard in guards:
                    record(name, guard)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            for name in _bound_names(node.target):
                record(name, node.value)
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.withitem):
                if child.optional_vars is not None:
                    for name in _bound_names(child.optional_vars):
                        record(name, child.context_expr)
                continue
            if isinstance(child, ast.comprehension):
                for name in _bound_names(child.target):
                    record(name, child.iter)
                continue
            walk(child, guards)

    for stmt in function.body:
        walk(stmt, [])
    return sources


def _taint(expr, local_sources, repo, declared, class_literals,
           class_repo_attrs=frozenset(), seen=None):
    """(reaches_repo, reaches_declared, reaches_fixture) for one expression.

    `self.<attr>` and `self.<method>(...)` are FIXTURE roots and are never
    followed: a helper method's body reaches the repository (it runs a shipped
    script) while the thing it measures is a scratch directory built in setUp.
    Following it would report every `assertEqual(1, len(self.warnings(result)))`
    in the corpus as a pin. The one exception is a class-level literal
    constant, which is a declaration, not a fixture.
    """
    if seen is None:
        seen = set()
    reaches_repo = reaches_declared = reaches_fixture = False
    for node in ast.walk(expr):
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id == "self"):
            if node.attr in class_repo_attrs:
                reaches_repo = True
            elif node.attr not in class_literals:
                reaches_fixture = True
            continue
        if not isinstance(node, ast.Name):
            continue
        name = node.id
        if name == "self":
            continue
        if name in repo:
            reaches_repo = True
        if name in declared:
            reaches_declared = True
        if name in local_sources and name not in seen:
            seen.add(name)
            for source in local_sources[name]:
                r, d, f = _taint(source, local_sources, repo, declared,
                                 class_literals, class_repo_attrs, seen)
                reaches_repo = reaches_repo or r
                reaches_declared = reaches_declared or d
                reaches_fixture = reaches_fixture or f
    return reaches_repo, reaches_declared, reaches_fixture


def _assertion_operands(node):
    """The (a, b) pair an equality-family assertion compares, or None.

    Two shapes: `<x>.assertEqual(a, b)` and this module's own
    `assert_set_matches(testcase, a, b, subject)`. The second is a bare
    module-level function rather than a `self.<name>` method, so it needs its
    own recognition -- otherwise converting a count pin into the better set
    shape would remove it from this inventory, and the scanner would go quiet
    exactly where the repository improved.
    """
    if not isinstance(node, ast.Call):
        return None
    if (isinstance(node.func, ast.Attribute)
            and node.func.attr in EQUALITY_ASSERTS and len(node.args) >= 2):
        return node.args[0], node.args[1]
    if (isinstance(node.func, ast.Name)
            and node.func.id == "assert_set_matches" and len(node.args) >= 3):
        return node.args[1], node.args[2]
    return None


def _candidates_from_tree(tree, rel):
    repo, declared = _module_scope(tree)
    out = []
    for class_def in ast.walk(tree):
        if not isinstance(class_def, ast.ClassDef):
            continue
        class_literals, class_repo_attrs = _class_attribute_roots(class_def, repo)
        for function in class_def.body:
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not function.name.startswith("test"):
                continue
            local_sources = _local_sources(function)
            hits = []
            for call in ast.walk(function):
                operands = _assertion_operands(call)
                if operands is None:
                    continue
                first, second = operands
                for declared_side, measured_side in ((first, second), (second, first)):
                    reaches_repo, reaches_declared, reaches_fixture = _taint(
                        measured_side, local_sources, repo, declared,
                        class_literals, class_repo_attrs)
                    if not reaches_repo or reaches_fixture:
                        continue
                    is_literal, is_collection, is_nonzero_scalar = _literal_shape(
                        declared_side)
                    stores_a_value = (
                        # A non-zero scalar or a non-empty collection literal.
                        (is_literal and (is_nonzero_scalar
                                         or (is_collection
                                             and _is_nonempty_collection_literal(
                                                 declared_side))))
                        # A module-level declared constant, whatever its size.
                        or (isinstance(declared_side, ast.Name)
                            and declared_side.id in declared)
                        # The same, reached through `self` -- a class-body
                        # literal is a declaration, not a fixture, and it is
                        # written `self.EXPECTED_FLAGGED` at the assertion.
                        or (isinstance(declared_side, ast.Attribute)
                            and isinstance(declared_side.value, ast.Name)
                            and declared_side.value.id == "self"
                            and declared_side.attr in class_literals)
                        # Registry drift: `assertEqual(set(), found - REGISTRY)`
                        # stores its value inside the measured expression.
                        or (is_literal and is_collection and reaches_declared)
                    )
                    if stores_a_value:
                        hits.append(call.lineno)
                        break
            if hits:
                out.append(PinCandidate(
                    rel, class_def.name, function.name,
                    function.lineno, function.end_lineno or function.lineno,
                    sorted(set(hits))))
    return out


def candidates_from_source(source, rel="<source>"):
    """find_candidates against a source string -- used to test the pattern's
    documented limits against a constructed instance without adding a fixture
    file to the very corpus this module enumerates."""
    return _candidates_from_tree(ast.parse(source), rel)


def find_candidates(path, rel=None):
    """Every pin-shaped assertion in one file, as PinCandidate records."""
    return _candidates_from_tree(
        ast.parse(path.read_text(encoding="utf-8")), rel or path.name)


# ---------------------------------------------------------------------------
# Corpus enumeration
# ---------------------------------------------------------------------------

def corpus_files(tests_dir=TESTS_DIR):
    """The same enumeration test_absence_only_assertions.py uses: scripts/
    tests/*.py + scripts/tests/workitems/*.py, minus __init__.py."""
    files = (sorted(tests_dir.glob("*.py"))
             + sorted((tests_dir / "workitems").glob("*.py")))
    return [(f, f.relative_to(tests_dir).as_posix())
            for f in files if f.name != "__init__.py"]


def all_candidates(tests_dir=TESTS_DIR):
    out = []
    for path, rel in corpus_files(tests_dir):
        out.extend(find_candidates(path, rel))
    return out


def all_markers(tests_dir=TESTS_DIR):
    out = []
    for path, rel in corpus_files(tests_dir):
        out.extend(find_markers(path, rel))
    return out
