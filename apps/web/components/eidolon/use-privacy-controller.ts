"use client";

import { apiJson } from "@/lib/api";

import { readError } from "./controller-utils";
import type { Conversation, Message } from "./types";

type UsePrivacyControllerArgs = {
  token: string | null;
  activeConversation: Conversation | null;
  activeCharacterId: string | null;
  setMessages: (messages: Message[]) => void;
  setError: (value: string | null) => void;
  setNotice: (value: string | null) => void;
  onAccountDeleted: (notice: string) => void;
  refreshSideState: (
    authToken: string,
    characterId: string,
    conversationId: string
  ) => Promise<void>;
};

export function usePrivacyController({
  token,
  activeConversation,
  activeCharacterId,
  setMessages,
  setError,
  setNotice,
  onAccountDeleted,
  refreshSideState
}: UsePrivacyControllerArgs) {
  async function queueProactive() {
    if (!token || !activeConversation || !activeCharacterId) {
      return;
    }
    setError(null);
    try {
      const message = await apiJson<Message | null>(
        `/debug/conversation/${activeConversation.id}/proactive`,
        {
          method: "POST",
          body: JSON.stringify({}),
          token
        }
      );
      setNotice(message ? "Queued check-in." : "Cooldown is active.");
      await refreshSideState(token, activeCharacterId, activeConversation.id);
    } catch (caught) {
      setError(readError(caught));
    }
  }

  async function clearConversationMessages() {
    if (!token || !activeConversation || !activeCharacterId) {
      return;
    }
    setError(null);
    try {
      const response = await apiJson<{ deleted: number }>(
        `/conversations/${activeConversation.id}/messages`,
        {
          method: "DELETE",
          token
        }
      );
      setMessages([]);
      setNotice(`${response.deleted} messages cleared.`);
      await refreshSideState(token, activeCharacterId, activeConversation.id);
    } catch (caught) {
      setError(readError(caught));
    }
  }

  async function exportAccount() {
    if (!token) {
      return;
    }
    setError(null);
    try {
      const payload = await apiJson<Record<string, unknown>>("/account/export", { token });
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json"
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `eidolon-export-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
      setNotice("Export ready.");
    } catch (caught) {
      setError(readError(caught));
    }
  }

  async function deleteAccount(password: string, confirmation: string) {
    if (!token) {
      return;
    }
    setError(null);
    try {
      await apiJson<{ deleted: number }>("/account", {
        method: "DELETE",
        body: JSON.stringify({ password, confirmation }),
        token
      });
      onAccountDeleted("Account deleted.");
    } catch (caught) {
      setError(readError(caught));
    }
  }

  return {
    queueProactive,
    clearConversationMessages,
    exportAccount,
    deleteAccount
  };
}
