"""A tags box on the capture page, and why it does not break the one box.

The capture surface's first principle is that nothing requires a decision at the
moment of entry — its own docstring says "one textarea, nothing to classify,
nothing to file, no fields", and that a dropdown "would break that before
anything else got a chance to".

**An optional free-text field is not that, and the distinction is the whole
justification.** A dropdown presents a closed set and asks which one; leaving it
alone still feels like an answer withheld. An empty text box asks nothing, and a
person who never touches it captures exactly as they did before. What it buys is
the other half of a decision already made: a typed tag becomes a confirmed
concept, and until now the only surface that could type one was the phone.

The evidence for needing it is concrete. On 15 August the first real detector
run over 18 notes proposed nothing, and the six candidates extraction did find
were `Gravity`, `MOT`, `Oct`, `YT` and two phrases — every one seen once. The
thing that genuinely recurred across four notes and twelve days was *movie*,
lowercase, which a capitalisation-based extractor cannot see. The gravity gate
is for the system's guesses; a person who knows "movie" is a thing should be
able to say so.
"""

import pytest

from mind.models import ConceptCandidate, Mention, Node

pytestmark = pytest.mark.django_db


@pytest.fixture
def signed_in(client, owner):
    client.force_login(owner)
    return client


def keep(client, content, tags=""):
    return client.post("/mind/", {"content": content, "tags": tags})


def test_a_tag_typed_at_capture_becomes_a_confirmed_concept(signed_in, owner):
    keep(signed_in, "the invention of lying", tags="movie")

    concept = ConceptCandidate.objects.get(label="movie")
    assert concept.confirmed_at is not None
    assert Mention.objects.filter(node__owner=owner, concept=concept).exists()


def test_several_tags_are_split_on_commas(signed_in, owner):
    keep(signed_in, "the monuments men", tags="movie, war, watched")

    assert set(ConceptCandidate.objects.values_list("label", flat=True)) == {
        "movie", "war", "watched",
    }


def test_the_same_tag_across_notes_builds_one_concept(signed_in, owner):
    """What the extractor could not do. Four notes about films become four
    mentions of one referent, because somebody said so rather than because a
    rule inferred it."""
    keep(signed_in, "the invention of lying", tags="movie")
    keep(signed_in, "down periscope", tags="movie")
    keep(signed_in, "the monuments men", tags="movie")

    concept = ConceptCandidate.objects.get(label="movie")
    assert Mention.objects.filter(concept=concept).count() == 3


def test_capturing_with_no_tags_is_exactly_as_before(signed_in, owner):
    """The principle this field had to survive: somebody who ignores it types a
    thought and nothing else happens."""
    keep(signed_in, "I like lucid cars")

    assert Node.objects.count() == 1
    assert ConceptCandidate.objects.count() == 0


@pytest.mark.parametrize("messy", [",", " , ,", "movie,,", "  movie  "])
def test_a_stray_comma_is_not_an_error(signed_in, owner, messy):
    """Nothing about tidying labels is worth failing a capture over."""
    response = keep(signed_in, "down periscope", tags=messy)

    assert response.status_code == 302
    assert Node.objects.count() == 1
    assert ConceptCandidate.objects.count() <= 1


def test_the_field_is_on_the_page_and_says_it_is_optional(signed_in, owner):
    """A required-looking field would ask a question at the moment of entry,
    which is the thing this surface refuses to do."""
    page = signed_in.get("/mind/")

    assert b'name="tags"' in page.content
    assert b"optional" in page.content.lower()
