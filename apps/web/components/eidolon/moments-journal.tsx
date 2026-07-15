"use client";

import type { FormEvent } from "react";
import { useMemo, useState } from "react";

import { journalIsAdultRedacted, journalResonance } from "./cognition";
import { EmptyExperience, IconButton, PageHeading, PrimaryButton, QuietButton, fieldClass } from "./experience-primitives";
import { Icon } from "./icons";
import type { Journal } from "./types";

export function MomentsJournal({
  characterName,
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
  characterName: string;
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
  const [writing, setWriting] = useState(false);
  const ordered = useMemo(() => [...journals].sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at)), [journals]);
  const years = [...new Set(ordered.map((journal) => new Date(journal.created_at).getFullYear()))];

  return (
    <div className="mx-auto w-full max-w-6xl px-5 pb-28 pt-8 sm:px-8 sm:pt-12 lg:px-12">
      <PageHeading
        action={<PrimaryButton onClick={() => setWriting((value) => !value)}><span className="flex items-center gap-2"><Icon className="h-4 w-4" name="edit" /> Add a reflection</span></PrimaryButton>}
        description={`The days and conversations that became part of the story between you and ${characterName}—kept as reflections, not transcripts.`}
        eyebrow="A shared journal"
        title="Moments"
      />

      {writing ? (
        <form className="glass-surface mt-8 rounded-[1.75rem] p-5 reveal-up sm:p-7" onSubmit={onAdd}>
          <div className="flex items-start justify-between gap-4"><div><h2 className="font-eidolon-display text-2xl">Leave a note for the two of you</h2><p className="mt-2 text-sm text-[#877e75]">Your reflection becomes part of your shared history, in the words you choose.</p></div><IconButton icon="close" label="Close reflection form" onClick={() => setWriting(false)} /></div>
          <div className="mt-6 grid gap-4 sm:grid-cols-[0.7fr_1.3fr]">
            <input aria-label="Reflection title" className={fieldClass} maxLength={200} onChange={(event) => setTitle(event.target.value)} placeholder="A name for this moment" value={title} />
            <textarea aria-label="Reflection" className={`${fieldClass} min-h-28 resize-none`} maxLength={2000} onChange={(event) => setSummary(event.target.value)} placeholder="What happened, what it meant, or what you want to return to…" value={summary} />
          </div>
          <div className="mt-5 flex justify-end"><PrimaryButton disabled={!title.trim() || !summary.trim() || journalActionId !== null} type="submit">{journalActionId === "add" ? "Writing it down…" : "Keep this reflection"}</PrimaryButton></div>
        </form>
      ) : null}

      {ordered.length === 0 ? (
        <EmptyExperience action={<QuietButton onClick={() => setWriting(true)}>Write the first reflection</QuietButton>} icon="book" title="The first page is still unwritten"><p>Meaningful exchanges will gather here as quiet chapters. You can also add a reflection in your own words.</p></EmptyExperience>
      ) : (
        <div className="mt-12">
          <div className="mb-10 flex flex-wrap items-center gap-4 text-xs text-[#766f68]"><span className="flex items-center gap-2"><Icon className="h-4 w-4 text-[#9f7965]" name="book" /> Your story with {characterName}</span><span className="h-px flex-1 bg-white/[0.07]" />{years.map((year) => <span key={year}>{year}</span>)}</div>
          <div className="space-y-16">
            {ordered.map((journal, index) => <MomentEntry
              characterName={characterName}
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
              prominent={index === 0}
              setEditSummary={setEditSummary}
              setEditTitle={setEditTitle}
            />)}
          </div>
        </div>
      )}
    </div>
  );
}

function MomentEntry({ journal, characterName, prominent, editing, editTitle, editSummary, journalActionId, setEditTitle, setEditSummary, onStartEdit, onCancelEdit, onSaveEdit, onDelete }: { journal: Journal; characterName: string; prominent: boolean; editing: boolean; editTitle: string; editSummary: string; journalActionId: string | null; setEditTitle: (value: string) => void; setEditSummary: (value: string) => void; onStartEdit: (journal: Journal) => void; onCancelEdit: () => void; onSaveEdit: (journal: Journal) => void; onDelete: (journal: Journal) => void }) {
  const manual = journal.metadata_json.source === "manual";
  const redacted = journalIsAdultRedacted(journal);
  const callbacks = journal.callbacks_json.filter(Boolean).slice(0, 3);
  const unresolved = journal.unresolved_threads_json.filter(Boolean).slice(0, 3);
  return (
    <article className={`relative grid gap-5 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-9 ${prominent ? "reveal-up" : ""}`}>
      <div className="sm:text-right"><p className="font-eidolon-display text-2xl text-[#c9bcb0]">{dayNumber(journal.created_at)}</p><p className="mt-1 text-[0.67rem] uppercase tracking-[0.14em] text-[#766e67]">{monthYear(journal.created_at)}</p><span className="mt-4 hidden h-px bg-gradient-to-l from-[#b98265]/30 to-transparent sm:block" /></div>
      <div className={`relative rounded-[1.75rem] border p-6 sm:p-8 ${prominent ? "border-[#b98265]/18 bg-[radial-gradient(circle_at_90%_0%,rgba(169,105,75,0.1),transparent_40%),rgba(255,255,255,0.025)]" : "border-white/[0.08] bg-white/[0.02]"}`}>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 flex-1">
            <p className="text-[0.65rem] uppercase tracking-[0.17em] text-[#9b7967]">{manual ? "Your reflection" : humanMomentType(journalResonance(journal))}</p>
            {editing ? <input aria-label="Reflection title" className={`${fieldClass} mt-3`} maxLength={200} onChange={(event) => setEditTitle(event.target.value)} value={editTitle} /> : <h2 className="mt-3 font-eidolon-display text-3xl leading-tight text-[#e0d5ca] sm:text-4xl">{journal.title}</h2>}
          </div>
          {prominent ? <span className="flex shrink-0 items-center gap-2 rounded-full border border-[#b98265]/15 bg-[#b98265]/[0.06] px-3 py-1.5 text-[0.65rem] text-[#a98775]"><Icon className="h-3 w-3" name="sparkles" /> Most recent</span> : null}
        </div>
        {editing ? <textarea aria-label="Reflection summary" className={`${fieldClass} mt-5 min-h-36 resize-none`} maxLength={2000} onChange={(event) => setEditSummary(event.target.value)} value={editSummary} /> : <p className="mt-6 whitespace-pre-wrap text-sm leading-7 text-[#a69c92] sm:text-[0.95rem]">{humanJournalSummary(journal.summary, characterName)}</p>}

        {redacted ? <p className="mt-5 flex items-start gap-2 text-xs leading-5 text-[#7e746d]"><Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" name="lock" /> Intimate details were intentionally left private; only the emotional shape of the moment remains.</p> : null}

        {!editing && (callbacks.length > 0 || unresolved.length > 0 || journal.emotional_tags_json.length > 0) ? (
          <details className="group mt-7 border-t border-white/[0.07] pt-5">
            <summary className="flex cursor-pointer list-none items-center justify-between text-xs text-[#8b8178]">What this moment still carries <Icon className="h-4 w-4 transition group-open:rotate-180" name="chevron-down" /></summary>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              {callbacks.length > 0 ? <MomentContext icon="sparkles" label="Worth calling back to" items={callbacks} /> : null}
              {unresolved.length > 0 ? <MomentContext icon="moon" label="Still unfolding" items={unresolved} /> : null}
              {journal.emotional_tags_json.length > 0 ? <div className="sm:col-span-2 flex flex-wrap gap-2">{journal.emotional_tags_json.slice(0, 6).map((tag) => <span className="rounded-full border border-white/[0.08] px-3 py-1 text-[0.66rem] text-[#817970]" key={tag}>{humanTag(tag)}</span>)}</div> : null}
            </div>
          </details>
        ) : null}

        {manual ? <div className="mt-6 flex flex-wrap gap-2">{editing ? <><PrimaryButton disabled={!editTitle.trim() || !editSummary.trim() || journalActionId !== null} onClick={() => onSaveEdit(journal)}>{journalActionId === `save:${journal.id}` ? "Saving…" : "Save reflection"}</PrimaryButton><QuietButton disabled={journalActionId !== null} onClick={onCancelEdit}>Cancel</QuietButton></> : <><QuietButton disabled={journalActionId !== null} onClick={() => onStartEdit(journal)}>Edit reflection</QuietButton><IconButton className="border-transparent" disabled={journalActionId !== null} icon="trash" label="Delete reflection" onClick={() => onDelete(journal)} /></>}</div> : null}
      </div>
    </article>
  );
}

function MomentContext({ icon, label, items }: { icon: "moon" | "sparkles"; label: string; items: string[] }) {
  return <div className="rounded-2xl bg-black/20 p-4"><p className="flex items-center gap-2 text-[0.65rem] uppercase tracking-[0.14em] text-[#86786e]"><Icon className="h-3.5 w-3.5 text-[#a57b65]" name={icon} />{label}</p><ul className="mt-3 space-y-2 text-xs leading-5 text-[#8d847b]">{items.map((item) => <li key={item}>{item}</li>)}</ul></div>;
}

function dayNumber(value: string): string { return new Intl.DateTimeFormat(undefined, { day: "2-digit" }).format(new Date(value)); }
function monthYear(value: string): string { return new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" }).format(new Date(value)); }
function humanMomentType(value: string): string { const labels: Record<string, string> = { episode: "A shared chapter", "shared moment": "A moment that lingered", "repair arc": "A return to each other", milestone: "A quiet landmark", anniversary: "A date worth holding", "inside joke": "Something only you understand", "private episode": "A private chapter", "open thread": "A story still unfolding", "callback ready": "Something worth returning to", "emotional marker": "A feeling that stayed" }; return labels[value] ?? "A shared chapter"; }
function humanTag(value: string): string { return value.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase()); }

function humanJournalSummary(summary: string, characterName: string): string {
  const generated = summary.match(
    /^User brought up:\s*([\s\S]*?)\s*Character responded around:\s*([\s\S]*)$/u
  );
  if (!generated) {
    return summary;
  }
  const shared = generated[1].replace(/[.\s]+$/u, "");
  const response = generated[2].trim();
  return `You shared, “${shared}.”\n\n${characterName} answered, “${response}”`;
}
