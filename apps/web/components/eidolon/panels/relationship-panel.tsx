import type { Relationship, RelationshipEvent } from "../types";
import { relationshipMetrics } from "../types";
import { EmptyState, formatTimestamp, MetricCard, TagRow } from "../ui";

export function RelationshipPanel({
  relationship,
  timeline
}: {
  relationship: Relationship;
  timeline: RelationshipEvent[];
}) {
  return (
    <>
      <div className="grid grid-cols-2 gap-2 text-sm">
        {relationshipMetrics.map((key) => (
          <MetricCard
            accent={key === "tension" ? "bg-ember" : key === "warmth" ? "bg-moss" : "bg-tide"}
            key={key}
            label={key}
            value={relationship[key]}
          />
        ))}
      </div>
      <div className="rounded-md border border-line bg-ink p-3 text-sm">
        <p>
          {relationship.mood} · {relationship.conflict_state}
        </p>
        {relationship.repair_needed ? <p className="mt-1 text-ember">Repair needed</p> : null}
        <TagRow tags={relationship.tags_json} />
      </div>
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Timeline</h2>
        {timeline.length === 0 ? <EmptyState text="No timeline events." /> : null}
        {timeline
          .slice()
          .reverse()
          .slice(0, 12)
          .map((event, index) => (
            <article className="rounded-md border border-line bg-ink p-3 text-xs" key={index}>
              <p className="text-zinc-300">{event.summary ?? event.kind ?? "state update"}</p>
              <p className="mt-1 text-zinc-500">{event.at ? formatTimestamp(event.at) : ""}</p>
              <TagRow tags={event.tags ?? []} />
            </article>
          ))}
      </section>
    </>
  );
}
