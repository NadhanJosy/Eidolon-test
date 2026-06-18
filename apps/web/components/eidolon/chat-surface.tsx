import type { FormEvent } from "react";
import { useEffect, useRef } from "react";

import type { AdultStatus, ContentMode, Message, Relationship } from "./types";
import {
  EmptyState,
  errorClass,
  formatMetric,
  formatTimestamp,
  noticeClass,
  quietButtonClass,
  secondaryButtonClass
} from "./ui";

export function ChatSurface({
  title,
  editableTitle,
  setEditableTitle,
  messageCount,
  memoryCount,
  journalCount,
  relationship,
  adultStatus,
  contentMode,
  messages,
  streamingContent,
  draft,
  setDraft,
  sending,
  busy,
  editingMessageId,
  error,
  notice,
  onSubmit,
  onSaveTitle,
  onQueueProactive,
  onCancelEdit,
  onEdit,
  onReroll
}: {
  title: string;
  editableTitle: string;
  setEditableTitle: (value: string) => void;
  messageCount: number;
  memoryCount: number;
  journalCount: number;
  relationship: Relationship;
  adultStatus: AdultStatus | null;
  contentMode: ContentMode;
  messages: Message[];
  streamingContent: string;
  draft: string;
  setDraft: (value: string) => void;
  sending: boolean;
  busy: boolean;
  editingMessageId: string | null;
  error: string | null;
  notice: string | null;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onSaveTitle: () => void;
  onQueueProactive: () => void;
  onCancelEdit: () => void;
  onEdit: (message: Message) => void;
  onReroll: (message: Message) => void;
}) {
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const gateLabel = adultStatus
    ? `${adultStatus.effective_mode}${adultStatus.allowed ? "" : " blocked"}`
    : contentMode;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, streamingContent]);

  return (
    <section className="flex min-h-[calc(100vh-112px)] flex-col rounded-lg border border-line bg-panel shadow-2xl shadow-black/30">
      <div className="border-b border-line px-4 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <input
                className="w-full min-w-0 rounded-md border border-line bg-ink px-2 py-1 text-sm font-medium text-paper sm:w-64"
                value={editableTitle}
                onChange={(event) => setEditableTitle(event.target.value)}
                aria-label="Thread title"
              />
              <button className={secondaryButtonClass} onClick={onSaveTitle} type="button">
                Save
              </button>
            </div>
            <p className="mt-1 truncate text-xs text-zinc-500">{title}</p>
          </div>
          <button
            className={secondaryButtonClass}
            onClick={onQueueProactive}
            type="button"
            disabled={busy || sending}
          >
            Queue check-in
          </button>
        </div>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <ContextTile label="Mood" value={relationship.mood} detail={relationship.conflict_state} />
          <ContextTile
            label="Warmth"
            value={formatMetric(relationship.warmth)}
            detail={`trust ${formatMetric(relationship.trust)}`}
          />
          <ContextTile
            label="Continuity"
            value={`${memoryCount} memories`}
            detail={`${journalCount} journals · ${messageCount} messages`}
          />
          <ContextTile
            label="Mode"
            value={gateLabel}
            detail={relationship.repair_needed ? "repair needed" : "clear"}
          />
        </div>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4" aria-live="polite">
        {messages.length === 0 && !streamingContent ? <EmptyState text="No messages yet." /> : null}
        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            onEdit={onEdit}
            onReroll={onReroll}
          />
        ))}
        {streamingContent ? (
          <div className="max-w-[86%] rounded-md border border-line bg-ink px-3 py-2 shadow-lg shadow-black/10">
            <p className="whitespace-pre-wrap text-sm leading-6">{streamingContent}</p>
            <p className="mt-2 text-xs text-zinc-500">composing</p>
          </div>
        ) : null}
        <div ref={bottomRef} />
      </div>

      <form className="border-t border-line p-3" onSubmit={onSubmit}>
        {error ? <p className={`mb-2 ${errorClass}`}>{error}</p> : null}
        {notice ? <p className={`mb-2 ${noticeClass}`}>{notice}</p> : null}
        <div className="flex flex-col gap-2 sm:flex-row">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            className="min-h-20 flex-1 resize-none rounded-md border border-line bg-ink px-3 py-2 text-sm shadow-inner shadow-black/20 sm:min-h-12"
            placeholder={editingMessageId ? "Edit message" : "Write a message"}
            disabled={sending}
          />
          <div className="flex gap-2 sm:w-24 sm:flex-col">
            <button
              className="min-h-10 flex-1 rounded-md bg-paper px-3 py-2 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50 sm:flex-none"
              disabled={sending || !draft.trim()}
              type="submit"
            >
              {sending ? "..." : editingMessageId ? "Save" : "Send"}
            </button>
            {editingMessageId ? (
              <button className={secondaryButtonClass} onClick={onCancelEdit} type="button">
                Cancel
              </button>
            ) : null}
          </div>
        </div>
      </form>
    </section>
  );
}

function ContextTile({
  label,
  value,
  detail
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="min-h-16 rounded-md border border-line bg-ink/80 px-3 py-2">
      <p className="text-[11px] uppercase text-zinc-600">{label}</p>
      <p className="mt-1 truncate text-sm font-medium text-paper">{value}</p>
      <p className="truncate text-xs text-zinc-500">{detail}</p>
    </div>
  );
}

function MessageBubble({
  message,
  onEdit,
  onReroll
}: {
  message: Message;
  onEdit: (message: Message) => void;
  onReroll: (message: Message) => void;
}) {
  const isUser = message.role === "user";
  const delivery = message.metadata_json.delivery_state;
  const assistantMode = message.metadata_json.content_mode;
  return (
    <article className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[86%] rounded-md border px-3 py-2 shadow-lg shadow-black/10 ${
          isUser ? "border-tide bg-cyan-950/80" : "border-line bg-ink"
        }`}
      >
        <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
          <span>
            {message.role} · {formatTimestamp(message.created_at)}
          </span>
          {message.metadata_json.edited ? <span>edited</span> : null}
          {message.metadata_json.proactive ? (
            <span>{message.metadata_json.proactive_label ?? "proactive"}</span>
          ) : null}
          {assistantMode ? <span>{assistantMode}</span> : null}
          {delivery?.read_state ? <span>{delivery.read_state}</span> : null}
          {delivery?.typing_ms ? <span>{Math.round(delivery.typing_ms)}ms</span> : null}
          {delivery?.away_state ? <span>{delivery.away_state}</span> : null}
          {isUser ? (
            <button className={quietButtonClass} onClick={() => onEdit(message)} type="button">
              Edit
            </button>
          ) : (
            <button
              className={quietButtonClass}
              onClick={() => void onReroll(message)}
              type="button"
            >
              Reroll
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
