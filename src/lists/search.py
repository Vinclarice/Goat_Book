"""Read-side search over tasks.

Query and derivation only; mutations live in `lists.services`. Split this way
from the first slice per `architecture-trajectory.md` §4 rule 4, and kept out
of `agenda.py` because that module answers "what should I do today" and this
one answers "where did I write that" -- two questions whose rules should be
free to diverge.

`design/search-plan.md` slice 1.
"""

from django.contrib.postgres.search import SearchRank
from django.db.models import F

from clarice.search import to_query
from lists.models import Item


def search_tasks(owner, text):
    """This owner's tasks matching `text`, best first.

    **Ranked from the first version rather than sorted later.** The knowledge
    core's search was a recency truncation for a while, and `mind/queries.py:78`
    records what that actually meant: it took the newest thirty matches rather
    than the best thirty, so which task you found depended on when you wrote it.
    That is a worse failure than a slow query and it is invisible.

    **Every status, deliberately.** The agenda hides completed and archived work
    because it is a plan for today; this is not the agenda. The older a task is,
    the more likely it is both finished and the one being looked for -- so
    filtering by status here would recreate the complaint this exists to answer,
    on exactly the material most affected by it. `status` rides along on each row
    so a surface can label it.
    """
    query = to_query(text)
    if query is None:
        return Item.objects.none()

    return (
        Item.objects.filter(owner=owner, search_document=query)
        .annotate(rank=SearchRank(F("search_document"), query))
        # `-updated_at` breaks ties rather than leaving them to the table's
        # order. Two equally good matches is common -- a task and its near
        # duplicate -- and an unstable order there means the same search returns
        # a different first result twice in a row.
        .order_by("-rank", "-updated_at")
    )
