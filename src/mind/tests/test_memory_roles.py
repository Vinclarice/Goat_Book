"""What kind of memory is this — Track B increment 6, and **D6 answered**.

Part 2's first axis. A memory holds several roles at once: a recipe that is
also *from Mum*, also *for Christmas*, also *something I want to try*. The
brief is explicit that these are **facets, not exclusive folders**.

**D6 asked whether roles are new `FacetKind` values or one kind with typed
data, and a constraint decides it.** `facet_one_live_per_kind` is
`unique(node, kind)` over live facets — so a single `FacetKind.ROLE` could hold
exactly **one** role per note, and roles are multi-valued by definition. The
typed-data option is not a trade-off here; it is unavailable without changing a
constraint that exists for a good reason (*"a second proposal updates rather
than accumulates"*), and that reason is about repeated proposals of one
capability, not about a memory being several things.

So: **one `FacetKind` value per role**, which is what `FacetKind`'s own
docstring already says to do — *"open by design: new kinds are new values with
their own validation, not new tables, because the set is expected to keep
growing."*

**Not all fourteen.** The brief lists fourteen roles and production has no
evidence for any: a value nothing proposes and nobody confirms is the dark seam
this project keeps rediscovering, times fourteen. What ships is the mechanism
and the roles the brief's own worked examples turn on.

**Proposal is deferred with a named trigger, and that is the honest half.**
*Proposed after capture* needs a producer, and a role classifier built with no
evidence is a proposer whose accept rate nobody can read. `Facet.producer` and
the accept-rate machinery exist precisely to judge one — which is the trigger.
Until then a person says what a memory is, and nothing guesses.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import services
from mind.models import Facet, FacetKind, InferenceOrigin, Node


WRITTEN = datetime(2026, 5, 4, 9, 0, tzinfo=dt_timezone.utc)


def later(**offset):
    return WRITTEN + timedelta(**offset)


@pytest.fixture
def signed_in(client, owner):
    client.force_login(owner)
    return client


@pytest.fixture
def note(owner):
    return services.capture(
        owner,
        content="Mum's lemon chicken, the one for Christmas",
        captured_at=WRITTEN,
        source=Node.Source.WEB,
        actor="vince",
    )


def roles_of(node):
    return sorted(
        facet.kind
        for facet in Facet.objects.filter(node=node, retired_at__isnull=True)
        if facet.kind in services.MEMORY_ROLES
    )


# ---------------------------------------------------------------------------
# D6: one FacetKind per role, because a memory is several things at once
# ---------------------------------------------------------------------------


def test_a_memory_can_hold_several_roles_at_once(db, note):
    """The requirement the whole decision turns on. *A recipe that is also from
    Mum, also for Christmas* is one note and three roles, and a shape that
    permits one would have made the axis meaningless."""
    services.say_what_this_is(note, roles=[FacetKind.RECIPE, FacetKind.OCCASION], now=WRITTEN, actor="vince")

    assert roles_of(note) == sorted([FacetKind.RECIPE, FacetKind.OCCASION])


def test_every_role_is_its_own_kind(db):
    """D6's answer, asserted rather than described: `facet_one_live_per_kind`
    is `unique(node, kind)`, so multi-valued and one-kind-with-data are
    mutually exclusive."""
    for role in services.MEMORY_ROLES:
        assert role in FacetKind.values


def test_a_role_is_corrigible(db, note):
    """*Proposed after capture, corrigible, never asked for.* Saying a note is
    a dream and then that it is not has to be as cheap as saying it was."""
    services.say_what_this_is(note, roles=[FacetKind.DREAM], now=WRITTEN, actor="vince")
    services.say_what_this_is(note, roles=[FacetKind.RECIPE], now=later(days=1), actor="vince")

    assert roles_of(note) == [FacetKind.RECIPE]


def test_saying_the_same_roles_again_changes_nothing(db, note):
    """The emitter-contract instinct, one module over: a corrigible property
    re-saved is not a second act, and `Facet` carries `confirmed_at` that a
    rewrite would move."""
    services.say_what_this_is(note, roles=[FacetKind.RECIPE], now=WRITTEN, actor="vince")
    first = Facet.objects.get(node=note, kind=FacetKind.RECIPE)

    services.say_what_this_is(note, roles=[FacetKind.RECIPE], now=later(days=1), actor="vince")

    assert Facet.objects.get(node=note, kind=FacetKind.RECIPE).pk == first.pk
    assert Facet.objects.get(node=note, kind=FacetKind.RECIPE).confirmed_at == first.confirmed_at


def test_a_role_a_person_gave_is_stated_not_inferred(db, note):
    """`origin` already separates a person's statement from a producer's guess,
    and the soft-apply rule turns on it: a guess is never treated as fact by
    anything downstream."""
    services.say_what_this_is(note, roles=[FacetKind.RECIPE], now=WRITTEN, actor="vince")

    assert Facet.objects.get(node=note, kind=FacetKind.RECIPE).origin == InferenceOrigin.EXPLICIT


def test_a_role_a_person_gave_is_confirmed_on_arrival(db, note):
    services.say_what_this_is(note, roles=[FacetKind.RECIPE], now=WRITTEN, actor="vince")

    assert Facet.objects.get(node=note, kind=FacetKind.RECIPE).confirmed_at == WRITTEN


def test_something_that_is_not_a_role_is_refused(db, note):
    """`ACTIONABLE` is a capability with its own data and its own confirmation
    path, and routing it through here would walk round `confirm_actionable` --
    which is the one facet that may never be attached outright."""
    with pytest.raises(services.MindError):
        services.say_what_this_is(note, roles=[FacetKind.ACTIONABLE], now=WRITTEN, actor="vince")


def test_a_deleted_note_gets_no_roles(db, note):
    services.delete_node(note, now=later(days=1), actor="vince")

    with pytest.raises(services.Deleted):
        services.say_what_this_is(note, roles=[FacetKind.RECIPE], now=later(days=2), actor="vince")


# ---------------------------------------------------------------------------
# Nothing guesses, and the deferral is declared
# ---------------------------------------------------------------------------


def test_nothing_proposes_a_role_yet_and_the_module_says_so(db):
    """*Proposed after capture* needs a producer, and a role classifier with no
    evidence is a proposer whose accept rate nobody can read.

    Declared rather than half-built, and `Facet.producer` plus the accept-rate
    machinery are the named trigger -- they exist to judge exactly this.
    """
    assert services.ROLE_PROPOSAL_IS_DEFERRED


# ---------------------------------------------------------------------------
# The surface
# ---------------------------------------------------------------------------


def test_the_note_page_offers_the_roles(signed_in, note):
    body = signed_in.get(f"/mind/notes/{note.public_id}/").content.decode()

    for role in services.MEMORY_ROLES:
        assert role in body


def test_saying_what_a_note_is_from_the_page(signed_in, note):
    signed_in.post(
        f"/mind/notes/{note.public_id}/is/",
        {"roles": [FacetKind.RECIPE, FacetKind.OCCASION]},
    )

    assert roles_of(note) == sorted([FacetKind.RECIPE, FacetKind.OCCASION])


def test_the_page_shows_what_a_note_already_is(signed_in, note):
    services.say_what_this_is(note, roles=[FacetKind.RECIPE], now=WRITTEN, actor="vince")

    body = signed_in.get(f"/mind/notes/{note.public_id}/").content.decode()

    assert "checked" in body


def test_nobody_types_another_persons_note(client, other_owner, note):
    client.force_login(other_owner)
    client.post(f"/mind/notes/{note.public_id}/is/", {"roles": [FacetKind.RECIPE]})

    assert roles_of(note) == []


def test_saying_what_a_note_is_needs_a_post(signed_in, note):
    response = signed_in.get(f"/mind/notes/{note.public_id}/is/")

    assert response.status_code == 405
