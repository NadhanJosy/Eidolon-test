import type { Relationship, RelationshipEvent } from "../types";
import {
  relationshipCards,
  relationshipMomentum,
  relationshipPhase,
  relationshipRecentChanges,
  relationshipTemperature,
  timelineSummary,
  toneClass,
  type SummaryCard
} from "../cognition";
import { EmptyState, formatTimestamp, TagRow } from "../ui";

export function RelationshipPanel({
  relationship,
  timeline
}: {
  relationship: Relationship;
  timeline: RelationshipEvent[];
}) {
  const cards = relationshipCards(relationship);
  const recentChanges = relationshipRecentChanges(relationship);
  return (
    <>
      <div className="grid grid-cols-3 gap-2 text-sm">
        {cards.map((card) => (
          <RelationshipStat card={card} key={card.label} />
        ))}
      </div>
      <div className="rounded-md border border-line bg-ink p-3 text-sm">
        <p className="font-medium text-paper">{relationshipPhase(relationship)}</p>
        <p className="mt-1 text-xs text-zinc-500">
          The connection feels {relationshipTemperature(relationship)} and{" "}
          {relationshipMomentum(relationship)}.
        </p>
        {relationship.repair_needed ? (
          <p className="mt-2 rounded border border-ember bg-amber-950/40 px-2 py-1 text-xs text-amber-100">
            Repair should come before escalation.
          </p>
        ) : null}
        <TagRow tags={relationship.tags_json} />
      </div>
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Recent Shifts</h2>
        {recentChanges.length === 0 ? (
          <EmptyState text="No recent relationship changes are ready yet." />
        ) : null}
        {recentChanges.map((change, index) => (
          <article className="rounded-md border border-line bg-ink p-3 text-xs" key={index}>
            <div className="flex items-center justify-between gap-2">
              <p className="font-medium text-zinc-300">
                {change.label ?? "Connection"}
              </p>
              <span className="rounded border border-line px-1.5 py-0.5 text-[10px] uppercase text-zinc-500">
                {change.magnitude ?? "subtle"}
              </span>
            </div>
            <p className="mt-1 text-zinc-500">{change.summary}</p>
            {change.at ? (
              <p className="mt-1 text-[11px] text-zinc-600">{formatTimestamp(change.at)}</p>
            ) : null}
          </article>
        ))}
      </section>
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Timeline</h2>
        {timeline.length === 0 ? (
          <EmptyState text="No relationship shifts have been recorded yet. The first few exchanges will start shaping the bond." />
        ) : null}
        {timeline
          .slice()
          .reverse()
          .slice(0, 12)
          .map((event, index) => (
            <article className="rounded-md border border-line bg-ink p-3 text-xs" key={index}>
              <p className="text-zinc-300">{timelineSummary(event)}</p>
              <p className="mt-1 text-zinc-500">{event.at ? formatTimestamp(event.at) : ""}</p>
              <TagRow tags={event.tags ?? []} />
            </article>
          ))}
      </section>
    </>
  );
}

function RelationshipStat({ card }: { card: SummaryCard }) {
  return (
    <div className={`rounded-md border p-2 ${toneClass(card.tone)}`}>
      <p className="text-[11px] uppercase text-zinc-600">{card.label}</p>
      <p className="mt-1 text-sm font-medium text-zinc-200">{card.value}</p>
      <p className="mt-1 line-clamp-2 text-xs text-zinc-500">{card.detail}</p>
    </div>
  );
}
