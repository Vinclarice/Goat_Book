"""Two entrances, and an explanation of only what is actually there.

Track D increment 15. `commercial-blueprint.md` has carried *"explain the six
invented concepts — Area, Project, Checklist Step, Compass, Focus, 'call it
enough' — somewhere in the product, once"* as an open item, and there is no
onboarding, no help and no in-product explanation of any of them.

**The obvious answer is a tour, and the plan refuses it.** Orientation is one
of two entrances — *quick start* beside *empty my head* — and it explains
**only the concepts the person's own material demonstrates**. The v3 plan says
why in one line: *explaining a Compass that is not there turns personalisation
back into the tutorial it replaced.*

So this is a read, not a script. It asks what somebody has actually produced
and explains that, which means:

- **Nothing is explained before it exists.** A person who has never pinned
  anything is not told what Focus is, because the word would attach to nothing.
- **It empties as it succeeds.** Once every concept is demonstrated there is
  nothing left to explain, and the page says so rather than repeating itself.
- **The evidence is theirs.** Each explanation names the thing of theirs that
  demonstrates it, so the concept has something to be about.

**Here rather than in `lists` or `mind`** because it reads across both cores
and `accounts` — a `List`, a `Project`, a `ChecklistStep`, two fields on
`User`, a `DailyFocus`, a `WeeklyReview` — which is what `clarice/` is for.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Concept:
    """One invented word, and the thing of the person's own it is about."""

    name: str
    #: What it means, in a sentence, without reference to anything they have
    #: not got.
    means: str
    #: Their own material that demonstrates it. **The reason this is a read**:
    #: a concept with no evidence is not explained at all.
    evidence: str


def what_their_material_demonstrates(owner):
    """The invented concepts this person has actually produced, in order.

    **Order is the order they tend to arrive in**, not importance: an Area
    exists the moment anything is captured, and *call it enough* cannot happen
    until a week has been reviewed. A list sorted by importance would put the
    rarest first and read as a list of things they have not done.
    """
    from daily.models import DailyFocus
    from lists.models import ChecklistStep, Item, List, Project
    from review.models import WeeklyReview

    found = []

    area = List.objects.filter(owner=owner).order_by("pk").first()
    if area is not None:
        found.append(
            Concept(
                "Area",
                "a place tasks live — a part of your life rather than a folder",
                f"yours is {area.title!r}",
            )
        )

    project = Project.objects.filter(owner=owner).order_by("pk").first()
    if project is not None:
        found.append(
            Concept(
                "Project",
                "something with an end, which holds Areas rather than sitting "
                "inside one",
                f"yours is {project.title!r}",
            )
        )

    step = (
        ChecklistStep.objects.filter(task__owner=owner).order_by("pk").first()
    )
    if step is not None:
        found.append(
            Concept(
                "Checklist step",
                "a part of one task, which can carry forward to the next time "
                "the task comes round",
                f"one of yours is {step.text!r}",
            )
        )

    if (owner.compass_purpose or "").strip() or (owner.compass_question or "").strip():
        found.append(
            Concept(
                "Compass",
                "a standing purpose and a standing question, which sit above "
                "any particular day",
                "you have written one",
            )
        )

    focus = DailyFocus.objects.filter(owner=owner).order_by("pk").first()
    if focus is not None:
        found.append(
            Concept(
                "Focus",
                "what you chose for a day — recorded as a choice, so putting "
                "it down later is a decision rather than a failure",
                f"you chose {focus.task_text!r}",
            )
        )

    reviewed = (
        WeeklyReview.objects.filter(owner=owner)
        .exclude(completed_at=None)
        .order_by("pk")
        .first()
    )
    if reviewed is not None:
        found.append(
            Concept(
                "Call it enough",
                "ending a week deliberately, against what you actually chose "
                "rather than against everything that existed",
                # `%-d` is glibc-only: it works on the Linux container and
                # raises `ValueError: Invalid format string` on Windows, so it
                # would have shipped fine and failed only on the machine this
                # is written on. Built from the parts instead.
                f"you did it for the week of "
                f"{reviewed.week_start.day} {reviewed.week_start:%B}",
            )
        )

    return found


def is_new_here(owner):
    """Whether this person has produced anything at all yet.

    **Not a stored flag**, and deliberately: a flag says *has been shown the
    tour* and this asks *has anything happened*, which is the question the two
    entrances are answering. Somebody who signed up, wrote nothing, and came
    back a month later is new here again, which is true.
    """
    from lists.models import Item

    from mind.models import Node

    return not (
        Item.objects.filter(owner=owner).exists()
        or Node.objects.filter(owner=owner).exists()
    )
