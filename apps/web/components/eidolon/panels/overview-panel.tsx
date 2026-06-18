import type { AdultStatus, Journal, MemoryItem, Relationship, ScheduledJob } from "../types";
import { EmptyState, MetricCard, TagRow } from "../ui";

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
  return (
    <>
      <section className="grid grid-cols-2 gap-2">
        <MetricCard label="warmth" value={relationship.warmth} accent="bg-moss" />
        <MetricCard label="trust" value={relationship.trust} accent="bg-tide" />
        <MetricCard label="tension" value={relationship.tension} accent="bg-ember" />
        <MetricCard label="memory" value={Math.min(100, memories.length * 12)} accent="bg-paper" />
      </section>
      <section className="rounded-md border border-line bg-ink p-3 text-sm">
        <p>
          {relationship.mood} · {relationship.conflict_state}
        </p>
        <p className="mt-1 text-xs text-zinc-500">
          {adultStatus?.effective_mode === "adult" ? "Adult gates active" : "SFW enforced"} ·{" "}
          {jobs.length} queued jobs
        </p>
        <TagRow tags={relationship.tags_json} />
      </section>
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Recent Memory</h2>
        {memories.slice(0, 3).map((memory) => (
          <p className="rounded-md border border-line bg-ink p-2 text-xs" key={memory.id}>
            {memory.content}
          </p>
        ))}
        {memories.length === 0 ? <EmptyState text="No memories." /> : null}
      </section>
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Journal</h2>
        {journals.slice(0, 2).map((journal) => (
          <article className="rounded-md border border-line bg-ink p-2 text-xs" key={journal.id}>
            <p className="text-zinc-300">{journal.title}</p>
            <p className="mt-1 text-zinc-500">{journal.summary}</p>
          </article>
        ))}
        {journals.length === 0 ? <EmptyState text="No journal entries." /> : null}
      </section>
    </>
  );
}
