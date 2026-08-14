"""The knowledge core's own routes, mounted under a prefix by the project.

Split out of Second Mind's project URLconf when the app moved here on
August 14, 2026. Login, logout and admin stayed behind: this project already has
all three, and a second login page would be two ways to sign in to one
application.

Everything is relative and every template reverses through `{% url %}`, so the
prefix the project chooses is not baked in anywhere. That matters more than
usual, because the prefix is temporary — the crossover ends with one capture
surface rather than two, and where these pages finally live is a decision for
that step rather than this one.
"""

from django.urls import path

from . import views
from .api import api

urlpatterns = [
    path("", views.capture, name="capture"),
    path("share/", views.share, name="share"),
    path(
        "commitments/<uuid:public_id>/",
        views.accept_commitment,
        name="accept_commitment",
    ),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("review/", views.review, name="review"),
    path("review/<uuid:public_id>/", views.resolve, name="resolve"),
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
    # Its own NinjaAPI instance rather than routers added to the task core's,
    # because the two define the same path: /api/v1/capture exists in both, one
    # for the Inbox and one as the mobile alias. That collision is the dual-write
    # question arriving early, and it is answered when facets land -- one capture
    # endpoint that writes a node and optionally a task. Until then they are kept
    # apart rather than merged badly.
    path("api/v1/", api.urls),
]
