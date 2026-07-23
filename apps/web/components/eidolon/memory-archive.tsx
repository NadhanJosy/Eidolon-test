"use client";

import type { FormEvent } from "react";
import { useMemo, useState } from "react";

import { hasActiveMemoryConflict, memoryTypeLabel } from "./cognition";
import { EmptyExperience, IconButton, PageHeading, PrimaryButton, QuietButton, fieldClass } from "./experience-primitives";
import { Icon } from "./icons";
import type { MemoryCategory, MemoryItem, MemoryView } from "./types";

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
  onClearCategory,
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
  onClearCategory: (category: MemoryCategory) => Promise<boolean>;
  onChangeView: (view: MemoryView) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [filter, setFilter] = useState<MemoryFilter>("all");
  const [query, setQuery] = useState("");
  const [pendingClear, setPendingClear] = useState<MemoryCategory | null>(null);
  const visible = memoryView === "active" ? memories : forgottenMemories;
  const filtered = useMemo(
    () => {
      const normalizedQuery = query.trim().toLocaleLowerCase();
      return visible
        .filter((memory) => filter === "all" || memoryCategory(memory) === filter)
        .filter((memory) => !normalizedQuery || memorySearchText(memory).includes(normalizedQuery))
        .sort(memoryOrder);
    },
    [filter, query, visible]
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
        <form className="glass-surface mt-8 rounded-[1.75rem] p-5 reveal-up sm:p-7" onSubmit={onAdd}>
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
          {(["all", "people", "promises", "moments", "inside-jokes", "patterns"] as MemoryFilter[]).map((item) => <button aria-selected={filter === item} className={`min-h-11 shrink-0 rounded-full border px-4 py-2 text-xs capitalize transition ${filter === item ? "border-[#b98265]/35 bg-[#b98265]/10 text-[#d5aa94]" : "border-white/[0.08] text-[#837b73] hover:border-white/[0.16]"}`} key={item} onClick={() => { setFilter(item); setPendingClear(null); }} role="tab" type="button">{item.replace("-", " ")}</button>)}
        </div>
        <div className="flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.02] p-1">
          <button aria-pressed={memoryView === "active"} className={`min-h-11 rounded-full px-4 py-2 text-xs transition ${memoryView === "active" ? "bg-white/[0.08] text-[#dfd4c9]" : "text-[#756e67]"}`} onClick={() => onChangeView("active")} type="button">Held close</button>
          <button aria-pressed={memoryView === "forgotten"} className={`min-h-11 rounded-full px-4 py-2 text-xs transition ${memoryView === "forgotten" ? "bg-white/[0.08] text-[#dfd4c9]" : "text-[#756e67]"}`} onClick={() => onChangeView("forgotten")} type="button">Allowed to fade</button>
        </div>
      </div>

      <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center">
        <label className="relative flex-1"><span className="sr-only">Search memories</span><Icon className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#776f68]" name="search" /><input className={`${fieldClass} pl-11`} maxLength={120} onChange={(event) => setQuery(event.target.value)} placeholder="Search people, places, promises, or moments" value={query} /></label>
        {memoryView === "active" && filter !== "all" && filtered.length > 0 ? pendingClear === clearCategoryForFilter(filter) ? <div className="flex items-center gap-2 rounded-full border border-[#ad675a]/20 bg-[#6c3028]/[0.06] p-1 pl-4 text-xs text-[#b98c82]"><span>Permanently remove this category?</span><QuietButton disabled={memoryActionId !== null} onClick={() => { const category = clearCategoryForFilter(filter); if (category) void onClearCategory(category).then((cleared) => { if (cleared) setPendingClear(null); }); }}>Remove</QuietButton><QuietButton onClick={() => setPendingClear(null)}>Cancel</QuietButton></div> : <QuietButton disabled={memoryActionId !== null} onClick={() => setPendingClear(clearCategoryForFilter(filter))}>Clear this category</QuietButton> : null}
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
      <p className="mt-5 text-[0.67rem] text-[#6f6861]">{memoryOrigin(memory)} · {formatMemoryDate(memory.last_evidence_at ?? memory.created_at)}</p>
      <div className="mt-3 flex flex-wrap gap-2 text-[0.63rem] text-[#857a71]">{memory.reinforcement_count > 1 ? <span className="rounded-full bg-white/[0.04] px-2.5 py-1">Confirmed {memory.reinforcement_count} times</span> : null}<span className="rounded-full bg-white/[0.04] px-2.5 py-1">{memoryRetentionLabel(memory)}</span>{memory.sensitivity === "sensitive" ? <span className="rounded-full bg-white/[0.04] px-2.5 py-1">Private detail</span> : null}</div>
      {memoryEmotionalMeaning(memory) ? <p className="mt-3 text-xs leading-5 text-[#8f8178]">{memoryEmotionalMeaning(memory)}</p> : null}
      {conflict && view === "active" ? <div className="mt-4 rounded-xl bg-[#b98265]/[0.08] p-3 text-xs leading-5 text-[#bd9986]"><p>This no longer matches another memory.</p><button className="mt-2 min-h-11 text-[#d6aa92] underline decoration-[#b98265]/40 underline-offset-4" disabled={memoryActionId !== null} onClick={() => onResolveConflict(memory)} type="button">Keep this version</button></div> : null}
      <div className="mt-5 flex flex-wrap gap-2 border-t border-white/[0.07] pt-4">
        {view === "forgotten" ? memory.lifecycle_state === "superseded" ? <span className="py-3 text-xs text-[#85776f]">Kept as correction history</span> : <QuietButton disabled={memoryActionId !== null} onClick={() => onRestore(memory)}>Bring back</QuietButton> : editing ? <><PrimaryButton disabled={!editValue.trim() || memoryActionId !== null} onClick={() => onSaveEdit(memory)}>Save</PrimaryButton><QuietButton onClick={onEdit}>Cancel</QuietButton></> : <><QuietButton disabled={memoryActionId !== null} onClick={onEdit}>Edit</QuietButton><QuietButton disabled={memoryActionId !== null} onClick={() => onTogglePinned(memory)}>{memory.pinned ? "Let it soften" : "Keep close"}</QuietButton><QuietButton disabled={memoryActionId !== null} onClick={() => onForget(memory)}>Let fade</QuietButton></>}
        <IconButton className="ml-auto border-transparent" disabled={memoryActionId !== null} icon="trash" label={view === "forgotten" ? "Delete permanently" : "Delete memory"} onClick={() => onDelete(memory)} />
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
  return Number(right.pinned) - Number(left.pinned) || Date.parse(right.last_evidence_at ?? right.created_at) - Date.parse(left.last_evidence_at ?? left.created_at);
}

function clearCategoryForFilter(filter: MemoryFilter): MemoryCategory | null {
  if (filter === "inside-jokes") return "inside_jokes";
  return filter === "people" || filter === "promises" || filter === "moments" || filter === "patterns" ? filter : null;
}

function memorySearchText(memory: MemoryItem): string {
  const entities = Array.isArray(memory.metadata_json.entity_keys)
    ? memory.metadata_json.entity_keys.filter((item): item is string => typeof item === "string")
    : [];
  return [memory.content, memory.memory_type, ...entities].join(" ").toLocaleLowerCase();
}

function memoryRetentionLabel(memory: MemoryItem): string {
  if (memory.pinned || memory.retention_tier === "core") return "Protected from fading";
  if (memory.retention_tier === "transient") return "May soften sooner";
  return "Fades only when quiet and stale";
}

function memoryEmotionalMeaning(memory: MemoryItem): string {
  const context = memory.emotional_context_json;
  for (const key of ["meaning", "feeling", "helped", "hurt", "resolution"]) {
    const value = context[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
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
