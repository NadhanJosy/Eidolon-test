import type { FormEvent } from "react";

import {
  hasActiveMemoryConflict,
  memoryFreshness,
  memoryOverviewCards,
  memoryResonance,
  memorySourceLabel,
  memoryTypeLabel,
  toneClass,
  type SummaryCard
} from "../cognition";
import type { MemoryItem } from "../types";
import type { MemoryView } from "../use-knowledge-controller";
import {
  EmptyState,
  formatTimestamp,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass
} from "../ui";

export function MemoryPanel({
  memories,
  forgottenMemories,
  memoryView,
  memoryActionId,
  forgottenMemoriesLoading,
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
  memories: MemoryItem[];
  forgottenMemories: MemoryItem[];
  memoryView: MemoryView;
  memoryActionId: string | null;
  forgottenMemoriesLoading: boolean;
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
  const visibleMemories = memoryView === "active" ? memories : forgottenMemories;
  const orderedMemories = [...visibleMemories].sort(
    (left, right) =>
      Number(right.pinned) - Number(left.pinned) ||
      right.importance - left.importance ||
      new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
  );
  const contradictionCount = memories.filter((memory) => hasActiveMemoryConflict(memory)).length;
  const overviewCards = memoryOverviewCards(memories);

  return (
    <>
      <div className="grid grid-cols-3 gap-2">
        {overviewCards.map((card) => (
          <MemoryStat card={card} key={card.label} />
        ))}
      </div>
      <div className="grid grid-cols-2 rounded-md border border-line bg-ink p-1">
        <MemoryViewButton
          active={memoryView === "active"}
          count={memories.length}
          label="Active"
          onClick={() => onChangeView("active")}
        />
        <MemoryViewButton
          active={memoryView === "forgotten"}
          count={forgottenMemories.length}
          label="Forgotten"
          onClick={() => onChangeView("forgotten")}
        />
      </div>
      {memoryView === "active" && contradictionCount > 0 ? (
        <p className="rounded-md border border-ember bg-amber-950/50 px-3 py-2 text-xs text-amber-100">
          Some memories disagree with earlier recall. Review them before leaning on either version.
        </p>
      ) : null}
      {memoryView === "active" ? (
        <form className="space-y-2" onSubmit={onAdd}>
        <textarea
          aria-label="New memory"
          className={`${inputClass} min-h-16 resize-none`}
          maxLength={1000}
          value={memoryContent}
          onChange={(event) => setMemoryContent(event.target.value)}
          placeholder="Memory"
        />
        <div className="grid grid-cols-2 gap-2">
          <select
            aria-label="Memory type"
            className={inputClass}
            value={memoryType}
            onChange={(event) => setMemoryType(event.target.value)}
          >
            <option value="preference">preference</option>
            <option value="event">event</option>
            <option value="inside_joke">inside joke</option>
            <option value="boundary">boundary</option>
            <option value="relationship_milestone">milestone</option>
          </select>
          <select
            className={inputClass}
            value={memoryImportance}
            onChange={(event) => setMemoryImportance(event.target.value)}
            aria-label="Memory staying power"
          >
            <option value="0.35">light note</option>
            <option value="0.6">worth keeping</option>
            <option value="0.85">core anchor</option>
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm text-zinc-300">
          <input
            type="checkbox"
            checked={memoryPinned}
            onChange={(event) => setMemoryPinned(event.target.checked)}
          />
          Pinned
        </label>
        <div className="flex flex-wrap gap-2">
          <button className={primaryButtonClass} disabled={memoryActionId !== null} type="submit">
            {memoryActionId === "add" ? "Saving..." : "Add memory"}
          </button>
          <button
            className={secondaryButtonClass}
            disabled={memoryActionId !== null}
            onClick={onForget}
            type="button"
          >
            {memoryActionId === "forget-stale" ? "Reviewing..." : "Let stale memories fade"}
          </button>
        </div>
        </form>
      ) : (
        <p className="rounded-md border border-line bg-ink px-3 py-2 text-xs leading-5 text-zinc-400">
          Forgotten memories stay out of replies and relationship context. Restore one to make it
          available for recall again, or delete it permanently.
        </p>
      )}
      <div className="space-y-2">
        {forgottenMemoriesLoading && memoryView === "forgotten" ? (
          <EmptyState text="Looking through faded memories..." />
        ) : null}
        {!forgottenMemoriesLoading && visibleMemories.length === 0 ? (
          <EmptyState
            text={
              memoryView === "active"
                ? "Nothing durable has been saved yet. Important details can be added here or learned from chat."
                : "Nothing has faded from active recall."
            }
          />
        ) : null}
        {!forgottenMemoriesLoading && orderedMemories.map((memory) => (
          <article className="rounded-md border border-line bg-ink p-3 text-sm" key={memory.id}>
            <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
              <span className="rounded border border-line bg-panel px-2 py-1">
                {memoryTypeLabel(memory.memory_type)}
              </span>
              {memory.pinned ? (
                <span className="rounded border border-moss bg-lime-950/40 px-2 py-1 text-lime-100">
                  pinned
                </span>
              ) : null}
              {memory.forgotten_at ? (
                <span className="rounded border border-line bg-panel px-2 py-1 text-zinc-400">
                  out of recall
                </span>
              ) : null}
              <span>{formatTimestamp(memory.created_at)}</span>
            </div>
            {memoryView === "active" && editingMemoryId === memory.id ? (
              <textarea
                aria-label="Edit memory"
                className={`${inputClass} min-h-20 resize-none`}
                maxLength={1000}
                value={memoryEditContent}
                onChange={(event) => setMemoryEditContent(event.target.value)}
              />
            ) : (
              <p>{memory.content}</p>
            )}
            <div className="mt-3 grid gap-2 text-xs text-zinc-500 sm:grid-cols-3">
              <MemoryTrait label="Resonance" value={memoryResonance(memory)} />
              <MemoryTrait label="Freshness" value={memoryFreshness(memory)} />
              <MemoryTrait label="Source" value={memorySourceLabel(memory)} />
            </div>
            {memory.last_recalled_at ? (
              <p className="mt-2 text-xs text-zinc-500">
                Brought back into context {formatTimestamp(memory.last_recalled_at)}
              </p>
            ) : null}
            {memory.forgotten_at ? (
              <p className="mt-2 text-xs text-zinc-500">
                Left active recall {formatTimestamp(memory.forgotten_at)}
              </p>
            ) : null}
            {memoryView === "active" && hasActiveMemoryConflict(memory) ? (
              <div className="mt-2 rounded border border-ember bg-amber-950/40 px-2 py-2 text-xs text-amber-100">
                <p>This memory conflicts with another preference or fact.</p>
                <button
                  className={`${secondaryButtonClass} mt-2 border-amber-700 text-amber-100`}
                  disabled={memoryActionId !== null}
                  onClick={() => void onResolveConflict(memory)}
                  type="button"
                >
                  Keep this version
                </button>
              </div>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-2">
              {memoryView === "forgotten" ? (
                <button
                  className={primaryButtonClass}
                  disabled={memoryActionId !== null}
                  onClick={() => void onRestoreMemory(memory)}
                  type="button"
                >
                  {memoryActionId === memory.id ? "Restoring..." : "Restore to recall"}
                </button>
              ) : editingMemoryId === memory.id ? (
                <button
                  className={primaryButtonClass}
                  disabled={memoryActionId !== null}
                  onClick={() => void onSaveEdit(memory)}
                  type="button"
                >
                  {memoryActionId === memory.id ? "Saving..." : "Save"}
                </button>
              ) : (
                <button
                  className={secondaryButtonClass}
                  disabled={memoryActionId !== null}
                  onClick={() => {
                    setEditingMemoryId(memory.id);
                    setMemoryEditContent(memory.content);
                  }}
                  type="button"
                >
                  Edit
                </button>
              )}
              {memoryView === "active" ? (
                <>
                  <button
                    className={secondaryButtonClass}
                    disabled={memoryActionId !== null}
                    onClick={() => void onTogglePinned(memory)}
                    type="button"
                  >
                    {memory.pinned ? "Unpin" : "Pin"}
                  </button>
                  <button
                    className={secondaryButtonClass}
                    disabled={memoryActionId !== null}
                    onClick={() => void onForgetMemory(memory)}
                    type="button"
                  >
                    {memoryActionId === memory.id ? "Forgetting..." : "Forget"}
                  </button>
                </>
              ) : null}
              <button
                className={secondaryButtonClass}
                disabled={memoryActionId !== null}
                onClick={() => void onDelete(memory)}
                type="button"
              >
                {memoryView === "forgotten" ? "Delete permanently" : "Delete"}
              </button>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}

function MemoryViewButton({
  active,
  count,
  label,
  onClick
}: {
  active: boolean;
  count: number;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      aria-pressed={active}
      className={`flex items-center justify-center gap-2 rounded px-3 py-2 text-sm ${
        active ? "bg-panel text-paper" : "text-zinc-500 hover:text-zinc-300"
      }`}
      onClick={onClick}
      type="button"
    >
      <span>{label}</span>
      <span className="rounded bg-black/20 px-1.5 py-0.5 text-xs">{count}</span>
    </button>
  );
}

function MemoryStat({ card }: { card: SummaryCard }) {
  return (
    <div className={`rounded-md border p-2 ${toneClass(card.tone)}`}>
      <p className="text-[11px] uppercase text-zinc-600">{card.label}</p>
      <p className="mt-1 text-sm font-medium text-zinc-200">{card.value}</p>
      <p className="mt-1 line-clamp-2 text-xs text-zinc-500">{card.detail}</p>
    </div>
  );
}

function MemoryTrait({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-line bg-panel px-2 py-1">
      <span>{label}</span> <span className="text-zinc-300">{value}</span>
    </div>
  );
}
