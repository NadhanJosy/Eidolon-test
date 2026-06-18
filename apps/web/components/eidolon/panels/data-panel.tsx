import { useState } from "react";

import { primaryButtonClass, secondaryButtonClass } from "../ui";

export function DataPanel({
  messageCount,
  memoryCount,
  conversationCount,
  activeConversationTitle,
  onExport,
  onDeleteAccount,
  onClearMessages,
  onClearMemories,
  onDeleteConversation
}: {
  messageCount: number;
  memoryCount: number;
  conversationCount: number;
  activeConversationTitle: string;
  onExport: () => void;
  onDeleteAccount: (password: string, confirmation: string) => void;
  onClearMessages: () => void;
  onClearMemories: () => void;
  onDeleteConversation: () => void;
}) {
  const [confirmed, setConfirmed] = useState(false);
  const [accountPassword, setAccountPassword] = useState("");
  const [accountConfirmation, setAccountConfirmation] = useState("");
  const accountDeleteReady =
    confirmed && accountPassword.length > 0 && accountConfirmation === "DELETE MY ACCOUNT";

  function submitAccountDelete() {
    if (!accountDeleteReady) {
      return;
    }
    onDeleteAccount(accountPassword, accountConfirmation);
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
        <DataStat label="Memories" value={memoryCount.toString()} />
        <DataStat label="Threads" value={conversationCount.toString()} />
      </div>
      <p className="rounded-md border border-line bg-ink p-3 text-xs text-zinc-400">
        Current thread: {activeConversationTitle}
      </p>
      <button className={primaryButtonClass} onClick={onExport} type="button">
        Export JSON
      </button>
      <label className="flex items-start gap-2 rounded-md border border-amber-900 bg-amber-950/30 p-3 text-sm text-amber-100">
        <input
          className="mt-1"
          type="checkbox"
          checked={confirmed}
          onChange={(event) => setConfirmed(event.target.checked)}
        />
        I understand the cleanup buttons below permanently remove local app data from PostgreSQL.
      </label>
      <div className="grid gap-2">
        <button
          className={secondaryButtonClass}
          disabled={!confirmed || messageCount === 0}
          onClick={onClearMessages}
          type="button"
        >
          Clear chat
        </button>
        <button
          className={secondaryButtonClass}
          disabled={!confirmed || memoryCount === 0}
          onClick={onClearMemories}
          type="button"
        >
          Clear memories
        </button>
        <button
          className={secondaryButtonClass}
          disabled={!confirmed || conversationCount === 0}
          onClick={onDeleteConversation}
          type="button"
        >
          Delete conversation
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
            className="mt-1 w-full rounded-md border border-red-950 bg-ink/90 px-3 py-2 text-sm text-paper shadow-inner shadow-black/20 placeholder:text-zinc-600"
            type="password"
            value={accountPassword}
            onChange={(event) => setAccountPassword(event.target.value)}
          />
        </label>
        <label className="block text-sm text-zinc-300">
          Type DELETE MY ACCOUNT
          <input
            className="mt-1 w-full rounded-md border border-red-950 bg-ink/90 px-3 py-2 text-sm text-paper shadow-inner shadow-black/20 placeholder:text-zinc-600"
            value={accountConfirmation}
            onChange={(event) => setAccountConfirmation(event.target.value)}
          />
        </label>
        <button
          className="rounded-md border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-50 hover:border-red-500 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={!accountDeleteReady}
          onClick={submitAccountDelete}
          type="button"
        >
          Delete account
        </button>
      </section>
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
