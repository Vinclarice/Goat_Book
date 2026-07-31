import { describe, expect, it } from "vitest";

import {
  addDays,
  applyFilters,
  bucketFor,
  dueLabel,
  snoozePresets,
  sortAgendaTasks,
  summaryCounts,
  tagSummaries,
  WEEK_HORIZON_DAYS,
  type SnoozeKey,
} from "./agenda";
import { task, TODAY } from "./test/fixtures";

describe("bucketFor", () => {
  it("puts undated tasks in someday", () => {
    expect(bucketFor(null, TODAY)).toBe("someday");
  });

  it("puts past dates in overdue", () => {
    expect(bucketFor("2026-07-27", TODAY)).toBe("overdue");
  });

  it("puts today in today", () => {
    expect(bucketFor(TODAY, TODAY)).toBe("today");
  });

  it("keeps the last day of the horizon in this week", () => {
    const edge = addDays(TODAY, WEEK_HORIZON_DAYS);
    expect(bucketFor(edge, TODAY)).toBe("week");
  });

  it("pushes the day after the horizon into later", () => {
    const past = addDays(TODAY, WEEK_HORIZON_DAYS + 1);
    expect(bucketFor(past, TODAY)).toBe("later");
  });
});

describe("addDays", () => {
  it("rolls over month boundaries", () => {
    expect(addDays("2026-07-31", 1)).toBe("2026-08-01");
  });

  it("goes backwards", () => {
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
  });
});

describe("snoozePresets", () => {
  // Pinned weekdays: presets that pivot on Saturday and Monday would
  // otherwise only be wrong one day a week. TODAY is a Tuesday.
  const FRIDAY = "2026-07-31";
  const SATURDAY = "2026-08-01";
  const SUNDAY = "2026-08-02";
  const MONDAY = "2026-08-03";

  function dueDate(today: string, key: SnoozeKey): string | null {
    return snoozePresets(today).find((preset) => preset.key === key)!.dueDate;
  }

  it("offers four labelled options in order", () => {
    expect(snoozePresets(TODAY).map((preset) => [preset.key, preset.label])).toEqual([
      ["tomorrow", "Tomorrow"],
      ["weekend", "This weekend"],
      ["next_week", "Next week"],
      ["clear", "Clear"],
    ]);
  });

  it("puts tomorrow a day out", () => {
    expect(dueDate(TODAY, "tomorrow")).toBe(addDays(TODAY, 1));
  });

  it("puts this weekend on the coming saturday", () => {
    expect(dueDate(TODAY, "weekend")).toBe(SATURDAY);
  });

  it("means the sunday still to come when today is saturday", () => {
    expect(dueDate(SATURDAY, "weekend")).toBe(SUNDAY);
  });

  it("rolls on to the next saturday when today is sunday", () => {
    expect(dueDate(SUNDAY, "weekend")).toBe("2026-08-08");
  });

  it("puts next week on the coming monday", () => {
    expect(dueDate(TODAY, "next_week")).toBe(MONDAY);
    expect(dueDate(SUNDAY, "next_week")).toBe(MONDAY);
  });

  it("skips a full week when today is monday", () => {
    expect(dueDate(MONDAY, "next_week")).toBe("2026-08-10");
  });

  it("collapses tomorrow and this weekend onto the same saturday on a friday", () => {
    // Mirrors test_agenda.py: the one day the menu offers a date twice.
    expect(dueDate(FRIDAY, "tomorrow")).toBe(SATURDAY);
    expect(dueDate(FRIDAY, "weekend")).toBe(SATURDAY);
    expect(dueDate(FRIDAY, "next_week")).toBe(MONDAY);
  });

  it("gives clear no date at all", () => {
    expect(dueDate(TODAY, "clear")).toBeNull();
  });

  it("never offers a date that isn't in the future", () => {
    for (const today of [TODAY, FRIDAY, SATURDAY, SUNDAY, MONDAY]) {
      for (const preset of snoozePresets(today)) {
        if (preset.dueDate !== null) expect(preset.dueDate > today).toBe(true);
      }
    }
  });
});

describe("summaryCounts", () => {
  it("folds overdue and today into the week total", () => {
    const tasks = [
      task({ id: 1, due_date: "2026-07-20" }),
      task({ id: 2, due_date: "2026-07-26" }),
      task({ id: 3, due_date: TODAY }),
      task({ id: 4, due_date: "2026-07-30" }),
      task({ id: 5, due_date: null }),
    ];

    expect(summaryCounts(tasks, TODAY)).toEqual({
      overdue: 2,
      today: 1,
      week: 4,
      open: 5,
    });
  });
});

describe("applyFilters", () => {
  const tasks = [
    task({ id: 1, text: "Late", due_date: "2026-07-20", tags: ["urgent"] }),
    task({ id: 2, text: "Now", due_date: TODAY }),
    task({
      id: 3,
      text: "Chores",
      due_date: null,
      list_id: 2,
    }),
  ];

  it("returns everything when nothing is selected", () => {
    const filters = { scope: null, list: null, tag: null };
    expect(applyFilters(tasks, TODAY, filters)).toHaveLength(3);
  });

  it("narrows by scope", () => {
    const filters = { scope: "overdue", list: null, tag: null };
    expect(applyFilters(tasks, TODAY, filters).map((t) => t.text)).toEqual([
      "Late",
    ]);
  });

  it("includes overdue tasks in the week scope", () => {
    const filters = { scope: "week", list: null, tag: null };
    expect(applyFilters(tasks, TODAY, filters).map((t) => t.text)).toEqual([
      "Late",
      "Now",
    ]);
  });

  it("narrows by list", () => {
    const filters = { scope: null, list: 2, tag: null };
    expect(applyFilters(tasks, TODAY, filters).map((t) => t.text)).toEqual([
      "Chores",
    ]);
  });

  it("narrows by tag", () => {
    const filters = { scope: null, list: null, tag: "urgent" };
    expect(applyFilters(tasks, TODAY, filters).map((t) => t.text)).toEqual([
      "Late",
    ]);
  });
});

describe("tagSummaries", () => {
  it("counts tags across tasks, alphabetically", () => {
    const tasks = [
      task({ id: 1, tags: ["work", "urgent"] }),
      task({ id: 2, tags: ["urgent"] }),
    ];

    expect(tagSummaries(tasks)).toEqual([
      { name: "urgent", count: 2 },
      { name: "work", count: 1 },
    ]);
  });
});

describe("dueLabel", () => {
  it("names yesterday rather than counting one day", () => {
    expect(dueLabel("2026-07-27", TODAY)).toBe("Yesterday");
  });

  it("counts days for anything older", () => {
    expect(dueLabel("2026-07-24", TODAY)).toBe("4 days overdue");
  });

  it("says today and tomorrow", () => {
    expect(dueLabel(TODAY, TODAY)).toBe("Today");
    expect(dueLabel("2026-07-29", TODAY)).toBe("Tomorrow");
  });
});

describe("sortAgendaTasks", () => {
  it("orders by due date, then position, then id, with undated last", () => {
    const tasks = [
      task({ id: 3, due_date: null, position: 0 }),
      task({ id: 1, due_date: "2026-08-01", position: 5 }),
      task({ id: 2, due_date: "2026-07-29", position: 2 }),
      task({ id: 4, due_date: "2026-07-29", position: 1 }),
    ];

    expect(sortAgendaTasks(tasks).map((t) => t.id)).toEqual([4, 2, 1, 3]);
  });
});
