"""similar.py -- `workitems.py similar "<text>"`: a read-only ranked TEXT search
over every item's title+description (CCP-1172).

ADR-0004 already settled dedup for the `lift` path ("deduplicate by behaviour
described, not by id") and explicitly rejected dedup-by-id. This module is the same
check for the OTHER creation path -- `create`, the one a planning command and a
human operator actually use -- and it approximates ADR-0004's goal rather than
reaching it: it ranks shared VOCABULARY, not shared MEANING (see NOT_REACHED).

Ranking: TF-IDF-weighted cosine similarity over a stopword-filtered token set. The
inverse-document-frequency term is computed FROM the corpus passed in (`backend.
list()`), never from a fixed table, so a word common across THIS project's items
(e.g. "item", "test", "check" in a repo about testing tooling) counts for less than
one that appears in only a handful.

Measured against a confirmed known-neighbour case (CCP-1167's text against the
173 OTHER items in this repo's own 174-item corpus, 10.09.2026, re-derived
against the code as shipped -- code-review follow-up, a prior revision of this
comment quoted a rank measured before the trailing-+1 smoothing below existed):
raw word-overlap (unweighted cosine on term counts) ranks the confirmed
neighbour CCP-1136 15th, outside any reasonable `--limit`; TF-IDF WITHOUT the
trailing +1 smoothing ranks it 2nd; TF-IDF WITH it -- the configuration this
module actually ships -- ranks it 6th. All three inside the default
`--limit 10` except the raw baseline. The smoothing trades some of that
precision for correctness at small corpus sizes (see `_tfidf_vector`'s own
comment): without it, a corpus of exactly one item can never be found at all.

Same three-part could-not-run shape lint.py's refusal() established (CCP-1171): a
search that could not read the corpus must never look like a search that read it
and found nothing similar -- an exit code alone cannot tell the two apart.
"""

import math
import re
from collections import Counter

from workitems import WorkItemError

DEFAULT_LIMIT = 10

# Words filtered out before scoring: high-frequency function words that carry no
# topical signal and would otherwise dominate every item's vector.
STOPWORDS = frozenset("""
    a an the of to in on for is are was were be been being this that these those
    it its as with and or not no but if then than so at by from into over under
    between each every any all both either neither one two three four five six
    seven eight nine ten first second third can could will would should shall
    may might must never always often sometimes here there where when why how
    what which who whom whose you he she we they them their his her our your
    my me us do does did done have has had having own same other another such
    only just also too very more most less least much many few s re
""".split())

# Unicode letters (code-review finding): `[a-zA-Z']+` broke a word at every
# non-ASCII letter -- CCPR ships to projects that do not write their items in
# English. `[^\W\d_]` is `\w` (Unicode-aware by default for a `str` pattern in
# Python 3) minus the two things `\w` also matches that are not letters
# (digits, underscore), so it reaches "Größe" and "café" the way `[a-zA-Z]`
# reached "cafe". The apostrophe is kept as an internal joiner only (`don't`,
# not a leading/trailing one) rather than folded into the same class as
# before, which also accepted a bare run of apostrophes as its own "word".
TOKEN_PATTERN = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*")

# The reference classes this search cannot reach, stated in its own output rather
# than only in the work item that commissioned it (mirrors lint.py's NOT_REACHED,
# CCP-1171): a comparison whose extent is not stated is not a result.
NOT_REACHED = (
    "a description of the same behaviour in different words -- this ranks shared "
    "VOCABULARY, not shared MEANING, so a paraphrase or a synonym-heavy rewrite "
    "stays invisible; ADR-0004's 'deduplicate by behaviour described' is the "
    "goal, and a text search only approximates it",
    "a reference living only in a comment, a result-link, or a tag: only title "
    "and description are scored",
    "an item with no vocabulary at all in common with the query -- it scores "
    "0.0 and is dropped from the ranking rather than listed with a zero",
)


def refusal(reason, provider=None):
    """The one report shape for 'nothing was compared' -- same three-part wording
    lint.refusal() and install.sh's verify_cannot_run() use: a check that could not
    look is not a check that looked and found nothing similar."""
    return {
        "verdict": "could-not-run",
        "provider": provider,
        "reason": reason,
        "message": (
            f"COULD NOT RUN -- {reason}. Nothing was compared. This is NOT the "
            "same as 'no similar items'. the work-item similarity search DID NOT RUN"
        ),
        "items_scanned": None,
        "results": [],
    }


def _tokenize(text):
    return [
        token.lower() for token in TOKEN_PATTERN.findall(text or "")
        if len(token) > 2 and token.lower() not in STOPWORDS
    ]


def _text_of(item):
    return " ".join(part for part in (item.get("title"), item.get("description")) if part)


def _document_frequencies(token_lists):
    df = Counter()
    for tokens in token_lists:
        df.update(set(tokens))
    return df


def _tfidf_vector(tokens, df, corpus_size):
    counts = Counter(tokens)
    # +1/+1 smoothing INSIDE the log, plus a trailing +1 on the whole term (the
    # scikit-learn `smooth_idf` convention): without the trailing +1, a corpus of
    # exactly ONE item makes every one of its own terms score idf=log(2/2)=0 --
    # its vector goes entirely to zero and it can never be found, regardless of
    # how similar the query is. The trailing +1 keeps a floor under every term's
    # weight so a small corpus does not silently zero itself out.
    return {
        term: count * (math.log((corpus_size + 1) / (df.get(term, 0) + 1)) + 1)
        for term, count in counts.items()
    }


def _cosine(a, b):
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[term] * b[term] for term in common)
    norm_a = math.sqrt(sum(value * value for value in a.values()))
    norm_b = math.sqrt(sum(value * value for value in b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def similar(backend, query_text, limit=DEFAULT_LIMIT, provider=None):
    """One pass over every item the backend lists, ranked by similarity to
    `query_text`. Returns a report dict.

    Two verdicts on the success path -- `results` (read, at least one item shares
    vocabulary with the query) and `no-results` (read, nothing does) -- plus
    `could-not-run` when the backend itself could not be reached. `could-not-run`
    is not `no-results` with a different label: an exit code alone cannot tell
    "the corpus was empty of matches" from "the corpus was never read".
    """
    try:
        items = backend.list()
    except WorkItemError as exc:
        return refusal(str(exc), provider=provider)

    token_lists = [_tokenize(_text_of(item)) for item in items]
    df = _document_frequencies(token_lists)
    corpus_size = len(items)
    query_vector = _tfidf_vector(_tokenize(query_text), df, corpus_size)

    scored = []
    for item, tokens in zip(items, token_lists):
        item_vector = _tfidf_vector(tokens, df, corpus_size)
        score = _cosine(query_vector, item_vector)
        if score > 0.0:
            scored.append({"id": item["id"], "title": item["title"], "score": round(score, 4)})

    scored.sort(key=lambda result: (-result["score"], result["id"]))
    # Verdict comes from the RANKED list, before the --limit slice (code-review
    # finding, Important): "found, but truncated to zero by --limit" is not the
    # same observation as "no vocabulary in common at all" -- exactly the
    # confusion the three-verdict form exists to prevent, one level deeper than
    # could-not-run vs. no-results.
    verdict = "results" if scored else "no-results"
    results = scored[:limit]

    return {
        "verdict": verdict,
        "provider": provider,
        "items_scanned": len(items),
        "query": query_text,
        "scope": {
            "fields_scanned": ["title", "description"],
            "method": (
                "TF-IDF-weighted cosine similarity over a stopword-filtered token "
                "set; the IDF term is computed from this corpus, not a fixed table"
            ),
            "limit": limit,
            "not_reached": list(NOT_REACHED),
        },
        "results": results,
    }
