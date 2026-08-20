"""How a person's typed text becomes a query, defined once.

`search-plan.md` makes the results sectioned -- tasks, journal, notes, each
ranked within itself -- and that design has a quiet dependency: every section
must have searched for the *same thing*. Two apps each building their own
`SearchQuery` is how one section starts requiring both words while another
accepts either, and the person sees two lists that disagree without being told
they were asked different questions.

So this is `principles.md`'s "one rule, one authoritative definition" applied to
a rule that is three lines long and would otherwise be copied. It lives in
`clarice` rather than in either core because it belongs to neither; the same
question about the *endpoint* is open as D1 in the plan, and this does not
answer it.
"""

from django.contrib.postgres.search import SearchQuery

# `websearch` rather than the default `plain`. Two words narrow rather than
# widen -- a query that ORs its terms gets less useful the more the person
# types, which is backwards -- and it accepts quoted phrases and a leading `-`
# without ever raising on malformed input, which `raw` would. What a person
# types into a search box is not a tsquery and should not be able to be one.
SEARCH_TYPE = "websearch"

# The stemmer. Without a configuration this is a LIKE query wearing a hat, and
# the case this exists for -- finding what you wrote three weeks ago -- is
# exactly the case where you remember the word with a different ending.
CONFIG = "english"


def to_query(text):
    """The tsquery for this text, or None if there is nothing to search for.

    None rather than an empty query, so callers return an empty result set
    without going to the database at all. A blank search box is the single most
    likely input on a search page, and the classic version of this bug returns
    the entire table for it.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    return SearchQuery(cleaned, config=CONFIG, search_type=SEARCH_TYPE)
