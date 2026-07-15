"use client";

import type { FormEvent } from "react";
import { useMemo, useState } from "react";

import { hasActiveMemoryConflict, memoryTypeLabel } from "./cognition";
import { EmptyExperience, IconButton, PageHeading, PrimaryButton, QuietButton, fieldClass } from "./experience-primitives";
import { Icon } from "./icons";
import type { MemoryItem, MemoryView } from "./types";

type MemoryFilter = "all" | "people" | "promises" | "moments" | "inside-jokes" | "patterns";

export function MemoryArchive({
  characterName,
  memories,
  forgottenMemories,
  memoryView,
  forgottenMemoriesLoading,
  memoryActionId,
  memoryContent,
  memoryType,
  memoryImportance,
  memoryPinned,
  editingMemoryId,
  memoryEditContent,
  setMemoryContent,
  setMemoryType,
  setMemoryImportance,
  setMemoryPinned,
  setEditingMemoryId,
  setMemoryEditContent,
  onAdd,
  onSaveEdit,
  onTogglePinned,
  onDelete,
  onForgetMemory,
  onRestoreMemory,
  onResolveConflict,
  onForget,
  onChangeView
}: {
  characterName: string;
  memories: MemoryItem[];
  forgottenMemories: MemoryItem[];
  memoryView: MemoryView;
  forgottenMemoriesLoading: boolean;
  memoryActionId: string | null;
  memoryContent: string;
  memoryType: string;
  memoryImportance: string;
  memoryPinned: boolean;
  editingMemoryId: string | null;
  memoryEditContent: string;
  setMemoryContent: (value: string) => void;
  setMemoryType: (value: string) => void;
  setMemoryImportance: (value: string) => void;
  setMemoryPinned: (value: boolean) => void;
  setEditingMemoryId: (value: string | null) => void;
  setMemoryEditContent: (value: string) => void;
  onAdd: (event: FormEvent<HTMLFormElement>) => void;
  onSaveEdit: (memory: MemoryItem) => void;
  onTogglePinned: (memory: MemoryItem) => void;
  onDelete: (memory: MemoryItem) => void;
  onForgetMemory: (memory: MemoryItem) => void;
  onRestoreMemory: (memory: MemoryItem) => void;
  onResolveConflict: (memory: MemoryItem) => void;
  onForget: () => void;
  onChangeView: (view: MemoryView) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [filter, setFilter] = useState<MemoryFilter>("all");
  const visible = memoryView === "active" ? memories : forgottenMemories;
  const filtered = useMemo(
    () => visible.filter((memory) => filter === "all" || memoryCategory(memory) === filter).sort(memoryOrder),
    [filter, visible]
  );
  const conflicts = memories.filter(hasActiveMemoryConflict);
  const archiveDescription = memoryArchiveDescription(memories, characterName);

  return (
    <div className="mx-auto w-full max-w-6xl px-5 pb-28 pt-8 sm:px-8 sm:pt-12 lg:px-12">
      <PageHeading
        action={<PrimaryButton onClick={() => setAdding((value) => !value)}><span className="flex items-center gap-2"><Icon className="h-4 w-4" name="plus" /> Hold onto something</span></PrimaryButton>}
        description={archiveDescription}
        eyebrow="Your private archive"
        title="Memories"
      />

      {adding ? (
        <form className="glass-surface mt-8 rounded-[1.75rem] p-5 reveal-up sm:p-7" onSubmit={(event) => { onAdd(event); if (memoryContent.trim()) setAdding(false); }}>
          <div className="flex items-start justify-between gap-4"><div><h2 className="font-eidolon-display text-2xl">What should stay with you?</h2><p className="mt-2 text-sm text-[#877e75]">Write it in your own words. You can change or release it whenever you like.</p></div><IconButton icon="close" label="Close memory form" onClick={() => setAdding(false)} /></div>
          <textarea autoFocus aria-label="Something to remember" className={`${fieldClass} mt-6 min-h-28 resize-none`} maxLength={1000} onChange={(event) => setMemoryContent(event.target.value)} placeholder="A person, a promise, a small ritual, something that mattered…" value={memoryContent} />
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <label className="text-xs text-[#8e857c]">Kind of memory<select className={`${fieldClass} mt-2`} onChange={(event) => setMemoryType(event.target.value)} value={memoryType}><option value="preference">A preference</option><option value="person">A person</option><option value="event">A shared moment</option><option value="inside_joke">An inside joke</option><option value="boundary">A boundary</option><option value="relationship_milestone">A milestone</option></select></label>
            <label className="text-xs text-[#8e857c]">How closely to keep it<select className={`${fieldClass} mt-2`} onChange={(event) => setMemoryImportance(event.target.value)} value={memoryImportance}><option value="0.35">Let it sit lightly</option><option value="0.6">Worth remembering</option><option value="0.85">Keep it close</option></select></label>
            <label className="flex items-center gap-3 self-end rounded-2xl border border-white/[0.09] px-4 py-3 text-sm text-[#c4b9ae]"><input checked={memoryPinned} onChange={(event) => setMemoryPinned(event.target.checked)} type="checkbox" /> Protect from fading</label>
          </div>
          <div className="mt-5 flex justify-end"><PrimaryButton disabled={!memoryContent.trim() || memoryActionId !== null} type="submit">{memoryActionId === "add" ? "Keeping it…" : "Keep this memory"}</PrimaryButton></div>
        </form>
      ) : null}

      {conflicts.length > 0 && memoryView === "active" ? (
        <div className="mt-8 flex items-start gap-3 rounded-2xl border border-[#b98265]/25 bg-[#b98265]/[0.07] px-4 py-4 text-sm text-[#c9aa99]"><Icon className="mt-0.5 h-4 w-4 shrink-0" name="sparkles" /><p>Two recollections no longer quite agree. You can choose which version feels true now.</p></div>
      ) : null}

      <div className="mt-9 flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div className="hide-scrollbar flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="Memory categories">
          {(["all", "people", "promises", "moments", "inside-jokes", "patterns"] as MemoryFilter[]).map((item) => <button aria-selected={filter === item} className={`shrink-0 rounded-full border px-4 py-2 text-xs capitalize transition ${filter === item ? "border-[#b98265]/35 bg-[#b98265]/10 text-[#d5aa94]" : "border-white/[0.08] text-[#837b73] hover:border-white/[0.16]"}`} key={item} onClick={() => setFilter(item)} role="tab" type="button">{item.replace("-", " ")}</button>)}
        </div>
        <div className="flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.02] p-1">
          <button aria-pressed={memoryView === "active"} className={`rounded-full px-4 py-2 text-xs transition ${memoryView === "active" ? "bg-white/[0.08] text-[#dfd4c9]" : "text-[#756e67]"}`} onClick={() => onChangeView("active")} type="button">Held close</button>
          <button aria-pressed={memoryView === "forgotten"} className={`rounded-full px-4 py-2 text-xs transition ${memoryView === "forgotten" ? "bg-white/[0.08] text-[#dfd4c9]" : "text-[#756e67]"}`} onClick={() => onChangeView("forgotten")} type="button">Allowed to fade</button>
        </div>
      </div>

      {forgottenMemoriesLoading && memoryView === "forgotten" ? <p className="py-16 text-center text-sm text-[#817970]">Looking through what has faded…</p> : null}
      {!forgottenMemoriesLoading && filtered.length === 0 ? (
        <EmptyExperience icon={memoryView === "forgotten" ? "moon" : "bookmark"} title={memoryView === "forgotten" ? "Nothing has faded" : "The archive is still quiet"}>
          <p>{memoryView === "forgotten" ? "Memories you release will rest here, outside future conversations, until you choose otherwise." : `${characterName} will begin noticing meaningful details as you talk. You can also keep something here yourself.`}</p>
        </EmptyExperience>
      ) : null}

      <div className="mt-6 columns-1 gap-4 md:columns-2 xl:columns-3">
        {filtered.map((memory) => (
          <MemoryCard
            editing={editingMemoryId === memory.id}
            editValue={memoryEditContent}
            key={memory.id}
            memory={memory}
            memoryActionId={memoryActionId}
            onDelete={onDelete}
            onEdit={() => {
              if (editingMemoryId === memory.id) {
                setEditingMemoryId(null);
              } else {
                setEditingMemoryId(memory.id);
                setMemoryEditContent(memory.content);
              }
            }}
            onEditValue={setMemoryEditContent}
            onForget={onForgetMemory}
            onResolveConflict={onResolveConflict}
            onRestore={onRestoreMemory}
            onSaveEdit={onSaveEdit}
            onTogglePinned={onTogglePinned}
            view={memoryView}
          />
        ))}
      </div>

      {memoryView === "active" && memories.length > 0 ? <div className="mt-12 flex flex-col items-start justify-between gap-4 border-t border-white/[0.07] pt-7 sm:flex-row sm:items-center"><div><p className="text-sm text-[#b9aea3]">Let old details soften naturally</p><p className="mt-1 text-xs text-[#746d66]">Only memories that have grown stale and unimportant will be released.</p></div><QuietButton disabled={memoryActionId !== null} onClick={onForget}>{memoryActionId === "forget-stale" ? "Listening for what can fade…" : "Let the quiet things fade"}</QuietButton></div> : null}
    </div>
  );
}

function MemoryCard({ memory, view, editing, editValue, memoryActionId, onEditValue, onEdit, onSaveEdit, onTogglePinned, onForget, onRestore, onResolveConflict, onDelete }: { memory: MemoryItem; view: MemoryView; editing: boolean; editValue: string; memoryActionId: string | null; onEditValue: (value: string) => void; onEdit: () => void; onSaveEdit: (memory: MemoryItem) => void; onTogglePinned: (memory: MemoryItem) => void; onForget: (memory: MemoryItem) => void; onRestore: (memory: MemoryItem) => void; onResolveConflict: (memory: MemoryItem) => void; onDelete: (memory: MemoryItem) => void }) {
  const conflict = hasActiveMemoryConflict(memory);
  return (
    <article className="mb-4 break-inside-avoid rounded-[1.5rem] border border-white/[0.08] bg-white/[0.025] p-5 transition hover:border-white/[0.14] hover:bg-white/[0.035]">
      <div className="flex items-center justify-between gap-3"><span className="flex items-center gap-2 text-[0.66rem] uppercase tracking-[0.14em] text-[#8e7e73]"><Icon className="h-3.5 w-3.5 text-[#b98265]" name={memoryIcon(memory)} />{memoryTypeLabel(memory.memory_type)}</span>{memory.pinned ? <span title="Protected from fading"><Icon className="h-4 w-4 text-[#b98265]" name="bookmark" /></span> : null}</div>
      {editing ? <textarea autoFocus aria-label="Edit memory" className={`${fieldClass} mt-5 min-h-28 resize-none`} maxLength={1000} onChange={(event) => onEditValue(event.target.value)} value={editValue} /> : <p className="mt-5 whitespace-pre-wrap font-eidolon-display text-xl leading-7 text-[#dfd5ca]">{memory.content}</p>}
      <p className="mt-5 text-[0.67rem] text-[#6f6861]">{memoryOrigin(memory)} · {formatMemoryDate(memory.created_at)}</p>
      {conflict && view === "active" ? <div className="mt-4 rounded-xl bg-[#b98265]/[0.08] p-3 text-xs leading-5 text-[#bd9986]"><p>This no longer matches another memory.</p><button className="mt-2 text-[#d6aa92] underline decoration-[#b98265]/40 underline-offset-4" disabled={memoryActionId !== null} onClick={() => onResolveConflict(memory)} type="button">Keep this version</button></div> : null}
      <div className="mt-5 flex flex-wrap gap-2 border-t border-white/[0.07] pt-4">
        {view === "forgotten" ? <QuietButton disabled={memoryActionId !== null} onClick={() => onRestore(memory)}>Bring back</QuietButton> : editing ? <><PrimaryButton disabled={!editValue.trim() || memoryActionId !== null} onClick={() => onSaveEdit(memory)}>Save</PrimaryButton><QuietButton onClick={onEdit}>Cancel</QuietButton></> : <><QuietButton disabled={memoryActionId !== null} onClick={onEdit}>Edit</QuietButton><QuietButton disabled={memoryActionId !== null} onClick={() => onTogglePinned(memory)}>{memory.pinned ? "Let it soften" : "Keep close"}</QuietButton><QuietButton disabled={memoryActionId !== null} onClick={() => onForget(memory)}>Let fade</QuietButton></>}
        <IconButton className="ml-auto h-10 w-10 border-transparent" disabled={memoryActionId !== null} icon="trash" label={view === "forgotten" ? "Delete permanently" : "Delete memory"} onClick={() => onDelete(memory)} />
      </div>
    </article>
  );
}

function memoryCategory(memory: MemoryItem): MemoryFilter {
  if (memory.memory_type === "person") return "people";
  if (memory.memory_type === "inside_joke") return "inside-jokes";
  if (["event", "shared_moment", "relationship_milestone", "date", "place"].includes(memory.memory_type)) return "moments";
  if (["boundary", "promise"].includes(memory.memory_type)) return "promises";
  return "patterns";
}

function memoryOrder(left: MemoryItem, right: MemoryItem): number {
  return Number(right.pinned) - Number(left.pinned) || Date.parse(right.created_at) - Date.parse(left.created_at);
}

function memoryIcon(memory: MemoryItem): "bookmark" | "heart" | "user" | "sparkles" | "shield" {
  const category = memoryCategory(memory);
  if (category === "people") return "user";
  if (category === "promises") return "shield";
  if (category === "moments") return "heart";
  if (category === "inside-jokes") return "sparkles";
  return "bookmark";
}

function memoryOrigin(memory: MemoryItem): string {
  const source = memory.metadata_json.source;
  if (source === "manual") return "Kept by you";
  if (source === "user_saved") return "Held from a conversation";
  if (source === "extracted") return "Something that stood out";
  return "Part of your shared history";
}

function formatMemoryDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { month: "long", day: "numeric", year: "numeric" }).format(new Date(value));
}

function memoryArchiveDescription(memories: MemoryItem[], name: string): string {
  if (memories.length === 0) return `This is where the details that matter to you and ${name} will gather—the things worth carrying gently into what comes next.`;
  if (memories.length < 4) return `${name} has begun to hold onto a few things. The archive will become richer as your shared language grows.`;
  return `People, promises, patterns, and small moments ${name} can carry gently into future conversations.`;
}
