import type { FormEvent } from "react";

import type { Journal } from "../types";
import { EmptyState, formatTimestamp, inputClass, primaryButtonClass, TagRow } from "../ui";

export function JournalPanel({
  journals,
  title,
  summary,
  setTitle,
  setSummary,
  onAdd
}: {
  journals: Journal[];
  title: string;
  summary: string;
  setTitle: (value: string) => void;
  setSummary: (value: string) => void;
  onAdd: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const unresolvedCount = journals.reduce(
    (total, journal) => total + journal.unresolved_threads_json.length,
    0
  );
  const callbackCount = journals.reduce(
    (total, journal) => total + journal.callbacks_json.length,
    0
  );
  const emotionalTagCount = journals.reduce(
    (total, journal) => total + journal.emotional_tags_json.length,
    0
  );
  const orderedJournals = [...journals].sort(
    (left, right) =>
      right.importance - left.importance ||
      new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
  );

  return (
    <>
      <div className="grid grid-cols-3 gap-2">
        <JournalStat label="Entries" value={journals.length.toString()} />
        <JournalStat label="Open" value={unresolvedCount.toString()} />
        <JournalStat label="Callbacks" value={callbackCount.toString()} />
      </div>
      {emotionalTagCount > 0 ? (
        <p className="rounded-md border border-line bg-ink px-3 py-2 text-xs text-zinc-400">
          {emotionalTagCount} emotional marker{emotionalTagCount === 1 ? "" : "s"} available for
          continuity.
        </p>
      ) : null}
      <form className="space-y-2" onSubmit={onAdd}>
        <input
          className={inputClass}
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Journal title"
        />
        <textarea
          className={`${inputClass} min-h-20 resize-none`}
          value={summary}
          onChange={(event) => setSummary(event.target.value)}
          placeholder="Summary"
        />
        <button className={primaryButtonClass} type="submit">
          Add journal
        </button>
      </form>
      <div className="space-y-2">
        {journals.length === 0 ? <EmptyState text="No journal entries." /> : null}
        {orderedJournals.map((journal) => (
          <article className="rounded-md border border-line bg-ink p-3 text-sm" key={journal.id}>
            <div className="flex items-start justify-between gap-2">
              <h3 className="font-medium">{journal.title}</h3>
              <span className="rounded border border-line bg-panel px-2 py-1 text-xs text-zinc-400">
                {journal.importance.toFixed(1)}
              </span>
            </div>
            <p className="mt-2 whitespace-pre-wrap leading-6">{journal.summary}</p>
            <p className="mt-2 text-xs text-zinc-500">
              {journal.journal_type} · {formatTimestamp(journal.created_at)}
            </p>
            {journal.unresolved_threads_json.length > 0 ? (
              <div className="mt-2 rounded border border-ember bg-amber-950/30 px-2 py-1 text-xs text-amber-100">
                {journal.unresolved_threads_json.slice(0, 2).join(" · ")}
              </div>
            ) : null}
            <TagRow tags={[...journal.emotional_tags_json, ...journal.callbacks_json.slice(0, 2)]} />
          </article>
        ))}
      </div>
    </>
  );
}

function JournalStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-ink p-2">
      <p className="text-[11px] uppercase text-zinc-600">{label}</p>
      <p className="mt-1 font-mono text-sm text-zinc-200">{value}</p>
    </div>
  );
}
