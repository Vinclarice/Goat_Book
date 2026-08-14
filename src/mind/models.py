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

import hashlib
import secrets
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
    SHARE = "share"
    IMPORT = "import"
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


class Attachment(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="attachments")
    kind = models.CharField(max_length=32)
    mime_type = models.CharField(max_length=127)
    byte_size = models.BigIntegerField()
    checksum = models.CharField(max_length=128)
    # Bytes live in object storage; this row is the metadata and the thing the
    # graph references. A purge removes both.
    storage_key = models.TextField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(byte_size__gte=0), name="attachment_size_non_negative"
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
    event_type = models.CharField(max_length=32, choices=EventType)
    schema_version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField(default=dict)
    occurred_at = models.DateTimeField()
    actor = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(event_type__in=EventType.values), name="event_type_valid"
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "-occurred_at"], name="event_timeline"),
            models.Index(
                fields=["node", "event_type", "occurred_at"], name="event_by_node"
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


class ApiToken(models.Model):
    """A long-lived bearer token, for a client that cannot hold a session cookie.

    Session authentication covers a browser, including a phone browser, but a native
    client needs a credential it can store and present. This is that.

    **Only a hash is stored.** The token is shown once, at issue, and never again —
    a leaked database yields no working credentials. SHA-256 rather than a slow KDF
    is deliberate and not a shortcut: the secret is 256 bits of CSPRNG output, so
    there is no low-entropy password to brute-force, and a per-request bcrypt would
    put a deliberate delay on the capture path, which is the one path that must stay
    cheap.

    `label` exists so a person can tell one device from another when revoking, which
    is the only moment anybody looks at this table.
    """

    PREFIX = "sm_"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_tokens"
    )
    label = models.CharField(max_length=64, default="device")
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    # First few characters of the token, kept in clear so a device is identifiable
    # in a list. Far too short to be useful to anyone who steals it.
    display_prefix = models.CharField(max_length=12, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["owner"],
                condition=Q(revoked_at__isnull=True),
                name="apitoken_live",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.label} ({self.display_prefix}…)"

    @staticmethod
    def hash_token(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def issue(cls, owner, *, label: str = "device") -> tuple["ApiToken", str]:
        """Create a token and return it with its one and only plaintext.

        The caller must hand the string to the person immediately; nothing can
        recover it afterwards, which is the property that makes the stored hash
        worth having.
        """
        raw = f"{cls.PREFIX}{secrets.token_urlsafe(32)}"
        token = cls.objects.create(
            owner=owner,
            label=label[:64] or "device",
            token_hash=cls.hash_token(raw),
            display_prefix=raw[:11],
        )
        return token, raw

    @property
    def is_live(self) -> bool:
        return self.revoked_at is None and self.owner.is_active


class MissContext(models.TextChoices):
    SEARCH = "search"
    CAPTURE = "capture"


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
    resolved_node = models.ForeignKey(
        Node, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

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
