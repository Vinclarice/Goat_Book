"""The knowledge core's own routes, mounted at `/mind/` by the project.

Split out of Second Mind's project URLconf when the app moved here on
August 14, 2026. Login, logout and admin stayed behind: this project already has
all three, and a second login page would be two ways to sign in to one
application.

Everything is relative and every template reverses through `{% url %}`, so the
prefix the project chooses is not baked in anywhere. That was written when the
prefix was temporary; it held, the prefix is now permanent (Heron step 5, see
`clarice/urls.py`), and it stays true because a URLconf that does not know where
it is mounted is simply a better URLconf.

**This is where the crossover ended.** Nine routes live here and only one is
capture — so this is the knowledge core's home rather than a capture page's, and
`/capture/`, freed by deleting the Inbox, would have named the smallest thing
under it.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.capture, name="capture"),
    path("share/", views.share, name="share"),
    path("<uuid:public_id>/tags/", views.tag_node, name="tag_node"),
    path(
        "commitments/<uuid:public_id>/",
        views.accept_commitment,
        name="accept_commitment",
    ),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("review/", views.review, name="review"),
    path("review/<uuid:public_id>/", views.resolve, name="resolve"),
    # A question is answered, not resolved-as-a-proposal, so it gets its own
    # routes rather than a mode on the one above. Two decisions that mean
    # different things sharing an endpoint is how one of them quietly acquires
    # the other's semantics.
    path(
        "questions/<uuid:public_id>/resolve/",
        views.resolve_question,
        name="resolve_question",
    ),
    path(
        "questions/<uuid:public_id>/dismiss/",
        views.dismiss_question,
        name="dismiss_question",
    ),
    # One note. `notes/` rather than a bare `<uuid>/` prefix, which is
    # already taken by `tag_node` -- and a noun in the path is worth the
    # eight characters when the surface is meant to be linked to.
    path("notes/<uuid:public_id>/", views.note, name="note"),
    # The door `revise` never had -- Track E increment 21.
    path(
        "notes/<uuid:public_id>/revise/", views.revise_note, name="revise_note"
    ),
    path("concepts/", views.concepts, name="concepts"),
    path("concepts/<uuid:public_id>/", views.concept, name="concept"),
    path(
        "concepts/<uuid:public_id>/decide/",
        views.decide_concept,
        name="decide_concept",
    ),
    path("search/", views.search, name="search"),
    path("search/miss/", views.record_miss, name="record_miss"),
    path("numbers/", views.summary, name="summary"),
    # **There is no API under here, and that is the resolution rather than an
    # omission.** This app arrived with its own `NinjaAPI` at `/mind/api/v1/`,
    # kept separate because both cores defined `/api/v1/capture` -- one for the
    # Inbox, one as the mobile alias. Its own note said that collision was "the
    # dual-write question arriving early, and it is answered when facets land:
    # one capture endpoint that writes a node and optionally a task."
    #
    # Facets landed, Heron 4a made that one endpoint, and this API was deleted
    # afterwards having never been called by anything -- not the phone, which
    # was never built split, and not these pages, which carry no JavaScript at
    # all. It took `mind.ApiToken` with it: a second token table in an
    # application with one user table, holding zero rows in production.
    #
    # A knowledge-core endpoint belongs on the application's `/api/v1/` now, as
    # a router in `mind/api_v1.py`, beside the capture one.
]
