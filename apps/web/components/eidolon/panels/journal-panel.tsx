import type { FormEvent } from "react";

import {
  journalContinuityLabels,
  journalContinuityNotes,
  journalIsAdultRedacted,
  journalOverviewCards,
  journalResonance,
  toneClass,
  type SummaryCard
} from "../cognition";
import type { Journal } from "../types";
import {
  EmptyState,
  formatTimestamp,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
  TagRow
} from "../ui";

export function JournalPanel({
  journals,
  title,
  summary,
  editingJournalId,
  editTitle,
  editSummary,
  journalActionId,
  setTitle,
  setSummary,
  setEditTitle,
  setEditSummary,
  onAdd,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  onDelete
}: {
  journals: Journal[];
  title: string;
  summary: string;
  editingJournalId: string | null;
  editTitle: string;
  editSummary: string;
  journalActionId: string | null;
  setTitle: (value: string) => void;
  setSummary: (value: string) => void;
  setEditTitle: (value: string) => void;
  setEditSummary: (value: string) => void;
  onAdd: (event: FormEvent<HTMLFormElement>) => void;
  onStartEdit: (journal: Journal) => void;
  onCancelEdit: () => void;
  onSaveEdit: (journal: Journal) => void;
  onDelete: (journal: Journal) => void;
}) {
  const orderedJournals = [...journals].sort(
    (left, right) =>
      right.importance - left.importance ||
      new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
  );
  const overviewCards = journalOverviewCards(journals);

  return (
    <>
      <div className="grid grid-cols-3 gap-2">
        {overviewCards.map((card) => (
          <JournalStat card={card} key={card.label} />
        ))}
      </div>
      {journals.some((journal) => journal.emotional_tags_json.length > 0) ? (
        <p className="rounded-md border border-line bg-ink px-3 py-2 text-xs text-zinc-400">
          Emotional markers are available for callbacks, repair arcs, and future tone.
        </p>
      ) : null}
      <form className="space-y-2" onSubmit={onAdd}>
        <input
          aria-label="New personal journal title"
          className={inputClass}
          maxLength={200}
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Journal title"
        />
        <textarea
          aria-label="New personal journal summary"
          className={`${inputClass} min-h-20 resize-none`}
          maxLength={2000}
          value={summary}
          onChange={(event) => setSummary(event.target.value)}
          placeholder="Summary"
        />
        <button className={primaryButtonClass} disabled={journalActionId !== null} type="submit">
          {journalActionId === "add" ? "Saving..." : "Add personal note"}
        </button>
      </form>
      <div className="space-y-2">
        {journals.length === 0 ? (
          <EmptyState text="No episodes have been written yet. Meaningful exchanges will become continuity notes here." />
        ) : null}
        {orderedJournals.map((journal) => (
          <JournalEntry
            editSummary={editSummary}
            editTitle={editTitle}
            editing={editingJournalId === journal.id}
            journal={journal}
            journalActionId={journalActionId}
            key={journal.id}
            onCancelEdit={onCancelEdit}
            onDelete={onDelete}
            onSaveEdit={onSaveEdit}
            onStartEdit={onStartEdit}
            setEditSummary={setEditSummary}
            setEditTitle={setEditTitle}
          />
        ))}
      </div>
    </>
  );
}

function JournalStat({ card }: { card: SummaryCard }) {
  return (
    <div className={`rounded-md border p-2 ${toneClass(card.tone)}`}>
      <p className="text-[11px] uppercase text-zinc-600">{card.label}</p>
      <p className="mt-1 text-sm font-medium text-zinc-200">{card.value}</p>
      <p className="mt-1 line-clamp-2 text-xs text-zinc-500">{card.detail}</p>
    </div>
  );
}

function JournalEntry({
  journal,
  editing,
  editTitle,
  editSummary,
  journalActionId,
  setEditTitle,
  setEditSummary,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  onDelete
}: {
  journal: Journal;
  editing: boolean;
  editTitle: string;
  editSummary: string;
  journalActionId: string | null;
  setEditTitle: (value: string) => void;
  setEditSummary: (value: string) => void;
  onStartEdit: (journal: Journal) => void;
  onCancelEdit: () => void;
  onSaveEdit: (journal: Journal) => void;
  onDelete: (journal: Journal) => void;
}) {
  const continuityLabels = journalContinuityLabels(journal);
  const continuityNotes = journalContinuityNotes(journal);
  const redactedAdult = journalIsAdultRedacted(journal);
  const manual = journal.metadata_json?.source === "manual";

  return (
    <article className="rounded-md border border-line bg-ink p-3 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          {editing ? (
            <input
              aria-label="Personal journal title"
              className={inputClass}
              maxLength={200}
              onChange={(event) => setEditTitle(event.target.value)}
              value={editTitle}
            />
          ) : (
            <h3 className="font-medium">{journal.title}</h3>
          )}
          <p className="mt-1 text-[11px] uppercase text-zinc-600">
            {manual ? "personal note" : "conversation episode"}
          </p>
        </div>
        <span className="shrink-0 rounded border border-line bg-panel px-2 py-1 text-xs text-zinc-400">
          {journalResonance(journal)}
        </span>
      </div>
      {editing ? (
        <textarea
          aria-label="Personal journal summary"
          className={`${inputClass} mt-2 min-h-24 resize-none`}
          maxLength={2000}
          onChange={(event) => setEditSummary(event.target.value)}
          value={editSummary}
        />
      ) : (
        <p className="mt-2 whitespace-pre-wrap leading-6">{journal.summary}</p>
      )}
      <p className="mt-2 text-xs text-zinc-500">
        {journal.journal_type.replaceAll("_", " ")} · {formatTimestamp(journal.created_at)}
      </p>
      {continuityLabels.length > 0 ? (
        <div className="mt-3 border-t border-line/70 pt-2">
          <p className="text-[11px] uppercase text-zinc-600">Continuity</p>
          <p className="mt-1 text-xs text-zinc-400">{continuityLabels.join(" · ")}</p>
          {redactedAdult ? (
            <p className="mt-2 text-xs leading-5 text-zinc-500">
              Gated details were intentionally left out of durable recall.
            </p>
          ) : null}
          {continuityNotes.length > 0 ? (
            <ul className="mt-2 space-y-1 text-xs leading-5 text-zinc-500">
              {continuityNotes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      {journal.unresolved_threads_json.length > 0 ? (
        <div className="mt-2 rounded border border-ember bg-amber-950/30 px-2 py-1 text-xs text-amber-100">
          {journal.unresolved_threads_json.slice(0, 2).join(" · ")}
        </div>
      ) : null}
      <TagRow tags={[...journal.emotional_tags_json, ...journal.callbacks_json.slice(0, 2)]} />
      {manual ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {editing ? (
            <>
              <button
                className={primaryButtonClass}
                disabled={journalActionId !== null || !editTitle.trim() || !editSummary.trim()}
                onClick={() => onSaveEdit(journal)}
                type="button"
              >
                {journalActionId === `save:${journal.id}` ? "Saving..." : "Save note"}
              </button>
              <button
                className={secondaryButtonClass}
                disabled={journalActionId !== null}
                onClick={onCancelEdit}
                type="button"
              >
                Cancel
              </button>
            </>
          ) : (
            <button
              className={secondaryButtonClass}
              disabled={journalActionId !== null}
              onClick={() => onStartEdit(journal)}
              type="button"
            >
              Edit note
            </button>
          )}
          <button
            className={secondaryButtonClass}
            disabled={journalActionId !== null}
            onClick={() => onDelete(journal)}
            type="button"
          >
            {journalActionId === `delete:${journal.id}` ? "Deleting..." : "Delete note"}
          </button>
        </div>
      ) : (
        <p className="mt-3 text-xs leading-5 text-zinc-500">
          This episode follows its conversation. Edit or clear the transcript to change it.
        </p>
      )}
    </article>
  );
}
