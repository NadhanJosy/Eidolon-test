"use client";

import type { FormEvent } from "react";
import { useMemo, useState } from "react";

import { IconButton, PrimaryButton, QuietButton } from "./experience-primitives";
import { Icon } from "./icons";
import type { ContinuityThread, ConversationPrivacyMode } from "./types";

type ThreadActions = {
  actionId: string | null;
  onDelete: (thread: ContinuityThread) => void;
  onReopen: (thread: ContinuityThread) => void;
  onResolve: (thread: ContinuityThread) => void;
};

export function LivingThreadsPopover({
  threads,
  privacyMode,
  draft,
  setDraft,
  onAdd,
  onReturn,
  onClose,
  ...actions
}: ThreadActions & {
  threads: ContinuityThread[];
  privacyMode: ConversationPrivacyMode;
  draft: string;
  setDraft: (value: string) => void;
  onAdd: (event: FormEvent<HTMLFormElement>) => void;
  onReturn: (thread: ContinuityThread) => void;
  onClose: () => void;
}) {
  const [view, setView] = useState<"open" | "resolved">("open");
  const [writing, setWriting] = useState(false);
  const ordered = useMemo(
    () =>
      [...threads]
        .filter((thread) => thread.status === view)
        .sort(threadOrder)
        .slice(0, 12),
    [threads, view]
  );
  const openCount = threads.filter((thread) => thread.status === "open").length;
  const resolvedCount = threads.filter((thread) => thread.status === "resolved").length;

  return (
    <aside
      aria-label="Living threads"
      className="glass-surface absolute left-1/2 top-14 z-40 flex max-h-[min(36rem,calc(100dvh-11rem))] w-[min(94vw,38rem)] -translate-x-1/2 flex-col overflow-hidden rounded-[1.75rem] shadow-[0_28px_100px_rgba(0,0,0,0.65)] reveal-up"
    >
      <div className="flex items-start justify-between gap-5 border-b border-white/[0.07] p-5 sm:p-6">
        <div>
          <p className="text-[0.64rem] uppercase tracking-[0.19em] text-[#9a7866]">
            Continuity between conversations
          </p>
          <h2 className="mt-2 font-eidolon-display text-2xl text-[#e7ddd3]">
            What is still unfolding
          </h2>
          <p className="mt-2 max-w-lg text-xs leading-5 text-[#837a72]">
            Explicit promises, plans, rituals, and things you asked to return to. They stay
            grounded in your words and leave future replies when you close them.
          </p>
        </div>
        <IconButton icon="close" label="Close living threads" onClick={onClose} />
      </div>

      <div className="flex items-center justify-between gap-3 border-b border-white/[0.06] px-5 py-3 sm:px-6">
        <div className="flex rounded-full border border-white/[0.08] bg-black/20 p-1">
          <ThreadTab
            active={view === "open"}
            count={openCount}
            label="Unfolding"
            onClick={() => setView("open")}
          />
          <ThreadTab
            active={view === "resolved"}
            count={resolvedCount}
            label="Settled"
            onClick={() => setView("resolved")}
          />
        </div>
        {view === "open" && privacyMode === "normal" ? (
          <button
            className="text-xs text-[#a6816d] transition hover:text-[#d1a58e]"
            onClick={() => setWriting((current) => !current)}
            type="button"
          >
            {writing ? "Cancel" : "Keep something in view"}
          </button>
        ) : null}
      </div>

      <div className="min-h-0 overflow-y-auto overscroll-contain p-4 sm:p-5">
        {writing && view === "open" ? (
          <form
            className="mb-4 rounded-2xl border border-[#b98265]/20 bg-[#b98265]/[0.055] p-4"
            onSubmit={onAdd}
          >
            <label className="text-[0.65rem] uppercase tracking-[0.15em] text-[#9b7967]" htmlFor="living-thread-draft">
              Something to return to
            </label>
            <textarea
              className="mt-3 min-h-20 w-full resize-none bg-transparent text-sm leading-6 text-[#ddd3ca] outline-none placeholder:text-[#655e58]"
              id="living-thread-draft"
              maxLength={600}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="A plan, promise, question, or small ritual…"
              value={draft}
            />
            <div className="mt-3 flex justify-end">
              <PrimaryButton disabled={!draft.trim() || actions.actionId !== null} type="submit">
                Keep this thread
              </PrimaryButton>
            </div>
          </form>
        ) : null}

        {privacyMode === "private" && view === "open" ? (
          <div className="mb-4 flex items-start gap-3 rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4 text-xs leading-5 text-[#817870]">
            <Icon className="mt-0.5 h-4 w-4 shrink-0 text-[#9b8273]" name="lock" />
            New threads stay off in this private conversation. Existing shared threads remain
            visible, but this conversation cannot change them.
          </div>
        ) : null}

        {ordered.length === 0 ? (
          <div className="grid min-h-44 place-items-center px-6 text-center">
            <div>
              <Icon className="mx-auto h-5 w-5 text-[#836b5f]" name={view === "open" ? "moon" : "sparkles"} />
              <p className="mt-4 font-eidolon-display text-xl text-[#cfc3b8]">
                {view === "open" ? "Nothing is asking to be carried" : "No loops have closed yet"}
              </p>
              <p className="mt-2 text-xs leading-5 text-[#716a63]">
                {view === "open"
                  ? "Eidolon will notice only explicit plans, promises, rituals, and requests to return."
                  : "Resolved threads remain here as quiet proof that the story moved forward."}
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {ordered.map((thread) => (
              <ThreadCard
                {...actions}
                key={thread.id}
                onReturn={onReturn}
                thread={thread}
              />
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}

export function LivingThreadsStory({
  characterName,
  threads,
  onReturn,
  ...actions
}: ThreadActions & {
  characterName: string;
  threads: ContinuityThread[];
  onReturn: (thread: ContinuityThread) => void;
}) {
  const open = threads.filter((thread) => thread.status === "open").sort(threadOrder);
  const settled = threads
    .filter((thread) => thread.status === "resolved")
    .sort(threadOrder)
    .slice(0, 4);

  return (
    <section className="mt-14 border-t border-white/[0.08] pt-10">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-[#857a70]">Living threads</p>
          <h2 className="mt-3 font-eidolon-display text-3xl">The things between then and next</h2>
        </div>
        <p className="max-w-md text-xs leading-5 text-[#716a63]">
          What you explicitly asked {characterName} to remember to return to—never inferred as
          completed, and never held after you release it.
        </p>
      </div>

      {open.length === 0 ? (
        <div className="mt-6 rounded-[1.75rem] border border-dashed border-white/[0.1] px-6 py-9 text-center">
          <p className="font-eidolon-display text-xl text-[#bfb3a8]">The horizon is clear</p>
          <p className="mt-2 text-xs text-[#716a63]">
            No plans, promises, or conversations are waiting to be returned to.
          </p>
        </div>
      ) : (
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {open.slice(0, 6).map((thread) => (
            <ThreadCard {...actions} key={thread.id} onReturn={onReturn} thread={thread} />
          ))}
        </div>
      )}

      {settled.length > 0 ? (
        <details className="group mt-6 rounded-2xl border border-white/[0.07] bg-white/[0.02] p-5">
          <summary className="flex cursor-pointer list-none items-center justify-between text-xs text-[#8b8178]">
            Recently settled
            <span className="flex items-center gap-2 text-[#6f6760]">
              {settled.length}
              <Icon className="h-4 w-4 transition group-open:rotate-180" name="chevron-down" />
            </span>
          </summary>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {settled.map((thread) => (
              <ThreadCard {...actions} key={thread.id} onReturn={onReturn} thread={thread} />
            ))}
          </div>
        </details>
      ) : null}
    </section>
  );
}

function ThreadCard({
  thread,
  actionId,
  onDelete,
  onReopen,
  onResolve,
  onReturn
}: ThreadActions & {
  thread: ContinuityThread;
  onReturn: (thread: ContinuityThread) => void;
}) {
  const busy = actionId !== null;
  const open = thread.status === "open";
  return (
    <article
      className={`rounded-2xl border p-4 transition sm:p-5 ${
        open
          ? "border-[#b98265]/16 bg-[linear-gradient(145deg,rgba(185,130,101,0.07),rgba(255,255,255,0.018))]"
          : "border-white/[0.07] bg-white/[0.018] opacity-75"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <p className="flex items-center gap-2 text-[0.64rem] uppercase tracking-[0.15em] text-[#9a7968]">
          <Icon className="h-3.5 w-3.5" name={threadIcon(thread)} />
          {threadKindLabel(thread)}
        </p>
        <span className="text-[0.62rem] text-[#68615b]">{threadAge(thread)}</span>
      </div>
      <p className="mt-4 text-sm leading-6 text-[#c5bbb1]">“{thread.content}”</p>
      {thread.last_proactive_at ? (
        <p className="mt-3 flex items-center gap-1.5 text-[0.62rem] text-[#745f54]">
          <Icon className="h-3 w-3" name="moon" /> A restrained follow-up was sent before
        </p>
      ) : null}
      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-white/[0.06] pt-3">
        {open ? (
          <>
            <QuietButton disabled={busy} onClick={() => onReturn(thread)}>
              Return to this
            </QuietButton>
            <QuietButton disabled={busy} onClick={() => onResolve(thread)}>
              Close the loop
            </QuietButton>
          </>
        ) : (
          <QuietButton disabled={busy} onClick={() => onReopen(thread)}>
            Reopen
          </QuietButton>
        )}
        <IconButton
          className="ml-auto h-9 w-9 border-transparent"
          disabled={busy}
          icon="trash"
          label="Release this thread permanently"
          onClick={() => onDelete(thread)}
        />
      </div>
    </article>
  );
}

function ThreadTab({
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
      className={`rounded-full px-3 py-1.5 text-[0.67rem] transition ${
        active ? "bg-white/[0.09] text-[#dfd4ca]" : "text-[#746d66] hover:text-[#9e958c]"
      }`}
      onClick={onClick}
      type="button"
    >
      {label} <span className="ml-1 text-[#8e7365]">{count}</span>
    </button>
  );
}

function threadOrder(left: ContinuityThread, right: ContinuityThread): number {
  return right.salience - left.salience || Date.parse(right.updated_at) - Date.parse(left.updated_at);
}

function threadKindLabel(thread: ContinuityThread): string {
  const labels: Record<ContinuityThread["thread_kind"], string> = {
    follow_up: "Worth returning to",
    plan: "A plan in motion",
    promise: "A promise between you",
    repair: "A repair still unfolding",
    ritual: "A ritual taking shape"
  };
  return labels[thread.thread_kind];
}

function threadIcon(thread: ContinuityThread): "clock" | "heart" | "moon" | "sparkles" {
  if (thread.thread_kind === "repair") return "heart";
  if (thread.thread_kind === "ritual") return "sparkles";
  if (thread.thread_kind === "plan") return "clock";
  return "moon";
}

function threadAge(thread: ContinuityThread): string {
  const timestamp = thread.resolved_at ?? thread.updated_at;
  const days = Math.max(0, Math.floor((Date.now() - Date.parse(timestamp)) / 86_400_000));
  if (thread.status === "resolved") {
    return days === 0 ? "settled today" : `settled ${days}d ago`;
  }
  if (days === 0) return "held today";
  if (days === 1) return "held yesterday";
  return `held ${days}d`;
}
