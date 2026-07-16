"use client";

import type { FormEvent, KeyboardEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { characterOpeningGreeting } from "./controller-utils";
import { CompanionPortrait, Feedback, IconButton, PrimaryButton, QuietButton, fieldClass } from "./experience-primitives";
import { Icon } from "./icons";
import { LivingThreadsPopover } from "./living-threads";
import type {
  Character,
  ContinuityThread,
  ContentMode,
  ConversationPrivacyMode,
  ConversationScenarioMode,
  Message,
  StreamFailure,
  StreamPhase
} from "./types";

type MemoryCapturePolicy = {
  standardEnabled: boolean;
  adultEnabled: boolean;
};

export function ChatSurface({
  character,
  editableTitle,
  setEditableTitle,
  privacyMode,
  contentMode,
  scenarioMode,
  scenarioText,
  scenarioDraft,
  characterScenario,
  setScenarioDraft,
  memoryCapturePolicy,
  rememberedMessageIds,
  rememberingMessageId,
  messages,
  pendingOutgoingContent,
  streamingContent,
  streamPhase,
  failedTurn,
  providerName,
  draft,
  setDraft,
  privateTurn,
  setPrivateTurn,
  sending,
  busy,
  editingMessageId,
  error,
  notice,
  onSubmit,
  onRetryFailed,
  onStop,
  onSaveTitle,
  onSetPrivacyMode,
  onSaveScenario,
  onResetScenario,
  onQueueProactive,
  onCancelEdit,
  onEdit,
  onReroll,
  onRemember,
  onDelete,
  onOpenMemories,
  continuityThreads,
  threadDraft,
  threadActionId,
  setThreadDraft,
  onAddContinuityThread,
  onResolveContinuityThread,
  onReopenContinuityThread,
  onDeleteContinuityThread
}: {
  character: Character | null;
  editableTitle: string;
  setEditableTitle: (value: string) => void;
  privacyMode: ConversationPrivacyMode;
  contentMode: ContentMode;
  scenarioMode: ConversationScenarioMode;
  scenarioText: string;
  scenarioDraft: string;
  characterScenario: string;
  setScenarioDraft: (value: string) => void;
  memoryCapturePolicy: MemoryCapturePolicy;
  rememberedMessageIds: string[];
  rememberingMessageId: string | null;
  messages: Message[];
  pendingOutgoingContent: string | null;
  streamingContent: string;
  streamPhase: StreamPhase | null;
  failedTurn: StreamFailure | null;
  providerName: string | null;
  draft: string;
  setDraft: (value: string) => void;
  privateTurn: boolean;
  setPrivateTurn: (value: boolean) => void;
  sending: boolean;
  busy: boolean;
  editingMessageId: string | null;
  error: string | null;
  notice: string | null;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onRetryFailed: () => void;
  onStop: () => void;
  onSaveTitle: () => void;
  onSetPrivacyMode: (privacyMode: ConversationPrivacyMode) => void;
  onSaveScenario: () => void;
  onResetScenario: () => void;
  onQueueProactive: () => void;
  onCancelEdit: () => void;
  onEdit: (message: Message) => void;
  onReroll: (message: Message) => void;
  onRemember: (message: Message) => void;
  onDelete: (message: Message) => void;
  onOpenMemories: () => void;
  continuityThreads: ContinuityThread[];
  threadDraft: string;
  threadActionId: string | null;
  setThreadDraft: (value: string) => void;
  onAddContinuityThread: (event: FormEvent<HTMLFormElement>) => void;
  onResolveContinuityThread: (thread: ContinuityThread) => void;
  onReopenContinuityThread: (thread: ContinuityThread) => void;
  onDeleteContinuityThread: (thread: ContinuityThread) => void;
}) {
  const [toolsOpen, setToolsOpen] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);
  const [threadsOpen, setThreadsOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const rememberedIds = useMemo(() => new Set(rememberedMessageIds), [rememberedMessageIds]);
  const visibleMessages = useMemo(
    () => messages.filter((message) => message.role !== "system" || message.content.trim()),
    [messages]
  );
  const latestUserMessageId = useMemo(
    () => [...messages].reverse().find((message) => message.role === "user")?.id ?? null,
    [messages]
  );
  const name = character?.name ?? "Eidolon";
  const greeting = characterOpeningGreeting(character);
  const openThreadCount = continuityThreads.filter((thread) => thread.status === "open").length;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, streamingContent, streamPhase]);

  useEffect(() => {
    const textarea = composerRef.current;
    if (!textarea) {
      return;
    }
    textarea.style.height = "0px";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 168)}px`;
  }, [draft]);

  function submitOnEnter(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) {
      return;
    }
    event.preventDefault();
    if (!sending && !busy && draft.trim()) {
      event.currentTarget.form?.requestSubmit();
    }
  }

  function choosePrompt(prompt: string) {
    setDraft(prompt);
    window.requestAnimationFrame(() => composerRef.current?.focus());
  }

  return (
    <section className="relative flex h-full min-h-0 flex-col" aria-label={`Conversation with ${name}`}>
      <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-16 bg-gradient-to-b from-[#0b0a09] via-[#0b0a09]/70 to-transparent" />

      <div className="relative z-20 flex justify-center gap-2 px-4 pt-3">
        <button
          className="group flex max-w-[min(92vw,32rem)] items-center gap-2 rounded-full border border-white/[0.07] bg-[#13110f]/75 px-3 py-1.5 text-xs text-[#8d847a] shadow-lg shadow-black/10 backdrop-blur-xl transition hover:border-white/[0.13] hover:text-[#bdb2a7]"
          onClick={() => {
            setThreadsOpen(false);
            setContextOpen((current) => !current);
          }}
          type="button"
        >
          <Icon className="h-3.5 w-3.5 text-[#b98265]" name={privacyMode === "private" ? "lock" : "sparkles"} />
          <span className="truncate">
            {privacyMode === "private"
              ? "A private moment"
              : scenarioMode === "custom"
                ? scenarioText
                : characterScenario || "Your shared space"}
          </span>
          <Icon className={`h-3 w-3 transition ${contextOpen ? "rotate-180" : ""}`} name="chevron-down" />
        </button>
        <button
          aria-expanded={threadsOpen}
          className={`group flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-xs shadow-lg shadow-black/10 backdrop-blur-xl transition ${
            threadsOpen
              ? "border-[#b98265]/28 bg-[#b98265]/[0.09] text-[#c9a08a]"
              : "border-white/[0.07] bg-[#13110f]/75 text-[#8d847a] hover:border-white/[0.13] hover:text-[#bdb2a7]"
          }`}
          onClick={() => {
            setContextOpen(false);
            setThreadsOpen((current) => !current);
          }}
          type="button"
        >
          <Icon className="h-3.5 w-3.5 text-[#b98265]" name="moon" />
          <span>{openThreadCount > 0 ? `${openThreadCount} unfolding` : "Clear horizon"}</span>
        </button>
      </div>

      {contextOpen ? (
        <ConversationContext
          busy={busy}
          characterScenario={characterScenario}
          editableTitle={editableTitle}
          onClose={() => setContextOpen(false)}
          onResetScenario={onResetScenario}
          onSaveScenario={onSaveScenario}
          onSaveTitle={onSaveTitle}
          onSetPrivacyMode={onSetPrivacyMode}
          privacyMode={privacyMode}
          scenarioDraft={scenarioDraft}
          scenarioMode={scenarioMode}
          setEditableTitle={setEditableTitle}
          setScenarioDraft={setScenarioDraft}
        />
      ) : null}

      {threadsOpen ? (
        <LivingThreadsPopover
          actionId={threadActionId}
          draft={threadDraft}
          privacyMode={privacyMode}
          setDraft={setThreadDraft}
          threads={continuityThreads}
          onAdd={onAddContinuityThread}
          onClose={() => setThreadsOpen(false)}
          onDelete={onDeleteContinuityThread}
          onReopen={onReopenContinuityThread}
          onResolve={onResolveContinuityThread}
          onReturn={(thread) => {
            setDraft(`Can we come back to this: ${thread.content}`);
            setThreadsOpen(false);
            window.requestAnimationFrame(() => composerRef.current?.focus());
          }}
        />
      ) : null}

      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 pb-8 pt-6 sm:px-8 lg:px-12" role="log" aria-live="polite" aria-relevant="additions text">
        <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col justify-end">
          {visibleMessages.length === 0 && !streamPhase ? (
            <FirstConversation
              characterName={name}
              greeting={greeting}
              theme={characterTheme(character)}
              onChoosePrompt={choosePrompt}
            />
          ) : (
            <div className="space-y-7 py-8 sm:space-y-9">
              {visibleMessages.map((message, index) => (
                <MessageTurn
                  canRemember={canRememberMessage(message, memoryCapturePolicy, privacyMode)}
                  editing={editingMessageId === message.id}
                  isLatestUser={message.id === latestUserMessageId}
                  key={message.id}
                  message={message}
                  remembered={rememberedIds.has(message.id)}
                  remembering={rememberingMessageId === message.id}
                  showDate={shouldShowDate(visibleMessages[index - 1], message)}
                  onCancelEdit={onCancelEdit}
                  onDelete={onDelete}
                  onEdit={onEdit}
                  onRemember={onRemember}
                  onReroll={onReroll}
                />
              ))}

              {pendingOutgoingContent ? (
                <PendingUserTurn content={pendingOutgoingContent} />
              ) : null}

              {streamPhase ? (
                <StreamingTurn
                  characterName={name}
                  content={streamingContent}
                  phase={streamPhase}
                />
              ) : null}

              {failedTurn && !streamPhase ? (
                <FailedTurn failure={failedTurn} onRetry={onRetryFailed} />
              ) : null}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="safe-area-composer relative z-30 bg-gradient-to-t from-[#090908] via-[#090908] to-transparent px-3 pt-3 sm:px-6 sm:pt-5">
        <div className="mx-auto w-full max-w-3xl">
          <Feedback error={error} notice={notice} />

          {privateTurn || privacyMode === "private" ? (
            <div className="mb-2 flex items-center justify-center gap-2 text-[0.68rem] text-[#92867c]">
              <Icon className="h-3.5 w-3.5" name="lock" />
              <span>
                {privacyMode === "private"
                  ? "This conversation stays outside shared memory"
                  : "This reply won’t shape memory or your bond"}
              </span>
            </div>
          ) : null}

          <form className="relative rounded-[1.6rem] border border-white/[0.13] bg-[#171512]/95 p-2 shadow-[0_18px_60px_rgba(0,0,0,0.4),inset_0_1px_rgba(255,255,255,0.025)] backdrop-blur-2xl transition focus-within:border-[#b98265]/35" onSubmit={onSubmit}>
            <textarea
              aria-label={editingMessageId ? "Revise your message" : `Message ${name}`}
              className="block max-h-40 min-h-[3rem] w-full resize-none overflow-y-auto bg-transparent px-3 pb-1 pt-2 text-[0.95rem] leading-6 text-[#eee7de] outline-none placeholder:text-[#686159] sm:px-4"
              disabled={sending || busy}
              maxLength={6000}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={submitOnEnter}
              placeholder={editingMessageId ? "Change what you said…" : `Say something to ${name}…`}
              ref={composerRef}
              rows={1}
              value={draft}
            />

            <div className="mt-1 flex items-center justify-between gap-2 px-1 pb-1">
              <div className="relative flex items-center gap-1">
                <IconButton
                  aria-expanded={toolsOpen}
                  className="h-9 w-9 border-transparent bg-transparent"
                  icon="plus"
                  label="Conversation actions"
                  onClick={() => setToolsOpen((current) => !current)}
                />
                {contentMode === "adult" ? (
                  <span className="ml-1 rounded-full border border-[#b98265]/20 bg-[#b98265]/[0.06] px-2 py-1 text-[0.65rem] text-[#b9937f]">consent mode</span>
                ) : null}

                {toolsOpen ? (
                  <div className="glass-surface absolute bottom-12 left-0 z-50 w-64 rounded-2xl p-2 shadow-veil">
                    <ComposerAction
                      detail="Keep this single exchange outside memory"
                      icon="lock"
                      label={privateTurn ? "Return to shared memory" : "Make this turn private"}
                      onClick={() => {
                        setPrivateTurn(!privateTurn);
                        setToolsOpen(false);
                      }}
                    />
                    <ComposerAction
                      detail="Visit the things held onto over time"
                      icon="bookmark"
                      label="Open your memories"
                      onClick={() => {
                        onOpenMemories();
                        setToolsOpen(false);
                      }}
                    />
                    <ComposerAction
                      detail={`Invite ${name} to leave a thoughtful note later`}
                      icon="moon"
                      label="A note for later"
                      onClick={() => {
                        onQueueProactive();
                        setToolsOpen(false);
                      }}
                    />
                  </div>
                ) : null}
              </div>

              <div className="flex items-center gap-2">
                {editingMessageId ? (
                  <button className="px-2 text-xs text-[#9f958b] hover:text-[#e8ded4]" onClick={onCancelEdit} type="button">Cancel edit</button>
                ) : null}
                <button
                  aria-label={sending ? "Stop response" : editingMessageId ? "Save revised message" : "Send message"}
                  className={`grid h-10 w-10 place-items-center rounded-full transition disabled:cursor-not-allowed disabled:bg-[#3c3732] disabled:text-[#777069] ${sending ? "bg-[#8f5d47] text-[#f5e6dc] hover:bg-[#a86c52]" : "bg-[#e7dbcf] text-[#281b16] hover:bg-[#f5ede5]"}`}
                  disabled={!sending && (busy || !draft.trim())}
                  onClick={sending ? onStop : undefined}
                  type={sending ? "button" : "submit"}
                >
                  <Icon className="h-4 w-4" name={sending ? "stop" : "arrow-up"} />
                </button>
              </div>
            </div>
          </form>
          <p className="mt-2 text-center text-[0.62rem] text-[#5f5a54]">
            Messages use {providerDisclosure(providerName)} · Enter to send · Shift + Enter for a new line
          </p>
        </div>
      </div>
    </section>
  );
}

function FirstConversation({
  characterName,
  greeting,
  theme,
  onChoosePrompt
}: {
  characterName: string;
  greeting: string;
  theme: string;
  onChoosePrompt: (prompt: string) => void;
}) {
  const prompts = [
    "Tell me how you want us to begin.",
    "I want somewhere quiet to land tonight.",
    "Ask me something you’ll remember."
  ];
  return (
    <div className="flex min-h-[34rem] flex-col items-center justify-center py-12 text-center reveal-up">
      <CompanionPortrait name={characterName} size="large" theme={theme} />
      <p className="mt-8 text-xs uppercase tracking-[0.2em] text-[#887d73]">Your first moment</p>
      <h2 className="mt-4 max-w-xl font-eidolon-display text-3xl leading-[1.2] text-[#eee5da] sm:text-4xl">
        “{greeting}”
      </h2>
      <p className="mt-5 max-w-md text-sm leading-6 text-[#8f867d]">
        There is no history to perform here. Start with what feels true, and let the rest grow slowly.
      </p>
      <div className="mt-8 flex max-w-2xl flex-wrap justify-center gap-2">
        {prompts.map((prompt) => (
          <button
            className="rounded-full border border-white/[0.09] bg-white/[0.025] px-4 py-2 text-xs text-[#aaa096] transition hover:border-[#b98265]/30 hover:bg-[#b98265]/[0.06] hover:text-[#d9c9bc]"
            key={prompt}
            onClick={() => onChoosePrompt(prompt)}
            type="button"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}

function MessageTurn({
  message,
  showDate,
  isLatestUser,
  editing,
  remembered,
  remembering,
  canRemember,
  onCancelEdit,
  onEdit,
  onReroll,
  onRemember,
  onDelete
}: {
  message: Message;
  showDate: boolean;
  isLatestUser: boolean;
  editing: boolean;
  remembered: boolean;
  remembering: boolean;
  canRemember: boolean;
  onCancelEdit: () => void;
  onEdit: (message: Message) => void;
  onReroll: (message: Message) => void;
  onRemember: (message: Message) => void;
  onDelete: (message: Message) => void;
}) {
  if (message.role === "system") {
    return (
      <div className="message-enter flex items-center justify-center gap-3 py-2 text-center text-[0.68rem] text-[#706961]">
        <span className="h-px w-8 bg-white/[0.08]" />
        <span>{humanSystemEvent(message)}</span>
        <span className="h-px w-8 bg-white/[0.08]" />
      </div>
    );
  }
  const fromUser = message.role === "user";
  const proactive = message.metadata_json.proactive === true;
  return (
    <article
      className={`message-enter group outline-none ${fromUser ? "ml-auto max-w-[88%] sm:max-w-[78%]" : "mr-auto w-full max-w-[92%] sm:max-w-[88%]"}`}
      id={`message-${message.id}`}
      tabIndex={-1}
    >
      {showDate ? (
        <p className="mb-8 text-center text-[0.65rem] uppercase tracking-[0.16em] text-[#625d57]">{formatDay(message.created_at)}</p>
      ) : null}
      {proactive ? (
        <p className="mb-2 flex items-center gap-2 text-[0.67rem] uppercase tracking-[0.14em] text-[#9b7968]"><Icon className="h-3.5 w-3.5" name="moon" /> A note that found you</p>
      ) : null}
      <div className={fromUser ? "rounded-[1.35rem] rounded-br-md bg-[#28231f] px-4 py-3 text-[#e7ded4] shadow-sm shadow-black/20 sm:px-5" : "pr-2 text-[#e4dbd1]"}>
        <p className={`whitespace-pre-wrap text-[0.96rem] leading-7 ${fromUser ? "" : "font-eidolon-display text-[1.12rem] leading-8 sm:text-[1.18rem]"}`}>{message.content}</p>
      </div>
      <div className={`mt-2 flex min-h-7 items-center gap-1 text-[#716a63] transition sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100 ${fromUser ? "justify-end" : "justify-start"}`}>
        <span className="mr-1 text-[0.62rem]">{formatTime(message.created_at)}{fromUser && isLatestUser ? " · Seen" : ""}</span>
        {fromUser && isLatestUser ? (
          <MiniAction icon="edit" label={editing ? "Cancel revision" : "Revise message"} onClick={() => editing ? onCancelEdit() : onEdit(message)} />
        ) : null}
        {!fromUser ? <MiniAction icon="sparkles" label="Ask for another response" onClick={() => onReroll(message)} /> : null}
        {canRemember ? (
          <MiniAction
            active={remembered}
            disabled={remembered || remembering}
            icon="bookmark"
            label={remembered ? "Held in memory" : remembering ? "Holding this memory" : "Remember this"}
            onClick={() => onRemember(message)}
          />
        ) : null}
        <MiniAction icon="trash" label="Remove this message" onClick={() => onDelete(message)} />
      </div>
      {remembered ? (
        <p className={`mt-1 flex items-center gap-1.5 text-[0.65rem] text-[#9e7c69] ${fromUser ? "justify-end" : ""}`}><Icon className="h-3 w-3" name="bookmark" /> Held close</p>
      ) : null}
    </article>
  );
}

function StreamingTurn({ characterName, content, phase }: { characterName: string; content: string; phase: StreamPhase }) {
  const waiting = !content.trim();
  return (
    <article className="message-enter mr-auto w-full max-w-[92%] pr-2" aria-label={`${characterName} is responding`}>
      {waiting ? (
        <div className="flex items-center gap-3 text-sm text-[#8c8278]">
          <span>{phase === "connecting" ? `${characterName} is here` : `${characterName} is thinking`}</span>
          <TypingMark />
        </div>
      ) : (
        <p className="whitespace-pre-wrap font-eidolon-display text-[1.12rem] leading-8 text-[#e4dbd1] sm:text-[1.18rem]">{content}<span aria-hidden="true" className="ml-1 inline-block h-4 w-px animate-pulse bg-[#b98265]" /></p>
      )}
    </article>
  );
}

function PendingUserTurn({ content }: { content: string }) {
  return (
    <article
      aria-label="Your message is being accepted"
      className="message-enter ml-auto w-full max-w-[88%] pl-5 text-right opacity-75"
    >
      <p className="whitespace-pre-wrap text-[0.96rem] leading-7 text-[#d6cec6]">
        {content}
      </p>
      <p className="mt-1 text-[0.62rem] uppercase tracking-[0.12em] text-[#6f6760]">
        Sending
      </p>
    </article>
  );
}

function FailedTurn({
  failure,
  onRetry
}: {
  failure: StreamFailure;
  onRetry: () => void;
}) {
  return (
    <div className="message-enter mr-auto w-full max-w-[92%] rounded-2xl border border-[#b98265]/20 bg-[#b98265]/[0.055] px-4 py-3 text-sm text-[#b9aaa0]">
      <p>{failure.detail}</p>
      <div className="mt-3 flex items-center gap-3">
        {failure.retryable ? (
          <button
            className="rounded-full border border-[#b98265]/30 px-3 py-1.5 text-xs text-[#d9b7a5] transition hover:bg-[#b98265]/10"
            onClick={onRetry}
            type="button"
          >
            Retry response
          </button>
        ) : null}
        <span className="text-[0.68rem] text-[#766c65]">
          Your message is still saved.
        </span>
      </div>
    </div>
  );
}

function TypingMark() {
  return (
    <span className="flex items-center gap-1" aria-hidden="true">
      <span className="typing-dot h-1 w-1 rounded-full bg-current" />
      <span className="typing-dot h-1 w-1 rounded-full bg-current" />
      <span className="typing-dot h-1 w-1 rounded-full bg-current" />
    </span>
  );
}

function providerDisclosure(providerName: string | null): string {
  if (providerName === "groq") {
    return "GroqCloud for model inference";
  }
  if (providerName === "ollama") {
    return "your local Ollama model";
  }
  if (providerName === "mock") {
    return "the development mock provider";
  }
  return "the configured text provider";
}

function MiniAction({ icon, label, active = false, disabled = false, onClick }: { icon: "bookmark" | "edit" | "sparkles" | "trash"; label: string; active?: boolean; disabled?: boolean; onClick: () => void }) {
  return (
    <button
      aria-label={label}
      className={`grid h-7 w-7 place-items-center rounded-full transition hover:bg-white/[0.06] hover:text-[#d2c5b8] disabled:cursor-default ${active ? "text-[#b98265]" : ""}`}
      disabled={disabled}
      onClick={onClick}
      title={label}
      type="button"
    ><Icon className="h-3.5 w-3.5" name={icon} /></button>
  );
}

function ComposerAction({ icon, label, detail, onClick }: { icon: "bookmark" | "lock" | "moon"; label: string; detail: string; onClick: () => void }) {
  return (
    <button className="flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left transition hover:bg-white/[0.055]" onClick={onClick} type="button">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-[#b98265]" name={icon} />
      <span><span className="block text-sm text-[#d9cfc4]">{label}</span><span className="mt-0.5 block text-[0.68rem] leading-4 text-[#776f67]">{detail}</span></span>
    </button>
  );
}

function ConversationContext({
  editableTitle,
  setEditableTitle,
  scenarioMode,
  scenarioDraft,
  setScenarioDraft,
  characterScenario,
  privacyMode,
  busy,
  onSaveTitle,
  onSaveScenario,
  onResetScenario,
  onSetPrivacyMode,
  onClose
}: {
  editableTitle: string;
  setEditableTitle: (value: string) => void;
  scenarioMode: ConversationScenarioMode;
  scenarioDraft: string;
  setScenarioDraft: (value: string) => void;
  characterScenario: string;
  privacyMode: ConversationPrivacyMode;
  busy: boolean;
  onSaveTitle: () => void;
  onSaveScenario: () => void;
  onResetScenario: () => void;
  onSetPrivacyMode: (privacyMode: ConversationPrivacyMode) => void;
  onClose: () => void;
}) {
  return (
    <div className="absolute inset-x-3 top-14 z-50 mx-auto max-w-xl rounded-3xl glass-surface p-5 shadow-veil sm:inset-x-8 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div><p className="text-xs uppercase tracking-[0.18em] text-[#8c8076]">This conversation</p><h2 className="mt-2 font-eidolon-display text-2xl">Set the feeling of the room</h2></div>
        <IconButton className="h-9 w-9" icon="close" label="Close conversation options" onClick={onClose} />
      </div>
      <div className="mt-6 space-y-5">
        <label className="block text-sm text-[#cfc4b8]">A name for this chapter
          <div className="mt-2 flex gap-2"><input className={fieldClass} maxLength={200} onChange={(event) => setEditableTitle(event.target.value)} value={editableTitle} /><QuietButton disabled={busy} onClick={onSaveTitle}>Save</QuietButton></div>
        </label>
        <label className="block text-sm text-[#cfc4b8]">Shared setting
          <textarea className={`${fieldClass} mt-2 min-h-24 resize-none`} maxLength={1200} onChange={(event) => setScenarioDraft(event.target.value)} placeholder={characterScenario || "A quiet place, a particular hour, the feeling between you…"} value={scenarioDraft} />
        </label>
        <div className="flex flex-wrap gap-2">
          <PrimaryButton disabled={busy || !scenarioDraft.trim()} onClick={onSaveScenario}>Set this scene</PrimaryButton>
          {scenarioMode === "custom" ? <QuietButton disabled={busy} onClick={onResetScenario}>Return to your usual place</QuietButton> : null}
        </div>
        <div className="border-t border-white/[0.08] pt-4">
          <button className="flex w-full items-center justify-between gap-4 text-left" disabled={busy} onClick={() => onSetPrivacyMode(privacyMode === "private" ? "normal" : "private")} type="button">
            <span><span className="block text-sm text-[#d9cfc4]">Keep this conversation separate</span><span className="mt-1 block text-xs leading-5 text-[#7e766e]">Messages remain in your history, but won’t shape memory, moments, or the relationship.</span></span>
            <span className={`relative h-6 w-11 shrink-0 rounded-full border transition ${privacyMode === "private" ? "border-[#b98265]/60 bg-[#8f5d47]" : "border-white/[0.12] bg-white/[0.07]"}`}><span className={`absolute left-1 top-1 h-4 w-4 rounded-full transition ${privacyMode === "private" ? "translate-x-5 bg-[#f4e6dc]" : "bg-[#a49a8f]"}`} /></span>
          </button>
        </div>
      </div>
    </div>
  );
}

function canRememberMessage(message: Message, policy: MemoryCapturePolicy, privacyMode: ConversationPrivacyMode): boolean {
  if (privacyMode === "private" || message.metadata_json.privacy_mode === "private") {
    return false;
  }
  return message.metadata_json.content_mode === "adult" ? policy.adultEnabled : policy.standardEnabled;
}

function shouldShowDate(previous: Message | undefined, current: Message): boolean {
  if (!previous) {
    return true;
  }
  return new Date(previous.created_at).toDateString() !== new Date(current.created_at).toDateString();
}

function formatDay(value: string): string {
  const date = new Date(value);
  const today = new Date();
  if (date.toDateString() === today.toDateString()) {
    return "Today";
  }
  return new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric" }).format(date);
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

function humanSystemEvent(message: Message): string {
  const type = message.metadata_json.event_type;
  if (type === "privacy_changed") {
    return message.content.toLowerCase().includes("private") ? "This moment became private" : "Shared memory returned";
  }
  if (type === "scenario_changed") {
    return "The feeling of the room shifted";
  }
  return message.metadata_json.event_label || message.content;
}

function characterTheme(character: Character | null): string {
  const value = character?.boundaries_json.visual_theme;
  return typeof value === "string" ? value : "";
}
