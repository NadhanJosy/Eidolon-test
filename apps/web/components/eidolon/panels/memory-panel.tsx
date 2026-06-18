import type { FormEvent } from "react";

import type { MemoryItem } from "../types";
import {
  EmptyState,
  formatMetric,
  formatTimestamp,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass
} from "../ui";

export function MemoryPanel({
  memories,
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
  onForget
}: {
  memories: MemoryItem[];
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
  onForget: () => void;
}) {
  const orderedMemories = [...memories].sort(
    (left, right) =>
      Number(right.pinned) - Number(left.pinned) ||
      right.importance - left.importance ||
      new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
  );
  const pinnedCount = memories.filter((memory) => memory.pinned).length;
  const contradictionCount = memories.filter((memory) => memory.contradiction_group).length;
  const averageConfidence =
    memories.length === 0
      ? 0
      : memories.reduce((total, memory) => total + memory.confidence, 0) / memories.length;

  return (
    <>
      <div className="grid grid-cols-3 gap-2">
        <MemoryStat label="Stored" value={memories.length.toString()} />
        <MemoryStat label="Pinned" value={pinnedCount.toString()} />
        <MemoryStat label="Trust" value={formatMetric(averageConfidence)} />
      </div>
      {contradictionCount > 0 ? (
        <p className="rounded-md border border-ember bg-amber-950/50 px-3 py-2 text-xs text-amber-100">
          {contradictionCount} contradiction group{contradictionCount === 1 ? "" : "s"} need review.
        </p>
      ) : null}
      <form className="space-y-2" onSubmit={onAdd}>
        <textarea
          className={`${inputClass} min-h-16 resize-none`}
          value={memoryContent}
          onChange={(event) => setMemoryContent(event.target.value)}
          placeholder="Memory"
        />
        <div className="grid grid-cols-2 gap-2">
          <select
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
          <input
            className={inputClass}
            value={memoryImportance}
            onChange={(event) => setMemoryImportance(event.target.value)}
            inputMode="decimal"
            aria-label="Memory importance"
          />
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
          <button className={primaryButtonClass} type="submit">
            Add memory
          </button>
          <button className={secondaryButtonClass} onClick={onForget} type="button">
            Forget stale
          </button>
        </div>
      </form>
      <div className="space-y-2">
        {memories.length === 0 ? <EmptyState text="No memories." /> : null}
        {orderedMemories.map((memory) => (
          <article className="rounded-md border border-line bg-ink p-3 text-sm" key={memory.id}>
            <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
              <span className="rounded border border-line bg-panel px-2 py-1">
                {memory.memory_type}
              </span>
              {memory.pinned ? (
                <span className="rounded border border-moss bg-lime-950/40 px-2 py-1 text-lime-100">
                  pinned
                </span>
              ) : null}
              <span>{formatTimestamp(memory.created_at)}</span>
            </div>
            {editingMemoryId === memory.id ? (
              <textarea
                className={`${inputClass} min-h-20 resize-none`}
                value={memoryEditContent}
                onChange={(event) => setMemoryEditContent(event.target.value)}
              />
            ) : (
              <p>{memory.content}</p>
            )}
            <div className="mt-3 grid gap-2 text-xs text-zinc-500 sm:grid-cols-3">
              <MetricLine label="confidence" value={memory.confidence} />
              <MetricLine label="importance" value={memory.importance} />
              <MetricLine label="decay" value={memory.decay_score} />
            </div>
            {memory.last_recalled_at ? (
              <p className="mt-2 text-xs text-zinc-500">
                last recalled {formatTimestamp(memory.last_recalled_at)}
              </p>
            ) : null}
            {memory.contradiction_group ? (
              <p className="mt-2 rounded border border-ember bg-amber-950/40 px-2 py-1 text-xs text-amber-100">
                {memory.contradiction_group}
              </p>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-2">
              {editingMemoryId === memory.id ? (
                <button
                  className={primaryButtonClass}
                  onClick={() => void onSaveEdit(memory)}
                  type="button"
                >
                  Save
                </button>
              ) : (
                <button
                  className={secondaryButtonClass}
                  onClick={() => {
                    setEditingMemoryId(memory.id);
                    setMemoryEditContent(memory.content);
                  }}
                  type="button"
                >
                  Edit
                </button>
              )}
              <button
                className={secondaryButtonClass}
                onClick={() => void onTogglePinned(memory)}
                type="button"
              >
                {memory.pinned ? "Unpin" : "Pin"}
              </button>
              <button
                className={secondaryButtonClass}
                onClick={() => void onDelete(memory)}
                type="button"
              >
                Delete
              </button>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}

function MemoryStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-ink p-2">
      <p className="text-[11px] uppercase text-zinc-600">{label}</p>
      <p className="mt-1 font-mono text-sm text-zinc-200">{value}</p>
    </div>
  );
}

function MetricLine({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-line bg-panel px-2 py-1">
      <span>{label}</span> <span className="font-mono text-zinc-300">{formatMetric(value)}</span>
    </div>
  );
}
