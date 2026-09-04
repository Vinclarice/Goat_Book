"""The connection lab's data model.

Scope is the lab and nothing more (see docs/design-concept.md, "The first
deliverable is a connection lab"): capture, concepts, mentions, confirmed
edges, connection hypotheses, the append-only log, and instrumentation.
No facets, no planning, no recurrence.

Two things are deliberately *not* expressible here and live in
migration 0002 as raw SQL, because Django cannot state them:

  * the depth-one triggers for concept aliases and `member_of`
  * the append-only trigger on ActivityEvent

Cross-row and cross-table invariants that no constraint can express are listed
in docs/ddl-decisions.md and belong to the service layer, each with its own
test.
"""

import uuid

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Greatest, Least, Lower
from pgvector.django import HnswIndex, VectorField


class NodeSource(models.TextChoices):
    WEB = "web"
    MOBILE = "mobile"
    # DARK: never written. `/mind/share/` pre-fills the capture form and
    # deliberately does not save -- `views.share` argues that writing a note
    # from a link tap takes the decision away for no benefit -- so the person
    # submits it themselves and it is recorded as `WEB`. Which is honest: it
    # was a web capture. Trigger: a share target that writes without the form.
    SHARE = "share"
    IMPORT = "import"
    # DARK: never written. `/api/v1/capture` writes `MOBILE` or `WEB` from
    # `from_a_phone`, so even the API does not use this -- it is for a caller
    # that is neither, which today there is none of. Trigger: a token client
    # that is not the phone and not the SPA.
    API = "api"
    # A meta-node distilled from a confirmed thread. Distinct provenance worth
    # recording: it was not captured, it was concluded.
    THREAD = "thread"


class Node(models.Model):
    """A captured thing. Content, a time, a source — nothing else required."""

    Source = NodeSource  # ergonomic alias; Meta cannot see a nested class

    # Client-suppliable stable identity, and the idempotency guarantee: a
    # retried capture carrying the same public_id collides on this unique
    # column and the service returns the existing row rather than a second one.
    # It exists because offline clients create nodes, and identity cannot be
    # retrofitted onto records a device already holds.
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="nodes"
    )

    # Never mutated. Edits become Revisions; this stays what was first said.
    # Empty is legal — a node may be attachment-only. That a node has either
    # content or an attachment is a cross-table invariant, enforced in the
    # service layer.
    original_content = models.TextField(blank=True, default="")

    # When the thought happened, not when the row was written. These diverge on
    # every imported record, and conflating them makes every temporal detector
    # wrong on exactly the material most likely to trigger one.
    captured_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    source = models.CharField(max_length=16, choices=NodeSource)
    #: The external thing this note came out of, when it came out of one — S15.
    #:
    #: **Deliberately not called `source`**, which is taken and means something
    #: else: `NodeSource` is the *capture channel* — mobile, web, import —
    #: and S15's entry names that collision as the reason the story was
    #: impossible. Two fields called source, one a channel and one an article,
    #: is how a reader comes to believe the wrong one.
    #:
    #: `SET_NULL`: a note outlives the record of what it was read in.
    came_from = models.ForeignKey(
        "Source",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notes",
    )
    #: The sitting this fragment came out of, when it came out of one.
    #:
    #: **Provenance, not containment** -- Track D increment 13. A dump is not a
    #: container node, so the relation points this way and nothing points back
    #: as content: deleting the session record would leave every fragment
    #: exactly where it is, which is the test of whether it is content.
    #:
    #: `SET_NULL` for the same reason. A fragment outlives the record of how it
    #: arrived.
    session = models.ForeignKey(
        "CaptureSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fragments",
    )

    # Stable key from the source system, so re-running an import cannot
    # duplicate. Null for material captured directly.
    import_key = models.TextField(null=True, blank=True)

    archived_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    # Generated, so it cannot drift from its source the way a worker-maintained
    # index can. The two-argument to_tsvector is immutable; the one-argument
    # form is only stable and would be rejected in a generated column.
    search_original = models.GeneratedField(
        expression=SearchVector("original_content", config="english"),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    class Meta:
        constraints = [
            # Django's `choices` is validated by forms and full_clean(), never by
            # the database — an arbitrary string reaches the column untouched.
            # The raw DDL used native enums, so without this the Django
            # translation would silently enforce less than the SQL it replaced.
            # Every choice field in this module carries one of these.
            models.CheckConstraint(
                condition=Q(source__in=NodeSource.values), name="node_source_valid"
            ),
            models.CheckConstraint(
                condition=Q(import_key__isnull=True) | Q(source="import"),
                name="node_import_key_requires_import_source",
            ),
            models.UniqueConstraint(
                fields=["owner", "import_key"],
                condition=Q(import_key__isnull=False),
                name="node_import_key_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["owner", "-captured_at"],
                condition=Q(deleted_at__isnull=True, archived_at__isnull=True),
                name="node_live_captured_at",
            ),
            # GinIndex, not models.Index. A plain Index on a tsvector column is
            # created as btree, which is wrong twice over: it cannot serve the
            # `@@` predicate at all — every search fell back to a sequential
            # scan — and btree caps index entries at 2704 bytes, so **inserting a
            # note with a few hundred distinct lexemes fails outright**. A
            # 400-word journal entry could not be saved. That is a write-path
            # outage on precisely the material this system exists to hold.
            GinIndex(fields=["search_original"], name="node_search_original"),
        ]

    def __str__(self) -> str:
        return (self.original_content or "(attachment)")[:60]


class Revision(models.Model):
    """One snapshot of a node's body.

    Snapshots, not patches: mixing the two is a reliable reconstruction-bug
    source, and at this write volume the storage cost is irrelevant. A node's
    current body is its highest-`seq` revision, falling back to
    `original_content` when it has none.
    """

    node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="revisions")
    seq = models.PositiveIntegerField()
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    actor = models.CharField(max_length=64)

    search_body = models.GeneratedField(
        expression=SearchVector("body", config="english"),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(seq__gt=0), name="revision_seq_positive"),
            # Two concurrent revisions racing for one seq collide here rather
            # than silently interleaving; the service retries with seq + 1.
            models.UniqueConstraint(fields=["node", "seq"], name="revision_seq_unique"),
        ]
        indexes = [
            models.Index(fields=["node", "-seq"], name="revision_latest"),
            GinIndex(fields=["search_body"], name="revision_search_body"),
        ]

    def __str__(self) -> str:
        return f"{self.node_id}@{self.seq}"


class Source(models.Model):
    """Something you read, which notes can come out of — S15.

    **It earns a model on `architecture-trajectory.md` §4's test**, which the
    v3 plan's table did not cover:

    - **Its life cycle is unlike anything else here.** A source exists *before*
      any note about it, produces notes over years, and outlives every one of
      them. A `Node` is captured, revised, archived, deleted; a `Facet` is
      proposed, confirmed, retired; an `Item` is open then done. None of those
      is *a thing in the world you keep returning to*.
    - **A `Node` with a kind is the tempting answer and it is wrong.** A node is
      something *you wrote*, and S15's whole gap is that this starts with an
      article somebody else wrote.
    - **Unlike `MoneyLine` it is not a sidecar**, because there is no existing row
      for it to hang off.

    **`url` is text and nothing ever fetches it** — D7's answer already made:
    storing one is most of the value, and fetching reopens SSRF surface on a
    one-host deployment where the interesting targets are that host and the
    link-local metadata endpoint.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sources"
    )
    title = models.TextField()
    #: Text, never fetched. See the class docstring and D7.
    url = models.TextField(blank=True, default="")
    author = models.TextField(blank=True, default="")
    created_at = models.DateTimeField()

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            # One row per thing a person read. Coming back to an article a week
            # later and noting something else must not split what grew out of
            # it in half -- which is the whole value of the model.
            models.UniqueConstraint(
                fields=("owner", "url"),
                condition=~Q(url=""),
                name="source_url_unique_per_owner",
            ),
        ]

    def __str__(self):
        return self.title


class Decision(models.Model):
    """Something chosen over something else, and what would bring it back — S11.

    **Not hypothetical.** S11 says so itself: `architecture-trajectory.md` §7
    and §8 are exactly this practice, done in Markdown *because the product
    cannot hold it*.

    **Earns its own model**, and the v3 plan argued it: *decided → held →
    returns on condition → revisited or superseded* is unlike `Item`
    (open→done), `Facet` (proposed→confirmed→retired) or `Node`.

    **On citing, and a widening of the plan's constraint.** It says *"it must
    cite a `Revision`, not a `Node`, or a note edited in October silently
    changes what was on screen in August."* The concern is exactly right and a
    `Revision` cannot deliver it — one exists only for a note that has been
    *edited*, and `revise` got its first door on August 21, so almost no node
    has one and a decision could only cite a note somebody happened to rewrite.

    So this cites three ways at once, and each does a different job:

    - `cited_node` keeps **navigation**, which a snapshot alone loses.
    - `cited_text` is **the record**, immune to a later edit *and* to the note
      being deleted — the move this codebase already makes in
      `DailyFocus.task_text`, `WeeklyOutcome.project_title` and
      `Facet.cited_text`.
    - `cited_revision_seq` keeps **exactness** where there is a revision to be
      exact about, which is what the plan was reaching for.

    **`revisit_when` and `revisit_after` are not the same thing and neither
    replaces the other.** A named condition is what makes a decision honest and
    **nothing can check it**; a date is checkable and cruder. Recording only
    the date would lose the reason, and recording only the condition would mean
    nothing ever comes back on its own — so both, and the read says plainly
    which of the two it cannot act on.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="decisions"
    )
    question = models.TextField()
    chose = models.TextField()
    #: What else was on the table. **The half a note cannot keep**: six weeks
    #: later the alternatives are the part you have forgotten, and *what he
    #: considered at the time* is a third of S11's done-means.
    considered = models.TextField(blank=True, default="")

    #: The condition in words. Honest, and uncheckable by anything.
    revisit_when = models.TextField(blank=True, default="")
    #: A date, which is crude and is the only half a read can act on.
    revisit_after = models.DateField(null=True, blank=True)

    decided_at = models.DateTimeField()
    #: When it came back. A revisited decision stops being due; it is never
    #: deleted, because *what he considered at the time* needs the time to
    #: survive.
    revisited_at = models.DateTimeField(null=True, blank=True)
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="superseded_by",
    )

    cited_node = models.ForeignKey(
        Node,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decisions",
    )
    cited_text = models.TextField(blank=True, default="")
    cited_revision_seq = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ("-decided_at",)
        constraints = [
            models.CheckConstraint(
                condition=~Q(chose=""), name="decision_chose_something"
            ),
        ]

    def __str__(self):
        return self.question


class Attachment(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="attachments")
    kind = models.CharField(max_length=32)
    mime_type = models.CharField(max_length=127)
    byte_size = models.BigIntegerField()
    checksum = models.CharField(max_length=128)
    # **The bytes are a row** — Track D increment 16, and D9's answer.
    #
    # This said *bytes live in object storage* from the first slice, written
    # when nothing could create an attachment. D9 asked the question for real
    # and named the deciding consideration: export and deletion ship every
    # owned **row**, so a file that is not a row breaks two promises `/privacy/`
    # currently keeps. As a row, both hold without either knowing files exist —
    # and so does the restore drill, which would otherwise bring back a
    # database referencing objects that are not there.
    #
    # It also avoids a fourth processor. The policy says *three companies, each
    # doing one job*, and DigitalOcean's paragraph already says the database is
    # where everything Clarice stores lives.
    #
    # **Postgres is not a blob store, and that is the cost.** Right at this
    # scale — one person, a personal corpus, a managed backed-up database — and
    # wrong later. `services.MAX_ATTACHMENT_BYTES` is the pressure valve, and
    # the trigger for revisiting is that limit starting to hurt.
    # `default=b""` only so the column can be added: **the table is provably
    # empty**, because until this increment nothing anywhere could create an
    # `Attachment` -- `FileField`, `ImageField` and `request.FILES` appeared
    # nowhere in `src/`. The default never meets a real row, and
    # `attachment_has_content` stops it becoming a way to write one.
    content = models.BinaryField(default=b"")
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(byte_size__gte=0), name="attachment_size_non_negative"
            ),
            # An attachment with no bytes is metadata pretending to be a file,
            # and the `default=b""` above is the one way one could arrive.
            models.CheckConstraint(
                condition=~Q(content=b""), name="attachment_has_content"
            ),
        ]


class ConceptType(models.TextChoices):
    # What a rule-based extractor honestly knows: that a referent was named, not
    # what kind of thing it is. Guessing between person and place from
    # capitalisation alone would be a fabrication dressed as data; the person
    # supplies the type when they confirm, or leaves it.
    UNKNOWN = "unknown"
    PERSON = "person"
    PLACE = "place"
    OBJECT = "object"
    PROJECT = "project"
    ACTIVITY = "activity"
    MOTIF = "motif"


class ConceptCandidate(models.Model):
    """A referent two nodes can connect *through* — a person, place, motif.

    Its own model rather than a node plus a concept facet: there is no facet
    table in the lab, and proposed -> confirmed -> merged-as-alias is a
    genuinely different lifecycle from a captured thought's. The node+facet
    unification is destination shape; see docs/ddl-decisions.md.
    """

    Type = None  # replaced below; Meta cannot see a nested class

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="concepts"
    )
    label = models.TextField()
    concept_type = models.CharField(max_length=16, choices=ConceptType)

    # Null while this is only a proposal. Unconfirmed candidates are excluded
    # from the corpus that seeds further inference — without that rule the
    # classifier feeds on its own guesses and there is no correction path.
    confirmed_at = models.DateTimeField(null=True, blank=True)

    # An alias is a candidate merged into a canonical one: "my brother" merged
    # into "Bob". Depth is capped at 1 by trigger, so resolution is a single
    # join rather than a recursive walk.
    merged_into = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="aliases",
    )

    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(concept_type__in=ConceptType.values),
                name="concept_type_valid",
            ),
            models.CheckConstraint(
                condition=~Q(merged_into=F("id")), name="concept_no_self_merge"
            ),
            models.UniqueConstraint(
                "owner",
                Lower("label"),
                "concept_type",
                condition=Q(retired_at__isnull=True),
                name="concept_label_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["owner", "concept_type"],
                condition=Q(merged_into__isnull=True, retired_at__isnull=True),
                name="concept_canonical",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.label} ({self.concept_type})"


ConceptCandidate.Type = ConceptType


class InferenceOrigin(models.TextChoices):
    EXPLICIT = "explicit"
    INFERRED = "inferred"


class FacetKind(models.TextChoices):
    """What a facet gives a node.

    Open by design: new kinds are new values with their own validation, not new
    tables, because the set is expected to keep growing and a migration per kind
    would make adding one a decision rather than a note.
    """

    ACTIONABLE = "actionable", "Actionable"

    # --- Memory roles, Track B increment 6 and D6's answer -----------------
    #
    # **What kind of memory is this** -- Part 2's first axis. One value per
    # role rather than one `ROLE` kind with the name in `data`, and a
    # constraint decides it rather than taste: `facet_one_live_per_kind` is
    # `unique(node, kind)` over live facets, so a single kind could hold
    # exactly one role, and a memory is several things at once. *A recipe that
    # is also from Mum, also for Christmas.*
    #
    # Unlike every kind above them these carry **no data and no validation**.
    # That is the difference between a capability and a description: being
    # actionable gives a note a due date and a task, and being a recipe gives
    # it nothing except an answer to what it is.
    #
    # **Six of the brief's fourteen**, and the rest are values away rather
    # than work away -- which is what "open by design" buys. Shipping all
    # fourteen with nothing proposing any of them would be the dark seam this
    # project keeps rediscovering, times fourteen.
    # Track C increment 11. **One kind, unlike the roles below**, and the
    # difference is which constraint applies: entry facets are unique by
    # `(entry, fingerprint)` and deliberately not one per kind, so a day can
    # carry several observations without needing a value each. The namespaced
    # name lives in `data`, which is what Part 3 means by "this needs no new
    # model".
    OBSERVATION = "observation", "Observation"

    RECIPE = "recipe", "Recipe or procedure"
    OCCASION = "occasion", "Occasion or birthday"
    DREAM = "dream", "Dream"
    FEAR = "fear", "Fear"
    DESIRE = "desire", "Something I want"
    PREFERENCE = "preference", "Preference"
    # DARK: never written. Ten of the twelve roles have something that proposes
    # them; these two do not, which is the docstring's own warning above coming
    # true at a scale of two rather than fourteen. Trigger: an extractor that
    # proposes it, or a person's facet surface offering it.
    MEDIA = "media", "Media"
    GOAL = "goal", "Goal"
    EPISTEMIC = "epistemic", "Epistemic status"
    # DARK: never written. See `MEDIA` above -- these are the two of twelve
    # roles nothing proposes. Trigger: an extractor that proposes it, or a
    # person's facet surface offering it.
    CONCEPT = "concept", "Concept"


def entry_body(entry) -> str:
    """A journal entry's three fields as one string, for spans to index into.

    **Defined once, because two definitions would silently disagree.** The
    producer computes offsets against this and `Facet.cited_text` reads them
    back out of it; if the two ever joined the fields differently, every quote
    would come back shifted from the sentence that actually caused the
    proposal — and it would look like a parser bug rather than an alignment
    one.

    Empty fields are dropped rather than joined as blanks, so a day with only
    happenings has offsets starting at zero instead of after two newlines
    nobody wrote.
    """
    return "\n".join(
        part
        for part in (entry.intentions, entry.gratitude, entry.happenings)
        if part
    )


class CaptureSession(models.Model):
    """One sitting of emptying your head — Track D increment 13.

    **Earns its own model** by `architecture-trajectory.md` §4's test, and the
    v3 plan says why in one line: *a session has duration, completion state, a
    budget, prompt provenance and a processing flag. A shared timestamp carries
    none of them.*

    **A dump is not a container node**, which is the distinction this exists to
    keep. `NodeSource.THREAD` is a semantic conclusion distilled from several
    memories and participates in the graph; a session is provenance and does
    not. Nothing searches a session, nothing links to one, and retiring it
    would leave every fragment exactly where it is.

    `processed_at` is a stored flag rather than an inference, and rule 7 is the
    reason: *the next maintenance run cannot process its forty nodes
    independently and walk straight around the cap.* A cap that a nightly pass
    can step around is not a cap.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="capture_sessions",
    )
    started_at = models.DateTimeField()
    #: When the producers ran over it, once. Null means the sitting is still
    #: open or was abandoned -- and an abandoned session is not a failure:
    #: every fragment in it was saved as it was typed.
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-started_at",)

    def __str__(self):
        return f"{self.owner}: {self.started_at:%Y-%m-%d %H:%M}"


class Facet(models.Model):
    """A capability a node carries, without being filed as it.

    A node may have several at once or none, and capture never asks. That is the
    design's answer to a promotion path whose terminus was a task: everything
    inside such a path inherits a direction, and a facet has none.

    `data` is JSONB validated per kind rather than a column per kind. The
    threshold for promoting a kind's fields to real columns is not defined yet
    and is deliberately left open; what is not open is that a facet nobody
    queries hard should not cost a migration.

    **Completion is not stored here.** It is a `completed` event on the log, and
    anything showing completion state is a projection over that. Two places
    recording whether a thing is done is how they come to disagree.
    """

    # Exactly one of these two, enforced below. A facet cites the thing it was
    # read out of, and until August 19, 2026 that could only be a Node --
    # which meant the journal, where most writing in this product actually
    # happens, could not carry a proposal at all.
    #
    # The alternative was minting a Node from a `DailyEntry` on confirmation,
    # and it was refused: the same sentence would live in two places and the
    # journal would quietly become a second capture surface, which is the
    # thing Heron deleted. `task` below already crosses into `lists`, so
    # crossing into `daily` is the same move rather than a new kind of one.
    # `planning-assistant-plan.md` increment 2.
    node = models.ForeignKey(
        Node, null=True, blank=True, on_delete=models.CASCADE, related_name="facets"
    )
    entry = models.ForeignKey(
        "daily.DailyEntry",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="facets",
    )
    kind = models.CharField(max_length=16, choices=FacetKind)
    data = models.JSONField(default=dict, blank=True)

    # Which producer proposed this — the shared contract's first field, and what
    # makes its sixth mean anything. A blended "are suggestions good" number
    # cannot answer the question that matters, which is *which* producer is
    # worth hearing from; `ConnectionHypothesis.detector` has said so from the
    # start and facets said nothing at all.
    #
    # **Two commitment producers, not one.** Capture fires on a date, the
    # journal on an undertaking. They read different material with different
    # signals and their false positives look nothing alike, so averaging them
    # would hide exactly what attribution exists to show.
    #
    # Blank for a facet nothing proposed — an explicitly attached one — rather
    # than a sentinel producer that would then appear in the readings as though
    # something had guessed.
    producer = models.CharField(max_length=48, blank=True, default="")

    # The cited passage, as offsets into the source's text. `reason` says why
    # this was proposed; these say *where*, which is what makes the claim
    # checkable rather than merely explained -- the same span-level citation
    # `HypothesisMember` has carried from the start, arriving here as the
    # contract's cited-evidence field.
    span_start = models.PositiveIntegerField(null=True, blank=True)
    span_end = models.PositiveIntegerField(null=True, blank=True)

    # Stable hash of the source, span and text. Unique per entry across *every*
    # state including retired, because a journal entry is edited all day: a
    # fingerprint that only excluded live facets would re-propose on each save
    # the thing dismissed an hour earlier, which is precisely how a surface
    # teaches somebody to skim it. `ConnectionHypothesis.fingerprint` follows
    # the same rule for the same reason.
    #
    # Null for node-backed facets, which have the one-per-kind constraint below
    # instead: a capture is one thought, so it cannot carry two of a kind.
    fingerprint = models.CharField(max_length=64, null=True, blank=True)

    # The same provenance columns every proposal in this system carries. A facet
    # with origin=inferred and confirmed_at NULL is soft-applied: visible,
    # labelled, dismissible, and not ground truth for anything downstream.
    origin = models.CharField(max_length=16, choices=InferenceOrigin)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)

    # The commitment this facet materialised, for the actionable kind only.
    #
    # A real foreign key rather than an id in `data`, because the invariant --
    # a confirmed actionable facet always has a live task -- is only checkable
    # if the database knows about the relationship. SET_NULL rather than CASCADE:
    # deleting a task should not delete the thought it came from, and a facet
    # left pointing at nothing is exactly what the reconciliation count is for.
    task = models.ForeignKey(
        "lists.Item",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mind_facets",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=[k for k, _ in FacetKind.choices]),
                name="facet_kind_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(origin__in=[o for o, _ in InferenceOrigin.choices]),
                name="facet_origin_valid",
            ),
            # One facet of a kind per node, so a second proposal updates rather
            # than accumulates. Retired ones are excluded so a dismissed facet
            # can be proposed again later on new evidence.
            models.UniqueConstraint(
                fields=["node", "kind"],
                condition=models.Q(retired_at__isnull=True),
                name="facet_one_live_per_kind",
            ),
            # Exactly one source. A facet citing neither is evidence for
            # nothing; one citing both makes "where did this come from"
            # ambiguous at the moment somebody is deciding whether to trust it.
            models.CheckConstraint(
                condition=(
                    models.Q(node__isnull=False, entry__isnull=True)
                    | models.Q(node__isnull=True, entry__isnull=False)
                ),
                name="facet_cites_exactly_one_source",
            ),
            # **Not** one per (entry, kind): a capture is one thought, but a
            # day's writing may carry three separate promises, and copying the
            # node rule across would let a Tuesday propose one of them and drop
            # the rest silently.
            models.UniqueConstraint(
                fields=["entry", "fingerprint"],
                name="facet_entry_fingerprint_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(span_start__isnull=True, span_end__isnull=True)
                | models.Q(span_start__isnull=False, span_end__isnull=False),
                name="facet_span_paired",
            ),
            models.CheckConstraint(
                condition=models.Q(span_start__isnull=True)
                | models.Q(span_end__gt=models.F("span_start")),
                name="facet_span_ordered",
            ),
        ]
        indexes = [
            models.Index(fields=["node", "kind"]),
            models.Index(fields=["entry", "kind"], name="facet_by_entry"),
        ]

    def __str__(self):
        return f"{self.kind} on {self.node_id or self.entry_id}"

    @property
    def owner(self):
        """Whose facet this is, whichever source it cites.

        One accessor because every existing caller reaches through
        `facet.node.owner`, and every one of them would break on an
        entry-backed facet. Resolving it here is cheaper and safer than
        teaching each call site which kind it is holding.
        """
        return self.node.owner if self.node_id else self.entry.owner

    @property
    def cited_text(self) -> str:
        """The passage this was read out of, or the whole source if unspanned.

        The evidence itself rather than a description of it. A proposal that
        cannot show its own sentence is asking to be trusted, which is the one
        thing every other producer here refuses to do.
        """
        body = (
            self.node.original_content if self.node_id else entry_body(self.entry)
        )
        if self.span_start is None:
            return body
        return body[self.span_start : self.span_end]


class Mention(models.Model):
    """A node refers to a concept, optionally at a specific span."""

    node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="mentions")
    concept = models.ForeignKey(
        ConceptCandidate, on_delete=models.CASCADE, related_name="mentions"
    )

    span_start = models.PositiveIntegerField(null=True, blank=True)
    span_end = models.PositiveIntegerField(null=True, blank=True)

    origin = models.CharField(max_length=16, choices=InferenceOrigin)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    index_version = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(origin__in=InferenceOrigin.values), name="mention_origin_valid"
            ),
            models.CheckConstraint(
                condition=Q(span_start__isnull=True, span_end__isnull=True)
                | Q(span_start__isnull=False, span_end__isnull=False),
                name="mention_span_paired",
            ),
            models.CheckConstraint(
                condition=Q(span_start__isnull=True) | Q(span_end__gt=F("span_start")),
                name="mention_span_ordered",
            ),
            # nulls_distinct=False is the whole point: a node-level mention has
            # both spans null, and standard SQL would happily accept it twice.
            # Postgres 15+ only — SQLite omits this class of constraint in
            # silence, which is why the suite runs on Postgres.
            models.UniqueConstraint(
                fields=["node", "concept", "span_start", "span_end"],
                nulls_distinct=False,
                name="mention_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["concept", "node"], name="mention_by_concept"),
            models.Index(
                fields=["concept"],
                condition=Q(confirmed_at__isnull=False),
                name="mention_confirmed",
            ),
        ]


class EdgeRelation(models.TextChoices):
    """Only what v1 produces or a person can create by hand.

    `supports` and `source_for` from the design document are omitted: no
    detector produces them and no manual need has been demonstrated. The last
    three exist because recording evolving thought is a manual act — which is
    the actual argument for typed relations rather than one untyped link.
    """

    RELATES_TO = "relates_to"
    ANSWERS = "answers"
    MEMBER_OF = "member_of"
    # The three the docstring above means by "a manual act". Dark until August
    # 26, 2026 -- declared with a trigger on the 24th, and the trigger fired two
    # days later when the note page got the form that writes them.
    CONTRADICTS = "contradicts"
    SUPERSEDES = "supersedes"
    DEVELOPED_FROM = "developed_from"


class Edge(models.Model):
    """A confirmed relation. Nothing unconfirmed is written here."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="edges"
    )
    from_node = models.ForeignKey(
        Node, on_delete=models.CASCADE, related_name="edges_out"
    )
    to_node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="edges_in")
    relation = models.CharField(max_length=20, choices=EdgeRelation)
    origin = models.CharField(max_length=16, choices=InferenceOrigin)
    confidence = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(relation__in=EdgeRelation.values), name="edge_relation_valid"
            ),
            models.CheckConstraint(
                condition=Q(origin__in=InferenceOrigin.values), name="edge_origin_valid"
            ),
            models.CheckConstraint(
                condition=~Q(from_node=F("to_node")), name="edge_no_self_link"
            ),
            models.CheckConstraint(
                condition=Q(confidence__isnull=True)
                | Q(confidence__gte=0, confidence__lte=1),
                name="edge_confidence_range",
            ),
            models.UniqueConstraint(
                fields=["from_node", "to_node", "relation"], name="edge_directed_unique"
            ),
            # relates_to has no direction, so A->B and B->A are one fact.
            # Normalising the pair prevents storing it twice; reads union both
            # columns.
            models.UniqueConstraint(
                Least("from_node", "to_node"),
                Greatest("from_node", "to_node"),
                condition=Q(relation="relates_to"),
                name="edge_symmetric_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["from_node", "relation"], name="edge_from"),
            models.Index(fields=["to_node", "relation"], name="edge_to"),
        ]


class HypothesisResolution(models.TextChoices):
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"
    EXPIRED = "expired"
    # DARK: never written. `confirm_hypothesis` and `dismiss_hypothesis` write
    # the first two and `expire_stale_hypotheses` the third; nothing renames a
    # hypothesis, so nothing resolves one this way. Trigger: a path that renames
    # a hypothesis rather than confirming or dismissing it.
    #
    # `EXPIRED` above is a **different** and worse case, already declared at
    # `mind/instrumentation.py` -- it has three writers and all three are
    # themselves dark, which is why `/numbers/` reported an `expired` count
    # that was structurally zero. Not catchable here: a scan cannot tell a
    # write from a read.
    RENAMED = "renamed"


class ConnectionHypothesis(models.Model):
    """A modest claim with visible evidence — never a fact.

    One model for both the pairwise and n-ary cases: a pairwise hypothesis is a
    two-member one, and the review surface queries them identically.
    """

    Resolution = HypothesisResolution  # ergonomic alias

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hypotheses"
    )

    # Which detector produced this. Attribution is what makes per-detector
    # accept rates possible, and a blended "are suggestions good" number
    # cannot answer the question that matters.
    detector = models.CharField(max_length=48)
    relation = models.CharField(
        max_length=20, choices=EdgeRelation, null=True, blank=True
    )
    concept = models.ForeignKey(
        ConceptCandidate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="hypotheses",
    )

    confidence = models.FloatField()

    # Extractive by default: the mediating concept, or distinguishing terms.
    label = models.TextField()
    # Null in v1 — no generative producer exists yet. Articulation arrives with
    # the motif detectors, is user-initiated, and never becomes durable.
    claim_text = models.TextField(null=True, blank=True)

    index_version = models.CharField(max_length=32)

    # Stable hash of detector + sorted member public_ids + relation, unique per
    # owner across *all* hypotheses including resolved ones. Without it a batch
    # run re-proposes everything already dismissed, forever: dedupe has to be
    # against everything seen, not against what was confirmed.
    fingerprint = models.CharField(max_length=64)

    # Injected, not auto_now_add. Expiry logic reads this field to decide
    # staleness, which makes it domain state rather than audit metadata — and
    # anything the domain reads must be passed in, or a batch job cannot be
    # replayed for a specific day and a test depends on when it runs.
    # Contrast Node.created_at, which nothing reads and may stay automatic.
    created_at = models.DateTimeField()

    # Silence is not consent. The review window is anchored to the moment the
    # hypothesis was actually shown, never to creation — otherwise "undismissed"
    # means "unseen" and inaction ripens into acceptance.
    first_surfaced_at = models.DateTimeField(null=True, blank=True)
    surface_count = models.PositiveIntegerField(default=0)
    review_window_expires_at = models.DateTimeField(null=True, blank=True)

    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution = models.CharField(
        max_length=16, choices=HypothesisResolution, null=True, blank=True
    )

    class Meta:
        verbose_name_plural = "connection hypotheses"
        constraints = [
            models.CheckConstraint(
                condition=Q(relation__isnull=True)
                | Q(relation__in=EdgeRelation.values),
                name="hypothesis_relation_valid",
            ),
            models.CheckConstraint(
                condition=Q(resolution__isnull=True)
                | Q(resolution__in=HypothesisResolution.values),
                name="hypothesis_resolution_valid",
            ),
            models.CheckConstraint(
                condition=Q(confidence__gte=0, confidence__lte=1),
                name="hypothesis_confidence_range",
            ),
            models.UniqueConstraint(
                fields=["owner", "fingerprint"], name="hypothesis_fingerprint_unique"
            ),
            models.CheckConstraint(
                condition=Q(review_window_expires_at__isnull=True)
                | Q(first_surfaced_at__isnull=False),
                name="hypothesis_window_requires_surfacing",
            ),
            models.CheckConstraint(
                condition=Q(first_surfaced_at__isnull=True, surface_count=0)
                | Q(first_surfaced_at__isnull=False, surface_count__gt=0),
                name="hypothesis_surface_count_agrees",
            ),
            models.CheckConstraint(
                condition=Q(resolved_at__isnull=True, resolution__isnull=True)
                | Q(resolved_at__isnull=False, resolution__isnull=False),
                name="hypothesis_resolution_paired",
            ),
        ]
        indexes = [
            models.Index(
                fields=["owner", "-confidence"],
                condition=Q(resolved_at__isnull=True),
                name="hypothesis_open",
            ),
            models.Index(
                fields=["owner", "detector", "resolution"],
                name="hypothesis_by_detector",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.detector}: {self.label}"


class HypothesisMember(models.Model):
    """One node's contribution to a hypothesis, cited at the span level.

    Span-level rather than node-level citation is what makes "assert only what
    the cited passages show" checkable: the evidence is the sentence, not the
    whole note.

    A hypothesis needs at least two members. That is a cross-row aggregate, so
    it lives in the service layer with its own test.
    """

    hypothesis = models.ForeignKey(
        ConnectionHypothesis, on_delete=models.CASCADE, related_name="members"
    )
    node = models.ForeignKey(
        Node, on_delete=models.CASCADE, related_name="hypothesis_memberships"
    )
    span_start = models.PositiveIntegerField(null=True, blank=True)
    span_end = models.PositiveIntegerField(null=True, blank=True)
    contribution_reason = models.TextField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["hypothesis", "node"], name="hypothesis_member_unique"
            ),
            models.CheckConstraint(
                condition=Q(span_start__isnull=True, span_end__isnull=True)
                | Q(span_start__isnull=False, span_end__isnull=False),
                name="hypothesis_member_span_paired",
            ),
            models.CheckConstraint(
                condition=Q(span_start__isnull=True) | Q(span_end__gt=F("span_start")),
                name="hypothesis_member_span_ordered",
            ),
        ]
        indexes = [
            models.Index(fields=["node"], name="hypothesis_member_by_node"),
        ]


class EventType(models.TextChoices):
    CAPTURED = "captured"
    REVISED = "revised"
    CONCEPT_PROPOSED = "concept_proposed"
    CONCEPT_CONFIRMED = "concept_confirmed"
    CONCEPT_RETIRED = "concept_retired"
    FACET_PROPOSED = "facet_proposed"
    FACET_CONFIRMED = "facet_confirmed"
    FACET_DISMISSED = "facet_dismissed"
    ALIAS_MERGED = "alias_merged"
    MENTION_PROPOSED = "mention_proposed"
    MENTION_CONFIRMED = "mention_confirmed"
    EDGE_CREATED = "edge_created"
    EDGE_REMOVED = "edge_removed"
    HYPOTHESIS_PROPOSED = "hypothesis_proposed"
    HYPOTHESIS_SURFACED = "hypothesis_surfaced"
    HYPOTHESIS_RESOLVED = "hypothesis_resolved"
    THREAD_ARTICULATED = "thread_articulated"
    REVIEWED = "reviewed"
    IMPORTED = "imported"
    ARCHIVED = "archived"
    DELETED = "deleted"
    PURGED = "purged"
    #: A scheduled maintenance pass completed for this owner. Owner-scoped and
    #: node-less, unlike everything above it -- the subject is the corpus, not
    #: any one note. It exists so `/numbers/` can tell "ran and found nothing"
    #: from "never ran", which no amount of counting rows can distinguish.
    MAINTENANCE_RAN = "maintenance_ran"

    # ------------------------------------------------------------------
    # Life events -- `temporal-substrate-plan.md` Track A increment 1.
    #
    # Everything above this line is about a note, which is the finding that
    # opened the substrate brief: the most carefully guarded structure in the
    # codebase was a note log, not a life log. The right structure with the
    # wrong vocabulary.
    #
    # **Facts, not derivations.** "This commitment was released on the 14th"
    # is a fact and belongs in an append-only row. "This project is stalling"
    # is a derivation and stays computed on demand, the way `review` does
    # today. Nothing here may record a thing a read could have produced --
    # which is what keeps Part 4's refusal of an event bus standing.
    #
    # **Scoped to where a durable decision already exists**, and deliberately
    # no wider: routine occurrences, project pause and resume, area changes,
    # and every task-field edit that is not a change of commitment are
    # deferred by name. A log recording every keystroke of a task's text is a
    # log nobody can read.
    #
    # Distinct from `ARCHIVED` and `DELETED` above rather than reusing them.
    # Those name a note's fate, and one value meaning two things is a value no
    # reading can filter on.
    # ------------------------------------------------------------------

    #: A commitment was met. The single most load-bearing fact in the task
    #: core, and until now the log could not say it.
    TASK_COMPLETED = "task_completed"
    #: ...and un-met. Without this the log asserts a completion it can never
    #: retract, so any projection folded over it drifts the first time
    #: somebody ticks the wrong row.
    TASK_REOPENED = "task_reopened"
    TASK_ARCHIVED = "task_archived"

    #: The recurring undertaking behind a task changed shape, or ended. Not
    #: every edit -- the cadence and the undertaking itself, which is what
    #: "its commitment changes" means in the brief's scope sentence.
    COMMITMENT_CHANGED = "commitment_changed"
    COMMITMENT_ENDED = "commitment_ended"
    #: Stopped carrying something without doing it --
    #: `superlists-2.0-plan.md` rule 8's *let go*.
    #:
    #: **Not `TASK_ARCHIVED`, and the difference is the whole point.**
    #: `archive_item` writes that one for filing a finished task too, so a
    #: count over it cannot tell tidying from abandoning -- and the weekly
    #: review reports lines let go precisely because it is *"a better number
    #: than lines open"*. Both rows are written: the archive happened, and so
    #: did the decision.
    TASK_LET_GO = "task_let_go"

    #: A day was planned, and un-planned. `DailyFocus` records what somebody
    #: *chose*, and `released_at` is how a pin ends -- so these two are what
    #: let a decommitment be told from a failure, which is the distinction the
    #: whole review block is built on.
    FOCUS_PINNED = "focus_pinned"
    FOCUS_RELEASED = "focus_released"

    #: The week-grained decisions. Subject-less like `MAINTENANCE_RAN`: a week
    #: is neither a task nor a day's entry, and inventing a subject column for
    #: one cadence would be a column the next cadence does not fit.
    WEEK_REVIEWED = "week_reviewed"
    INTENTION_SET = "intention_set"
    OUTCOME_CHOSEN = "outcome_chosen"


class EventOrigin(models.TextChoices):
    """Whether the log was there, or is re-presenting a time it found later.

    `temporal-substrate-plan.md` **D2**, answered August 20, 2026. The task
    core already held years of history the log never saw, and increment 3
    reconstructs what carries its own recorded timestamp -- so a reading needs
    to tell a record from a re-presentation, and `Facet.origin`'s split is the
    shape this copies.

    **A column rather than a payload key.** Every read over the log will want
    to label or exclude reconstructions, and a JSONB lookup with no index is
    not what that should cost. The log is append-only, so the cheap choice
    would have been the unfixable one.

    Distinct from `InferenceOrigin` and deliberately not reusing it: that one
    says whether somebody stated a thing or the system inferred it, which is a
    question about *content*. This is a question about *witness*.
    """

    #: The log was there. Something called `clarice.life_log.record` at the
    #: moment the thing happened.
    RECORDED = "recorded"
    #: Reconstructed from a timestamp already stored against the thing itself.
    #: Honest about *when*, and silent about everything the row does not keep
    #: -- which is why increment 3 reconstructs so much less than happened.
    RECONSTRUCTED = "reconstructed"


class ActivityEvent(models.Model):
    """The one append-only log.

    Append-only is enforced by trigger, not intention (migration 0002). Folded
    projections — review schedules now, goal state after absorption — are only
    trustworthy if the log genuinely cannot be edited.

    `schema_version` is scoped to `event_type`. Old payloads are never migrated
    in place; upcasters are written only when a replay path needs to read across
    a version boundary. One column now, unaddable later without guessing at
    what old rows meant.
    """

    Type = None  # replaced below; Meta cannot see a nested class

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="events"
    )
    # A non-constraining reference, deliberately. An append-only log cannot
    # participate in any referential action: CASCADE, SET_NULL and SET_DEFAULT
    # are each a *mutation* of the log, which the append-only trigger refuses —
    # so a real FK would make any node with events undeletable, and every node
    # has events. PROTECT would forbid deletion outright, contradicting "real
    # deletion, not just hidden".
    #
    # This is also the semantically correct shape: an event asserts what
    # happened, not what currently exists, so it may legitimately point at
    # material since purged. Readers must tolerate a dangling node_id; the
    # retention policy purges a node's events explicitly rather than by cascade.
    node = models.ForeignKey(
        Node,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="events",
    )

    # The two subject references `Facet` already carries, arriving here for the
    # same reason they arrived there: this is where the writing actually
    # happens. **Every word of the `node` comment above applies unchanged** --
    # non-constraining because a cascade is a mutation of the log and the
    # trigger refuses one, so a real foreign key would make any task with
    # events undeletable, and under increment 2 every completed task has one.
    #
    # **Foreign keys rather than ids in `payload`.** `around()` is the read all
    # of this exists for and it joins; an id buried in JSON cannot be indexed
    # or joined, and D3's payload-versus-reference question is about the
    # *snapshot*, not about the subject.
    #
    # **No exactly-one constraint, unlike `Facet`.** A facet citing two sources
    # makes "where did this come from" ambiguous at the moment somebody is
    # deciding whether to trust it. An event citing two subjects is not
    # ambiguous: `confirm_actionable` turns a thought into a commitment, and
    # that event honestly has both. Subject-less stays legal too --
    # `MAINTENANCE_RAN` shipped that way and a reviewed week has neither.
    task = models.ForeignKey(
        "lists.Item",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="events",
    )
    entry = models.ForeignKey(
        "daily.DailyEntry",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="events",
    )
    event_type = models.CharField(max_length=32, choices=EventType)
    # Defaulted, so every row that predates the question is what it says it is:
    # each one was written by something calling `record` as it happened.
    origin = models.CharField(
        max_length=16, choices=EventOrigin, default=EventOrigin.RECORDED
    )
    schema_version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField(default=dict)
    occurred_at = models.DateTimeField()
    actor = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(event_type__in=EventType.values), name="event_type_valid"
            ),
            models.CheckConstraint(
                condition=Q(origin__in=EventOrigin.values), name="event_origin_valid"
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "-occurred_at"], name="event_timeline"),
            models.Index(
                fields=["node", "event_type", "occurred_at"], name="event_by_node"
            ),
            # The same shape as `event_by_node`, for the same read. A subject
            # column nothing can seek on is a subject column that pushes every
            # life-event query into a sequential scan of the whole log.
            models.Index(
                fields=["task", "event_type", "occurred_at"], name="event_by_task"
            ),
            models.Index(
                fields=["entry", "event_type", "occurred_at"], name="event_by_entry"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event_type}@{self.occurred_at:%Y-%m-%d}"


ActivityEvent.Type = EventType


class SentenceEmbedding(models.Model):
    """One sentence of one node, as a vector.

    Sentence-level rather than one vector per note, and that is the whole point.
    Measured against a corpus with known answers, whole-document embeddings scored
    **0% precision** at usable volume: every note is the same register, so document
    cosine mostly reports how alike two pieces of first-person prose are. Scoring a
    pair by its best-matching *sentence* pair reached 67% — because a real forgotten
    connection is one sentence in each note about the same concern, surrounded by
    material that has nothing to do with it, and averaging destroys exactly that
    signal. See docs/embedding-shadow-evaluation.md.

    The span is not incidental. It means a proposal can quote the two sentences that
    matched, which is stronger evidence than any score: the person reads the
    sentences and judges, rather than trusting a number.

    `index_version` is stamped on every row, so changing the model is a re-embedding
    migration rather than a silent drift in what "similar" meant when a suggestion
    was made. The vector dimension is fixed by the column, so a model of a different
    size needs a migration too — which is honest about the cost rather than hiding
    it behind a nullable column.
    """

    DIMENSIONS = 384  # all-MiniLM-L6-v2

    node = models.ForeignKey(
        Node, on_delete=models.CASCADE, related_name="sentence_embeddings"
    )
    seq = models.PositiveIntegerField()
    span_start = models.PositiveIntegerField()
    span_end = models.PositiveIntegerField()
    embedding = VectorField(dimensions=DIMENSIONS)
    index_version = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["node", "index_version", "seq"], name="sentence_unique_per_model"
            ),
            models.CheckConstraint(
                condition=Q(span_end__gt=F("span_start")), name="sentence_span_ordered"
            ),
        ]
        indexes = [
            models.Index(fields=["index_version"], name="sentence_by_model"),
            # HNSW over cosine distance. Built now because it is cheap on a small
            # table and awkward to add under load later.
            HnswIndex(
                name="sentence_vector_hnsw",
                fields=["embedding"],
                opclasses=["vector_cosine_ops"],
                m=16,
                ef_construction=64,
            ),
        ]

    def __str__(self) -> str:
        return f"{self.node_id}#{self.seq}"


# `ApiToken` stood here: a long-lived bearer token for a native client, with its
# own `sm_` prefix, its own hash-only storage and its own resolver in
# `mind/auth.py`. It was built so the Android app could point at a separate
# Second Mind server by changing one build property.
#
# **It never was.** No shipped build set `secondMindBaseUrl`, so the phone always
# talked to the task core, and these pages carry no JavaScript, so nothing here
# called it either. Deleted August 15, 2026 with `/mind/api/v1/`, holding zero
# rows in production — counted before the table was dropped, because afterwards
# there is nothing left to ask. See `migrations/0014_delete_apitoken`.
#
# The application has one token table, `accounts.PersonalAccessToken`, and it
# has scopes, which this never did. Two token tables over one user table was
# merger residue rather than a design.


class MissContext(models.TextChoices):
    SEARCH = "search"
    # DARK: never written. The two miss buttons that exist are the search page's
    # and the note page's, which write `SEARCH` and `RECOLLECTION`. There is
    # none on the capture surface, which is what this value is for -- *I came
    # here to write something down and could not find what it was about.*
    # Trigger: a miss button on the capture surface.
    CAPTURE = "capture"
    # Track B increment 10, and the source D8 registered on August 21: the
    # search page's miss button, borrowed verbatim onto the note page --
    # *"there was more to that morning."* One value, and Recollection has the
    # only other honest failure signal in the project.
    RECOLLECTION = "recollection"


class RetrievalMiss(models.Model):
    """Where the person's own memory beat the index.

    The strongest evidence available about whether semantic retrieval is
    needed, because the correct answer is known. Vocabulary drift shows up
    here first and nowhere else.
    """

    Context = MissContext  # ergonomic alias

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="misses"
    )
    query_text = models.TextField()
    context = models.CharField(max_length=16, choices=MissContext)
    # Injected for the same reason as ConnectionHypothesis.created_at: the
    # retirement gate asks whether misses fall *over time*, so this is measured
    # state, not incidental metadata.
    created_at = models.DateTimeField()
    # Set if the node is later found, which makes the miss diagnosable.
    #
    # **Nothing has ever set this.** `services.resolve_retrieval_miss` is its
    # only writer and has no caller outside its own tests; nothing reads the
    # column at all. Recorded here rather than removed because the *idea* is
    # sound and the field costs nothing -- but it is a seam that was never
    # switched on, and `search-plan.md` D3 was framed around widening it before
    # anybody checked. Widen it when something populates it.
    resolved_node = models.ForeignKey(
        Node, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # What each section of the search actually returned, at the moment the
    # button was pressed. `search-plan.md` D3, August 20, 2026.
    #
    # A miss used to need no such thing: `/mind/search/` searched notes and
    # only notes, so every miss was a note-retrieval failure by construction.
    # Increment 3 put the same button under three sections and made a bare miss
    # ambiguous -- and a miss cannot be re-interpreted afterwards, which is why
    # these arrived before the deploy rather than after it.
    #
    # **Null means "recorded before this existed", which means notes-only**, and
    # `retrieval_miss_trend` counts those. Reading null as "the notes section
    # had results" would silently drop every miss recorded up to this date out
    # of the gate they were collected for.
    #
    # Totals rather than booleans, at the same cost: "the index returned
    # nothing" and "it returned thirty and none was right" are different
    # evidence, and only the first answers the embeddings question.
    notes_found = models.PositiveIntegerField(null=True, blank=True)
    tasks_found = models.PositiveIntegerField(null=True, blank=True)
    days_found = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "retrieval misses"
        constraints = [
            models.CheckConstraint(
                condition=Q(context__in=MissContext.values), name="miss_context_valid"
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "-created_at"], name="miss_recent"),
        ]
