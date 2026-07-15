import { useState } from "react";

import { primaryButtonClass, secondaryButtonClass } from "../ui";

const CLEAR_CHAT_CONFIRMATION = "CLEAR CHAT";
const CLEAR_MEMORIES_CONFIRMATION = "CLEAR MEMORIES";
const DELETE_THREAD_CONFIRMATION = "DELETE THREAD";

export function DataPanel({
  streaming,
  messageCount,
  memoryCount,
  conversationCount,
  activeConversationTitle,
  onExport,
  onDeleteAccount,
  onClearMessages,
  onClearMemories,
  onDeleteConversation,
  accountActionId,
  deletingConversationId
}: {
  streaming: boolean;
  messageCount: number;
  memoryCount: number;
  conversationCount: number;
  activeConversationTitle: string;
  onExport: () => Promise<boolean>;
  onDeleteAccount: (password: string, confirmation: string) => Promise<boolean>;
  onClearMessages: () => Promise<boolean>;
  onClearMemories: () => Promise<boolean>;
  onDeleteConversation: () => Promise<boolean>;
  accountActionId: string | null;
  deletingConversationId: string | null;
}) {
  const [cleanupConfirmation, setCleanupConfirmation] = useState("");
  const [accountPassword, setAccountPassword] = useState("");
  const [accountConfirmation, setAccountConfirmation] = useState("");
  const accountDeleteReady =
    accountPassword.length > 0 && accountConfirmation === "DELETE MY ACCOUNT";
  const canClearMessages =
    messageCount > 0 && cleanupConfirmation.trim() === CLEAR_CHAT_CONFIRMATION;
  const canClearMemories = cleanupConfirmation.trim() === CLEAR_MEMORIES_CONFIRMATION;
  const canDeleteConversation =
    conversationCount > 0 && cleanupConfirmation.trim() === DELETE_THREAD_CONFIRMATION;

  function submitAccountDelete() {
    if (!accountDeleteReady) {
      return;
    }
    void onDeleteAccount(accountPassword, accountConfirmation);
  }

  async function submitClearMessages() {
    if (!canClearMessages) {
      return;
    }
    if (await onClearMessages()) {
      setCleanupConfirmation("");
    }
  }

  async function submitClearMemories() {
    if (!canClearMemories) {
      return;
    }
    if (await onClearMemories()) {
      setCleanupConfirmation("");
    }
  }

  async function submitDeleteConversation() {
    if (!canDeleteConversation) {
      return;
    }
    if (await onDeleteConversation()) {
      setCleanupConfirmation("");
    }
  }

  return (
    <div className="space-y-3">
      <section className="rounded-md border border-line bg-ink p-3 text-sm">
        <p className="font-medium">Private export and cleanup</p>
        <p className="mt-1 text-xs leading-5 text-zinc-500">
          Export is scoped to this account and excludes password hashes, token hashes, secrets, and
          other users. Destructive actions only affect the current account scope.
        </p>
      </section>
      <div className="grid grid-cols-3 gap-2">
        <DataStat label="Messages" value={messageCount.toString()} />
        <DataStat label="Active recall" value={memoryCount.toString()} />
        <DataStat label="Threads" value={conversationCount.toString()} />
      </div>
      <p className="rounded-md border border-line bg-ink p-3 text-xs text-zinc-400">
        Current thread: {activeConversationTitle}
      </p>
      <button
        className={primaryButtonClass}
        disabled={streaming}
        onClick={() => void onExport()}
        type="button"
      >
        {accountActionId === "export" ? "Preparing..." : "Export JSON"}
      </button>
      <section className="space-y-3 rounded-md border border-amber-900 bg-amber-950/30 p-3 text-sm text-amber-100">
        <div>
          <p className="font-medium">Scoped cleanup</p>
          <p className="mt-1 text-xs leading-5 text-amber-100/80">
            Type the exact phrase for the action you want. Each phrase unlocks only one cleanup
            button.
          </p>
        </div>
        <div className="grid gap-2 text-xs text-amber-100/80 sm:grid-cols-3">
          <ConfirmationHint label="Clear chat" phrase={CLEAR_CHAT_CONFIRMATION} />
          <ConfirmationHint label="Clear memories" phrase={CLEAR_MEMORIES_CONFIRMATION} />
          <ConfirmationHint label="Delete thread" phrase={DELETE_THREAD_CONFIRMATION} />
        </div>
        <label className="block text-sm text-zinc-300">
          Cleanup phrase
          <input
            aria-label="Cleanup phrase"
            className="mt-1 w-full rounded-md border border-amber-900 bg-ink/90 px-3 py-2 text-sm text-paper shadow-inner shadow-black/20 placeholder:text-zinc-600"
            value={cleanupConfirmation}
            onChange={(event) => setCleanupConfirmation(event.target.value)}
          />
        </label>
      </section>
      <div className="grid gap-2">
        <p className="rounded-md border border-line bg-ink p-3 text-xs leading-5 text-zinc-400">
          Clear chat removes this thread&apos;s messages, journal, and queued notes. Saved memories
          and relationship history remain until cleared separately.
        </p>
        <button
          className={secondaryButtonClass}
          disabled={!canClearMessages}
          onClick={() => void submitClearMessages()}
          type="button"
        >
          Clear chat
        </button>
        <button
          className={secondaryButtonClass}
          disabled={streaming || !canClearMemories}
          onClick={() => void submitClearMemories()}
          type="button"
        >
          Clear memories
        </button>
        <button
          className={secondaryButtonClass}
          disabled={streaming || !canDeleteConversation}
          onClick={() => void submitDeleteConversation()}
          type="button"
        >
          {deletingConversationId ? "Deleting thread..." : "Delete conversation"}
        </button>
      </div>
      <section className="space-y-3 rounded-md border border-red-950 bg-red-950/20 p-3">
        <div>
          <p className="text-sm font-medium text-red-100">Delete account</p>
          <p className="mt-1 text-xs leading-5 text-red-200/70">
            Removes the account and its characters, conversations, messages, memories, journals,
            relationship state, and scheduled jobs.
          </p>
        </div>
        <label className="block text-sm text-zinc-300">
          Current password
          <input
            aria-label="Current account password"
            autoComplete="current-password"
            className="mt-1 w-full rounded-md border border-red-950 bg-ink/90 px-3 py-2 text-sm text-paper shadow-inner shadow-black/20 placeholder:text-zinc-600"
            maxLength={256}
            disabled={streaming}
            type="password"
            value={accountPassword}
            onChange={(event) => setAccountPassword(event.target.value)}
          />
        </label>
        <label className="block text-sm text-zinc-300">
          Type DELETE MY ACCOUNT
          <input
            aria-label="Account deletion phrase"
            className="mt-1 w-full rounded-md border border-red-950 bg-ink/90 px-3 py-2 text-sm text-paper shadow-inner shadow-black/20 placeholder:text-zinc-600"
            maxLength={17}
            disabled={streaming}
            value={accountConfirmation}
            onChange={(event) => setAccountConfirmation(event.target.value)}
          />
        </label>
        <button
          className="rounded-md border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-50 hover:border-red-500 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={streaming || !accountDeleteReady}
          onClick={submitAccountDelete}
          type="button"
        >
          {accountActionId === "delete" ? "Deleting..." : "Delete account"}
        </button>
      </section>
    </div>
  );
}

function ConfirmationHint({ label, phrase }: { label: string; phrase: string }) {
  return (
    <div className="rounded border border-amber-900/80 bg-amber-950/30 px-2 py-1">
      <p className="text-amber-100">{label}</p>
      <p className="mt-0.5 font-mono text-[11px] text-amber-100/70">{phrase}</p>
    </div>
  );
}

function DataStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-ink p-2">
      <p className="text-[11px] uppercase text-zinc-600">{label}</p>
      <p className="mt-1 font-mono text-sm text-zinc-200">{value}</p>
    </div>
  );
}
