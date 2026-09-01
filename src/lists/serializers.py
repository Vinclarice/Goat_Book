from django.urls import reverse

from lists.models import List, Project


def serialize_checklist_step(step):
    return {
        "id": step.id,
        "text": step.text,
        "position": step.position,
        "is_done": step.is_done,
        "completed_at": (
            step.completed_at.isoformat() if step.completed_at else None
        ),
        "carries_forward": step.carries_forward,
        "task_id": step.task_id,
        # **`url` and `promote_url` were here until August 30, 2026** --
        # coherence-audit-2026-08-30.md F2. The client addresses a step by id
        # now, and unlike a task's `url`, nothing outside this repository ever
        # read these: the phone has no checklist surface. So they go with the
        # views they pointed at, rather than being repointed.
    }


def serialize_item(item):
    return {
        "id": item.id,
        "text": item.text,
        "status": item.status,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "completed_at": (
            item.completed_at.isoformat() if item.completed_at else None
        ),
        "archived_at": item.archived_at.isoformat() if item.archived_at else None,
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "position": item.position,
        "tags": [tag.name for tag in item.tags.all()],
        "recurrence": item.recurrence,
        "priority": item.priority,
        "lead_days": item.lead_days,
        "notes": item.notes,
        # Just the id -- callers already have (or can fetch) the area's
        # title/url from the top-level `areas` array in the page payload,
        # so it doesn't need repeating on every single task.
        # `item.list_id` is the ORM's column; `area_id` is what the boundary
        # calls it, the same split Item/"task" already lives with.
        "area_id": item.list_id,
        # Null for most tasks. Derived through the task's own Area now
        # rather than stored on the task itself -- project-workspace-plan.md
        # 2: a task belongs to a project only by belonging to an Area that
        # is inside it. Every caller already select_related("list"), so this
        # is free.
        #
        # Null also when there is no Area at all, which is a different fact
        # wearing the same value and is correct either way: a task belongs to
        # a project by belonging to an Area, so one with no Area is in no
        # project. Written as a guard rather than left to `item.list` because
        # this line ran for *every* task in the agenda payload -- one unfiled
        # task did not degrade its own row, it raised and took the whole page.
        "project_id": item.list.project_id if item.list_id else None,
        # update and delete hit the same endpoint, just with different
        # HTTP methods, so one url covers both.
        #
        # **`url` is here for the shipped Android build alone** -- it reads it
        # with getString and posts to it. Nothing in this repository does any
        # more; see lists/api.py for what retires it.
        "url": reverse("api_item_detail", args=(item.id,)),
        # **`edit_url` stood here until August 30, 2026** --
        # coherence-audit-2026-08-30.md F4. It pointed at a Django view whose
        # entire body was a redirect into the SPA, so the Agenda's "Edit" took
        # two round trips to reach a route the client router already had. The
        # Agenda uses a Link now and nothing else ever read the field.
    }


def project_ref_for(project):
    """A project's minimal read shape: id, title, and its own url.

    project-workspace-plan.md closes ui-second-pass-plan.md F2/F3's second
    half: a Project has its own SPA page now. Hand-built rather than
    reverse()'d -- Project has no Django-rendered view to reverse against,
    the same "web/API-only surface" reasoning its model docstring already
    gives for skipping a public identifier. Shared by the Agenda and Daily
    Page reads, the two surfaces that join a task's project_id against this.
    """
    return {
        "id": project.id,
        "title": project.title,
        "url": f"/app/projects/{project.id}",
    }


def area_ref_for(our_list):
    return {
        "id": our_list.id,
        "title": our_list.title,
        # Still `create_item_url`/`api_create_item`: that spelling belongs to
        # the unfinished Item -> "task" rename, not to this one. Renaming it
        # here would make one commit answer for two vocabularies.
        "create_item_url": reverse("api_create_item", args=(our_list.id,)),
    }


def area_workspace_data_for(our_list, items):
    """Shapes the area-detail JSON shared by the Django-rendered area page's
    React bootstrap data and the /api/v1/areas/{id} endpoint, so the two
    can't drift apart -- same reasoning as agenda.workspace_data_for().
    """
    return {
        "area": area_ref_for(our_list),
        "items": [serialize_item(item) for item in items],
        # Singular and optional now -- project-workspace-plan.md 2 inverted
        # this: an Area belongs to at most one Project, not the other way
        # around.
        "project": (
            project_ref_for(our_list.project) if our_list.project_id else None
        ),
    }


def task_detail_data_for(item):
    """Shapes the single-task JSON for /api/v1/tasks/{id} -- there's no
    Django-rendered equivalent to share a contract with (edit_item.html
    is HTML-only), so this is genuinely new rather than extracted from
    an existing view.
    """
    return {
        "task": serialize_item(item),
        # On the detail payload only. It lives on the commitment, so putting it
        # on every TaskOut would mean joining the series for every row of the
        # agenda to answer a question only this page asks. Null for a task that
        # does not repeat, which is most of them.
        "cadence_mode": (
            item.commitment.cadence_mode if item.commitment_id else None
        ),
        # Null for a task standing on its own. Present-but-empty rather than
        # absent, so the client reads "this task has no Area" instead of
        # having to infer it from a missing key -- inference is how a filed
        # task and an unfiled one end up rendered the same.
        "area": (
            {
                "id": item.list.id,
                "title": item.list.title,
                "url": item.list.get_absolute_url(),
            }
            if item.list_id
            else None
        ),
        "checklist_steps": [
            serialize_checklist_step(step)
            for step in item.checklist_steps.order_by("position", "id")
        ],
        # **Two urls stood here until August 30, 2026** --
        # coherence-audit-2026-08-30.md F2. The client addresses
        # `/api/v1/tasks/{id}/checklist-steps` by the task's own id now, which
        # this payload has always carried, so these were a second spelling of
        # a route the caller could already build. Nothing outside this
        # repository read them.
    }


def archive_workspace_data_for(user, archived_items):
    """Shapes the archive JSON shared by the Django-rendered archive page's
    React bootstrap data and the /api/v1/archive endpoint.
    """
    return {
        "items": [serialize_item(item) for item in archived_items],
        # Task JSON only carries area_id; the frontend joins against this
        # to show an area's title and link.
        "areas": [
            {
                "id": each.id,
                "title": each.title,
                "url": each.get_absolute_url(),
            }
            for each in List.objects.filter(owner=user)
        ],
        # ui-second-pass-plan.md F2's third and last surface the sitting
        # observed: an archived task carries project_id same as any other,
        # so it gets the same join the Agenda and Daily Page already have.
        "projects": [
            project_ref_for(each) for each in Project.objects.filter(owner=user)
        ],
    }
