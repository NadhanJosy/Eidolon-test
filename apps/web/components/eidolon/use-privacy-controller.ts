"use client";

import { useLayoutEffect, useRef, useState } from "react";

import { apiErrorFromResponse, apiFetch, apiJson } from "@/lib/api";

import { conversationPrivacyMode, readError } from "./controller-utils";
import { completeMessage, completeMessageList } from "./message-contract";
import type { Conversation, Message } from "./types";

type UsePrivacyControllerArgs = {
  token: string | null;
  sessionOwnerId: string | null;
  activeConversation: Conversation | null;
  activeCharacterId: string | null;
  messages: Message[];
  chatSending: boolean;
  interactionBusy: boolean;
  appendMessage: (message: Message) => void;
  cancelActiveStream: () => void;
  resetChat: () => void;
  setError: (value: string | null) => void;
  setNotice: (value: string | null) => void;
  refreshSideState: (
    authToken: string,
    characterId: string,
    conversationId: string,
    shouldApply?: () => boolean
  ) => Promise<void>;
};

type ConversationAction = {
  id: number;
  kind: "proactive" | "clear";
  ownerUserId: string;
  token: string;
  sessionGeneration: number;
  conversationId: string;
  characterId: string;
  knownMessageIds: Set<string>;
};

export function usePrivacyController({
  token,
  sessionOwnerId,
  activeConversation,
  activeCharacterId,
  messages,
  chatSending,
  interactionBusy,
  appendMessage,
  cancelActiveStream,
  resetChat,
  setError,
  setNotice,
  refreshSideState
}: UsePrivacyControllerArgs) {
  const [conversationMutating, setConversationMutating] = useState(false);
  const actionInFlight = useRef<ConversationAction | null>(null);
  const sessionGeneration = useRef(0);
  const sessionOwnerIdRef = useRef(sessionOwnerId);
  const nextActionId = useRef(0);
  const activeConversationId = activeConversation?.id ?? null;
  const activeConversationIdRef = useRef(activeConversationId);

  function invalidateConversationAction() {
    sessionGeneration.current += 1;
    actionInFlight.current = null;
    setConversationMutating(false);
  }

  function actionStillApplies(action: ConversationAction): boolean {
    return (
      actionInFlight.current === action &&
      sessionGeneration.current === action.sessionGeneration &&
      sessionOwnerIdRef.current === action.ownerUserId
    );
  }

  useLayoutEffect(() => {
    if (sessionOwnerIdRef.current === sessionOwnerId) {
      return;
    }
    sessionOwnerIdRef.current = sessionOwnerId;
    invalidateConversationAction();
  }, [sessionOwnerId]);

  useLayoutEffect(() => {
    activeConversationIdRef.current = activeConversationId;
    const action = actionInFlight.current;
    if (action && action.conversationId !== activeConversationId) {
      invalidateConversationAction();
    }
  }, [activeConversationId]);

  async function queueProactive() {
    if (
      !token ||
      !sessionOwnerId ||
      !activeConversation ||
      !activeCharacterId ||
      chatSending ||
      interactionBusy ||
      actionInFlight.current
    ) {
      return;
    }
    setError(null);
    if (conversationPrivacyMode(activeConversation) === "private") {
      setNotice("This conversation is private, so companion notes stay paused here.");
      return;
    }
    const authToken = token;
    const conversationId = activeConversation.id;
    const characterId = activeCharacterId;
    const action: ConversationAction = {
      id: ++nextActionId.current,
      kind: "proactive",
      ownerUserId: sessionOwnerId,
      token: authToken,
      sessionGeneration: sessionGeneration.current,
      conversationId,
      characterId,
      knownMessageIds: new Set(messages.map((message) => message.id))
    };
    const shouldApply = () =>
      actionStillApplies(action) &&
      activeConversationIdRef.current === conversationId;
    let requestAccepted = false;
    let messagePersisted = false;
    actionInFlight.current = action;
    setConversationMutating(true);
    setNotice(null);
    try {
      const response = await acceptedJsonMutation(
        `/debug/conversation/${conversationId}/proactive`,
        "POST",
        action.token
      );
      requestAccepted = true;
      if (!shouldApply()) {
        return;
      }
      if (response.readable && response.value === null) {
        setNotice("Presence is paused, snoozed, or cooling down.");
        return;
      }
      let message = expectedProactiveMessage(response.value, action);
      if (!message) {
        const canonical = await readCanonicalTranscript(action);
        message = recoveredProactiveMessage(canonical, action);
        if (!message) {
          throw new Error(
            "The note was requested, but it could not be confirmed in your history. Reload Eidolon before requesting another."
          );
        }
      }
      if (!shouldApply()) {
        return;
      }
      messagePersisted = true;
      appendMessage(message);
      await refreshSideState(authToken, characterId, conversationId, shouldApply);
      if (shouldApply()) {
        setNotice("A check-in arrived.");
      }
    } catch (caught) {
      if (shouldApply()) {
        setError(
          messagePersisted
            ? "A check-in was saved, but the conversation could not refresh. Reload Eidolon before continuing this conversation."
            : requestAccepted
              ? "The note may have been prepared, but it could not be confirmed. Reload Eidolon before requesting another."
              : readError(caught)
        );
      }
    } finally {
      if (actionStillApplies(action)) {
        actionInFlight.current = null;
        setConversationMutating(false);
      }
    }
  }

  async function clearConversationMessages(): Promise<boolean> {
    if (
      !token ||
      !sessionOwnerId ||
      !activeConversation ||
      !activeCharacterId ||
      interactionBusy ||
      actionInFlight.current
    ) {
      return false;
    }
    const authToken = token;
    const conversationId = activeConversation.id;
    const characterId = activeCharacterId;
    const action: ConversationAction = {
      id: ++nextActionId.current,
      kind: "clear",
      ownerUserId: sessionOwnerId,
      token: authToken,
      sessionGeneration: sessionGeneration.current,
      conversationId,
      characterId,
      knownMessageIds: new Set(messages.map((message) => message.id))
    };
    const shouldApply = () =>
      actionStillApplies(action) &&
      activeConversationIdRef.current === conversationId;
    let accepted = false;
    let verified = false;
    actionInFlight.current = action;
    setConversationMutating(true);
    setError(null);
    setNotice(null);
    try {
      cancelActiveStream();
      const response = await acceptedJsonMutation(
        `/conversations/${conversationId}/messages`,
        "DELETE",
        action.token
      );
      accepted = true;
      if (!shouldApply()) {
        return true;
      }
      let deleted: number | null = null;
      if (
        response.readable &&
        isDeleteCountResponse(response.value) &&
        response.value.deleted >= action.knownMessageIds.size
      ) {
        deleted = response.value.deleted;
      } else {
        const canonical = await readCanonicalTranscript(action);
        if (canonical.length !== 0) {
          throw new Error(
            "The conversation could not be confirmed as cleared, so it remains visible. Reload Eidolon before trying again."
          );
        }
      }
      if (!shouldApply()) {
        return true;
      }
      verified = true;
      resetChat();
      await refreshSideState(authToken, characterId, conversationId, shouldApply);
      if (shouldApply()) {
        setNotice(
          deleted !== null
            ? `${deleted} messages cleared with this thread's journal and queued notes.`
            : "Conversation cleared, along with its moments and waiting notes."
        );
      }
      return true;
    } catch (caught) {
      if (shouldApply()) {
        setError(
          verified
            ? "Chat was cleared, but the conversation could not refresh. Reload Eidolon before continuing this conversation."
            : accepted
              ? "The conversation may have been cleared, but the change could not be confirmed. Your messages remain visible until you reload."
            : readError(caught)
        );
      }
      return verified;
    } finally {
      if (actionStillApplies(action)) {
        actionInFlight.current = null;
        setConversationMutating(false);
      }
    }
  }

  return {
    conversationMutating,
    queueProactive,
    clearConversationMessages
  };
}

async function readCanonicalTranscript(action: ConversationAction): Promise<Message[]> {
  const value = await apiJson<unknown>(
    `/conversations/${action.conversationId}/messages`,
    { token: action.token }
  );
  const messages = completeMessageList(value, action.conversationId);
  if (!messages) {
    throw new Error("The conversation history could not be reopened safely.");
  }
  return messages;
}

function expectedProactiveMessage(
  value: unknown,
  action: ConversationAction
): Message | null {
  const message = completeMessage(value, action.conversationId);
  return message?.role === "assistant" &&
    message.metadata_json.proactive === true &&
    message.content.length <= 600 &&
    !action.knownMessageIds.has(message.id)
    ? message
    : null;
}

function recoveredProactiveMessage(
  messages: Message[],
  action: ConversationAction
): Message | null {
  const candidates = messages.filter(
    (message) =>
      message.role === "assistant" &&
      message.metadata_json.proactive === true &&
      message.content.length <= 600 &&
      !action.knownMessageIds.has(message.id)
  );
  return candidates.length === 1 ? candidates[0] : null;
}

function isDeleteCountResponse(value: unknown): value is { deleted: number } {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.deleted === "number" &&
    Number.isInteger(candidate.deleted) &&
    candidate.deleted >= 0
  );
}

async function acceptedJsonMutation(
  path: string,
  method: "POST" | "DELETE",
  token: string
): Promise<{ readable: boolean; value: unknown }> {
  const response = await apiFetch(path, {
    method,
    body: method === "POST" ? JSON.stringify({}) : undefined,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(method === "POST" ? { "Content-Type": "application/json" } : {})
    }
  });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, path);
  }
  try {
    return { readable: true, value: await response.json() };
  } catch {
    return { readable: false, value: null };
  }
}
