import { colorForKey } from "../../agenda";
import type { AreaColorKey } from "../../types";

interface CompositionArea {
  id: number;
  title: string;
  open_count: number;
  color_key: AreaColorKey;
}

/**
 * A project's areas, drawn as one segmented strip -- the visual answer to
 * "what's actually inside this workspace" that a bare open-task number
 * can't give. Segment width follows each area's own open_count (floored at
 * 1 so an area with nothing open still shows a sliver rather than
 * vanishing), so a project leaning heavily on one area reads that way at a
 * glance. Same --list-color-* values as every area dot elsewhere in the
 * app -- this is that existing color identity, not a new one.
 *
 * Color alone never carries the information: each segment's `title`
 * attribute names the area and its count, and callers still render the
 * area list in text beneath it.
 */
export function ProjectComposition({
  areas,
  dimmed = false,
}: {
  areas: CompositionArea[];
  dimmed?: boolean;
}) {
  if (areas.length === 0) {
    return (
      <div
        className="h-1.5 w-full rounded-full border border-dashed border-border"
        aria-hidden="true"
      />
    );
  }

  const weights = areas.map((area) => Math.max(area.open_count, 1));
  const total = weights.reduce((sum, weight) => sum + weight, 0);

  return (
    <div
      className={`flex h-1.5 w-full gap-px overflow-hidden rounded-full${dimmed ? " opacity-40" : ""}`}
      role="img"
      aria-label={`Areas: ${areas.map((area) => `${area.title}, ${area.open_count} open`).join("; ")}`}
    >
      {areas.map((area, index) => (
        <span
          key={area.id}
          title={`${area.title} · ${area.open_count} open`}
          style={{
            background: colorForKey(area.color_key),
            width: `${(weights[index] / total) * 100}%`,
          }}
          className="h-full first:rounded-l-full last:rounded-r-full"
        />
      ))}
    </div>
  );
}
