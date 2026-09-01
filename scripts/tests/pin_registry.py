r"""pin_registry.py -- WI-0133 T1: the shared vocabulary for ADR-0012 pins.

Deliberately NOT named `test_*`: `unittest discover` must not collect it. It
sits directly under `scripts/tests/` rather than in a subpackage so that it
stays inside test_absence_only_assertions.py's existing `TESTS_DIR.glob("*.py")`
scan -- a helper in a new subpackage would be a new blind spot in the very
corpus this round exists to enumerate.

Three things live here:

* `PIN_GROUPS` + `MARKER_RE` -- the marker vocabulary a pin uses to name
  itself at its own site, per ADR-0012 obligation 1.
* `find_sites` -- the AST-derived population of assertions that LOOK like
  pins, so a pin that never named itself can still be found and reported. Its
  unit is the ASSERTION, not the method around it (WI-0133 T2c); `bind_markers`
  says which assertion a marker names.
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
        """Line-free identity -- see `subject_of`."""
        return (self.rel, self.group, self.pin_id)

    def __repr__(self):
        return "Marker{}".format((self.rel, self.lineno, self.group, self.pin_id))


# The outermost node of a measured expression, as a stable word. It is what
# separates `len(names)` from `names`: the same name, a different measurement.
# Rendered from the node TYPE rather than from `ast.unparse`, and the
# difference is not stylistic -- see `subject_of`.
SUBJECT_TAGS = {
    ast.Attribute: "attr", ast.BinOp: "binop", ast.BoolOp: "boolop",
    ast.Call: "call", ast.Compare: "compare", ast.Constant: "const",
    ast.Dict: "dict", ast.DictComp: "dictcomp", ast.GeneratorExp: "genexp",
    ast.IfExp: "ifexp", ast.JoinedStr: "fstring", ast.Lambda: "lambda",
    ast.List: "list", ast.ListComp: "listcomp", ast.Name: "name",
    ast.Set: "set", ast.SetComp: "setcomp", ast.Starred: "starred",
    ast.Subscript: "item", ast.Tuple: "tuple", ast.UnaryOp: "unaryop",
}


def subject_of(expr):
    """A line-free name for WHAT one assertion measures (WI-0133 T2c).

    Since T2c a marker belongs to an ASSERTION, not to the method around it,
    so the identity of a pin site has to separate two assertions inside one
    method -- and it still must not contain a line number. The lesson that
    forbids the line is recorded in test_external_tool_exit_status.py:1173-1178:
    the same change measured both ways gave 7 additions / 4 removals with a
    line-bearing identity and 3 / 0 without, because every insertion above a
    site reads as one removal plus one addition.

    The fourth component is therefore the measured expression itself, rendered
    as a sorted token set plus the kind of its outermost node:

        len(invocations)  ->  "invocations+len:call"
        by_disposition    ->  "by_disposition:name"

    Why this is line-free AND stable, which are two different claims:

    * **Line-free**: it is derived from the expression, not from its position.
      Inserting a line, a docstring or a whole sibling assertion above a site
      leaves it untouched. An ORDINAL within the method would also avoid the
      word "line" while keeping exactly the defect -- inserting an assertion
      renumbers every one below it -- so an ordinal was rejected.
    * **Sensitive in the right place**: it moves when the assertion's measured
      side is edited. That is the correct sensitivity, not noise: the site
      being measured has changed, and a PENDING entry going stale is the
      signal someone should look. The line number's defect is that it moves
      for edits that are not about the site at all.

    Why the tokens are rendered here rather than by `ast.unparse`, which would
    be one line: `ast.unparse` output is INTERPRETER-DEPENDENT. Measured over
    this corpus on 3.9.6 and on 3.14.4, eleven operands differ -- 3.9 writes
    `{path for (path, _line, _rule, _cat) in exempted}` and 3.12+ writes the
    same target without parentheses -- and one of them is a live pin site
    (test_bsd_gnu_portability.py:1923). An identity that changes with the
    interpreter would make PENDING go stale on CI (pinned to 3.11) while
    staying green on the machine that wrote it. The token rendering below uses
    only node types, `Attribute.attr` and `Constant.value`, and produced
    byte-identical output on both interpreters.

    Tokens, and why each is needed:

    * free `ast.Name` ids -- the names the expression reads. Comprehension and
      lambda targets are subtracted: renaming a loop variable is not a change
      of subject. `self` is dropped, it names no subject.
    * `.attr` for every attribute access -- without it
      `len(found)` and `len(found[0].assert_linenos)` collide.
    * `[<const>]` for every constant subscript key -- without it
      `len(ns['COMPLETED'])` and `len(ns['HANDLERS'])` collide.

    Measured over the whole corpus: 174 sites, 174 distinct keys. The bare
    name set alone collided 5 times; adding the two token kinds above removed
    all five.

    TWO WAYS THIS IS DELIBERATELY NOT INJECTIVE, both latent today and both
    pinned by `test_the_subject_is_a_token_set_and_not_a_rendering`:

    * a TOKEN SET carries no order, so `f(a, b)` and `f(b, a)` -- and `a - b`
      and `b - a` -- render the same. Rendering order would fix it and would
      re-introduce the interpreter dependence the token set exists to avoid.
    * the bound-name subtraction is SCOPE-BLIND: `bound` and `tokens` are both
      collected over the whole expression, so a name that is a comprehension
      target in one sub-expression is subtracted even where it occurs free in
      another (`sum(x for x in y) + x` loses `x` entirely).

    Neither can misbind a marker silently. The failure mode of both is two
    sites sharing one key, and
    `test_every_site_in_the_corpus_has_a_unique_identity` fails loudly on
    exactly that over the whole corpus. Sharpening the renderer is the answer
    if that test ever goes red -- not before, because every sharpening costs
    stability against edits that are not about the subject.
    """
    bound = set()
    for node in ast.walk(expr):
        if isinstance(node, ast.comprehension):
            bound.update(_bound_names(node.target))
        elif isinstance(node, ast.Lambda):
            arguments = node.args
            for group in (getattr(arguments, "posonlyargs", []),
                          arguments.args, arguments.kwonlyargs):
                bound.update(argument.arg for argument in group)
            for single in (arguments.vararg, arguments.kwarg):
                if single is not None:
                    bound.add(single.arg)
    tokens = set()
    for node in ast.walk(expr):
        if isinstance(node, ast.Name):
            tokens.add(node.id)
        elif isinstance(node, ast.Attribute):
            tokens.add("." + node.attr)
        elif isinstance(node, ast.Subscript):
            key = node.slice
            if isinstance(key, ast.Constant) and isinstance(key.value, (str, int)):
                tokens.add("[{}]".format(key.value))
    tokens -= bound
    tokens.discard("self")
    tag = SUBJECT_TAGS.get(type(expr), type(expr).__name__.lower())
    return "{}:{}".format("+".join(sorted(tokens)) or "-", tag)


class PinSite:
    """ONE assertion shaped like a pin, identified WITHOUT a line number.

    Until WI-0133 T2c the unit was the METHOD (`PinSite`), and a method
    carrying two pin-shaped assertions was one record with a tuple of lines.
    That made the marker's group statement unresolvable exactly where it is
    needed: `ExternalToolExitStatusTest.test_classification_counts` pins a
    count on one line and a membership register on the next, and one marker
    over both would have to call them the same group. 25 methods in this
    corpus carry more than one pin-shaped assertion and 4 of those carry two
    different declared shapes.

    `key()` is (file, class, method, subject) -- see `subject_of` for why the
    fourth component is the measured expression and not an ordinal.
    `lineno`/`end_lineno` are the ASSERTION CALL's span, kept so a marker can
    be bound to the assertion it sits on, and never part of `key()`.
    """

    __slots__ = ("rel", "class_name", "method_name", "subject",
                 "declared_shape", "lineno", "end_lineno")

    def __init__(self, rel, class_name, method_name, subject, declared_shape,
                 lineno, end_lineno):
        self.rel = rel
        self.class_name = class_name
        self.method_name = method_name
        self.subject = subject
        self.declared_shape = declared_shape
        self.lineno = lineno
        self.end_lineno = end_lineno

    def key(self):
        return (self.rel, self.class_name, self.method_name, self.subject)

    def method_key(self):
        return (self.rel, self.class_name, self.method_name)

    def __repr__(self):
        return "PinSite{}".format(self.key())


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


def _mutated_names(target):
    """The name an assignment MUTATES rather than rebinds: `tally[i] = ...`
    and `tally[i] += 1` both write into `tally`.

    Kept apart from `_bound_names` on purpose. `_bound_names` also feeds
    `_module_scope`, where `assignments[name] = stmt.value` keeps the LAST
    binding of a name; folding subscript targets in there would let
    `REGISTRY['a'] = 1` overwrite `REGISTRY = {...}`'s declared binding and
    silently reclassify a module-level constant. Only `_local_sources` needs
    this, and only to ADD a source to a name that already has one.

    `self.counts[k] = ...` is deliberately not matched: its base is an
    `ast.Attribute`, and `self` is a fixture root that is never followed. The
    exclusion is in fact structurally inert, which is the stronger reason:
    `_taint` handles a `self.<attr>` node in its own branch and `continue`s
    without ever consulting `local_sources`, and it skips the bare name `self`
    as well -- so matching that shape here could not change a verdict either
    way. Measured too: the corpus has two `self.<attr>[k] = ...` sites, both in
    `workitems/fake_youtrack_transport.py` and neither inside a `test*` method.
    Widening this function to EVERY subscript base (`self.<attr>[k]`, `f()[k]`,
    nested) was probed over the whole corpus and moved nothing: zero additions,
    zero removals.
    """
    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
        return [target.value.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        out = []
        for element in target.elts:
            out.extend(_mutated_names(element))
        return out
    return []


def _names_used(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _module_scope(tree):
    """(repo_derived_names, declared_constant_names, declared_shapes).

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
    declared_shapes = {}
    for name, value in assignments.items():
        is_literal, is_collection, is_nonzero_scalar = _literal_shape(value)
        if is_literal and (is_collection or is_nonzero_scalar):
            declared.add(name)
            declared_shapes[name] = "collection" if is_collection else "scalar"

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
    return repo - declared, declared, declared_shapes


def _class_attribute_roots(class_def, repo):
    """Class-body names that are NOT fixtures: (declared_literals,
    repo_derived, literal_shapes).

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
    literal_shapes = {}
    repo_derived = set()
    for stmt in class_def.body:
        if not isinstance(stmt, ast.Assign):
            continue
        is_literal, is_collection, is_nonzero_scalar = _literal_shape(stmt.value)
        names = _bound_names_of_targets(stmt.targets)
        if is_literal and (is_collection or is_nonzero_scalar):
            literals.update(names)
            for name in names:
                literal_shapes[name] = "collection" if is_collection else "scalar"
            continue
        used = _names_used(stmt.value)
        if used and used <= repo:
            repo_derived.update(names)
    return literals, repo_derived, literal_shapes


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

    That edge only fires for a name an assignment TARGET names, which is why
    it also has to run over `_mutated_names`: an accumulator built as
    `tally[key] = ...` inside the loop is written through a Subscript, binds
    no `ast.Name`, and so inherited nothing. That is not a corner case --
    test_external_tool_exit_status.py's `test_classification_counts`
    accumulates its per-disposition register exactly that way, and the
    candidate carried only its total assertion until WI-0133 T2b.

    WHAT THIS STILL DOES NOT SEE, AND IT IS THE SAME MECHANISM: accumulation
    by METHOD CALL. `out.append(i)`, `seen.add(i)` and `tally.update(...)`
    inside a loop are `ast.Expr` statements with no assignment target at all,
    so nothing binds their container to the loop. Measured, not assumed --
    `OriginTrackingIsFormDependentTest` in test_pin_inventory.py carries all
    three as recorded findings. Closing them is a scope decision (a call whose
    receiver is a local name mutates that local), deliberately not taken here.
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
                for name in (_bound_names(target) + _mutated_names(target)):
                    record(name, node.value)
                    for guard in guards:
                        record(name, guard)
        elif isinstance(node, ast.AugAssign):
            for name in (_bound_names(node.target)
                         + _mutated_names(node.target)):
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


def _declared_shape(declared_side, declared_shapes, class_shapes):
    """"scalar" or "collection" for the DECLARED side of one assertion.

    The coarsest property of a pin that the four `PIN_GROUPS` disagree about,
    and the only one derivable without doing the classification work itself: a
    `set` pin's declared side IS the collection, while a count or a floor is a
    scalar. WI-0133 T2c uses it to tell "a method with two subjects" from "a
    method with two subjects a single marker could not describe truthfully",
    which is the distinction the per-assertion rule exists for.

    Deliberately NOT a group. It cannot decide `derived` against `set`, and it
    is not meant to: the classification is the later tranches' work, and a
    discriminator that guessed a group here would put the same false statement
    in the mechanism that a wrong marker puts at a site.
    """
    is_literal, is_collection, is_nonzero_scalar = _literal_shape(declared_side)
    if is_literal and is_collection:
        return "collection"
    if is_literal and is_nonzero_scalar:
        return "scalar"
    if isinstance(declared_side, ast.Name):
        return declared_shapes.get(declared_side.id, "other")
    if (isinstance(declared_side, ast.Attribute)
            and isinstance(declared_side.value, ast.Name)
            and declared_side.value.id == "self"):
        return class_shapes.get(declared_side.attr, "other")
    return "other"


def _sites_from_tree(tree, rel):
    repo, declared, declared_shapes = _module_scope(tree)
    out = []
    for class_def in ast.walk(tree):
        if not isinstance(class_def, ast.ClassDef):
            continue
        class_literals, class_repo_attrs, class_shapes = _class_attribute_roots(
            class_def, repo)
        for function in class_def.body:
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not function.name.startswith("test"):
                continue
            local_sources = _local_sources(function)
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
                        out.append(PinSite(
                            rel, class_def.name, function.name,
                            subject_of(measured_side),
                            _declared_shape(declared_side, declared_shapes,
                                            class_shapes),
                            call.lineno, call.end_lineno or call.lineno))
                        break
    return out


def sites_from_source(source, rel="<source>"):
    """find_sites against a source string -- used to test the pattern's
    documented limits against a constructed instance without adding a fixture
    file to the very corpus this module enumerates."""
    return _sites_from_tree(ast.parse(source), rel)


def find_sites(path, rel=None):
    """Every pin-shaped assertion in one file, as PinSite records."""
    return _sites_from_tree(
        ast.parse(path.read_text(encoding="utf-8")), rel or path.name)


# ---------------------------------------------------------------------------
# Binding a marker to the assertion it names
# ---------------------------------------------------------------------------

def bind_markers(sites, markers):
    """(bound, unbound) -- which assertion each `# pin:` marker names.

    Returns a dict from `PinSite.key()` to the markers on that assertion, and
    a sorted list of `(rel, lineno, group, pin_id)` for markers that name no
    pin-shaped assertion at all.

    A MARKER NAMES AN ASSERTION, NOT A METHOD (WI-0133 T2c). Before T2c the
    completeness check asked only whether some marker fell anywhere inside the
    method's span, so one marker silently vouched for every pin-shaped
    assertion in it -- and a group named once for two subjects of different
    groups is a false statement exactly where the group is consulted.

    Two placements are accepted, and both are the same relation ("the marker
    stands over this assertion"):

    * INSIDE the assertion's own span, which in this corpus means as a
      trailing comment on the call's first line
      (`self.assertEqual(  # pin: <group> <id>`). All 22 markers live today
      use this form -- measured, not assumed. The example is written with
      PLACEHOLDERS and not with a real group and id, because `find_markers` is
      a line regex with no notion of Python strings: a complete marker inside
      this docstring would be a live, unregistered marker in the corpus this
      module enumerates. The first draft of this docstring planted one.
    * on the line DIRECTLY ABOVE the assertion's first line, for an assertion
      whose first line has no room left.

    The span match wins when both could apply, and the innermost span wins if
    two assertions were ever nested, so the binding is total and deterministic.

    UNBOUND MARKERS ARE LEGAL AND ARE RETURNED RATHER THAN REJECTED. A marker
    must be allowed on a pin this scanner cannot see -- gap 8 of the boundary
    clause is exactly that, and two markers in this corpus sit on such sites.
    Nothing enforces marker-implies-site and nothing should; returning them
    makes the set visible so it can be pinned instead of drifting.
    """
    by_rel = {}
    for site in sites:
        by_rel.setdefault(site.rel, []).append(site)

    bound = {}
    unbound = []
    for marker in markers:
        in_file = by_rel.get(marker.rel, ())
        containing = sorted(
            (site for site in in_file
             if site.lineno <= marker.lineno <= site.end_lineno),
            key=lambda site: (site.end_lineno - site.lineno, site.lineno))
        target = containing[0] if containing else None
        if target is None:
            below = sorted((site for site in in_file
                            if site.lineno == marker.lineno + 1),
                           key=lambda site: site.end_lineno)
            target = below[0] if below else None
        if target is None:
            unbound.append((marker.rel, marker.lineno, marker.group,
                            marker.pin_id))
            continue
        bound.setdefault(target.key(), []).append(marker)
    return bound, sorted(unbound)


def methods_with_multiple_sites(sites):
    """Sorted (rel, class, method) keys carrying more than one pin-shaped
    assertion. Mere multiplicity -- NOT a problem on its own."""
    return sorted(key for key, group in _sites_by_method(sites).items()
                  if len(group) > 1)


def methods_with_divergent_declared_shapes(sites):
    """Sorted (rel, class, method) keys carrying pin-shaped assertions of MORE
    THAN ONE declared shape -- the subset of `methods_with_multiple_sites`
    that a single marker could not describe truthfully.

    The two are kept apart on purpose (WI-0133 T2c, PO). Splitting a method
    that merely repeats one shape would be work with no gain in what the
    inventory can say; splitting a method whose subjects disagree about their
    shape is the whole reason the marker's unit moved to the assertion.
    """
    return sorted(key for key, group in _sites_by_method(sites).items()
                  if len({site.declared_shape for site in group}) > 1)


def _sites_by_method(sites):
    out = {}
    for site in sites:
        out.setdefault(site.method_key(), []).append(site)
    return out


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


def all_sites(tests_dir=TESTS_DIR):
    out = []
    for path, rel in corpus_files(tests_dir):
        out.extend(find_sites(path, rel))
    return out


def all_markers(tests_dir=TESTS_DIR):
    out = []
    for path, rel in corpus_files(tests_dir):
        out.extend(find_markers(path, rel))
    return out
