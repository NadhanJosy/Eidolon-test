import type { AdultStatus, Journal, MemoryItem, Relationship, ScheduledJob } from "../types";
import {
  memoryResonance,
  memoryTypeLabel,
  overviewCards,
  relationshipPhase,
  toneClass,
  type SummaryCard
} from "../cognition";
import { EmptyState, TagRow } from "../ui";

export function OverviewPanel({
  relationship,
  memories,
  journals,
  jobs,
  adultStatus
}: {
  relationship: Relationship;
  memories: MemoryItem[];
  journals: Journal[];
  jobs: ScheduledJob[];
  adultStatus: AdultStatus | null;
}) {
  const cards = overviewCards({ relationship, memories, journals, jobs, adultStatus });
  return (
    <>
      <section className="grid grid-cols-2 gap-2">
        {cards.map((card) => (
          <OverviewStat card={card} key={card.label} />
        ))}
      </section>
      <section className="rounded-md border border-line bg-ink p-3 text-sm">
        <p className="font-medium text-paper">{relationshipPhase(relationship)}</p>
        <p className="mt-1 text-xs text-zinc-500">
          {adultStatus?.effective_mode === "adult" ? "Adult gates active" : "Safe mode active"} ·{" "}
          {jobs.some((job) => job.status === "pending")
            ? "companion notes are queued"
            : "no pending companion notes"}
        </p>
        <TagRow tags={relationship.tags_json} />
      </section>
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Recent Memory</h2>
        {memories.slice(0, 3).map((memory) => (
          <article className="rounded-md border border-line bg-ink p-2 text-xs" key={memory.id}>
            <p className="text-zinc-300">{memory.content}</p>
            <p className="mt-1 text-zinc-500">
              {memoryTypeLabel(memory.memory_type)} · {memoryResonance(memory)}
            </p>
          </article>
        ))}
        {memories.length === 0 ? (
          <EmptyState text="No durable memories yet. The companion is still learning what matters." />
        ) : null}
      </section>
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Journal</h2>
        {journals.slice(0, 2).map((journal) => (
          <article className="rounded-md border border-line bg-ink p-2 text-xs" key={journal.id}>
            <p className="text-zinc-300">{journal.title}</p>
            <p className="mt-1 text-zinc-500">{journal.summary}</p>
          </article>
        ))}
        {journals.length === 0 ? (
          <EmptyState text="No shared episodes yet. Milestones and callbacks will appear here." />
        ) : null}
      </section>
    </>
  );
}

function OverviewStat({ card }: { card: SummaryCard }) {
  return (
    <div className={`rounded-md border p-2 ${toneClass(card.tone)}`}>
      <p className="text-[11px] uppercase text-zinc-600">{card.label}</p>
      <p className="mt-1 text-sm font-medium text-zinc-200">{card.value}</p>
      <p className="mt-1 line-clamp-2 text-xs text-zinc-500">{card.detail}</p>
    </div>
  );
}
