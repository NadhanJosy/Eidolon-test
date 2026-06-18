"use client";

import { FormEvent, useMemo, useState } from "react";

import { ApiError, apiErrorFromResponse, apiFetch, apiJson, getApiBaseUrl } from "@/lib/api";

import { isMessage, readError } from "./controller-utils";
import type { ContentMode, Conversation, Message } from "./types";

type UseChatControllerArgs = {
  token: string | null;
  activeConversation: Conversation | null;
  activeCharacterId: string | null;
  contentMode: ContentMode;
  setBusy: (value: boolean) => void;
  setError: (value: string | null) => void;
  setNotice: (value: string | null) => void;
  refreshSideState: (
    authToken: string,
    characterId: string,
    conversationId: string
  ) => Promise<void>;
};

export function useChatController({
  token,
  activeConversation,
  activeCharacterId,
  contentMode,
  setBusy,
  setError,
  setNotice,
  refreshSideState
}: UseChatControllerArgs) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [messageDraft, setMessageDraft] = useState("");
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState("");
  const [sending, setSending] = useState(false);

  const sortedMessages = useMemo(
    () =>
      [...messages].sort(
        (left, right) =>
          new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
      ),
    [messages]
  );

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !activeConversation || !activeCharacterId || !messageDraft.trim()) {
      return;
    }
    if (editingMessageId) {
      await saveEditedMessage();
      return;
    }

    setSending(true);
    setError(null);
    setNotice(null);
    setStreamingContent("");

    try {
      const response = await apiFetch("/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          conversation_id: activeConversation.id,
          content: messageDraft.trim(),
          content_mode: contentMode
        })
      });
      if (!response.ok) {
        throw await apiErrorFromResponse(response, "/chat/stream");
      }
      if (!response.body) {
        throw new ApiError(
          `Eidolon API at ${getApiBaseUrl()}/chat/stream did not open a response stream.`,
          response.status
        );
      }
      setMessageDraft("");
      await readEventStream(response.body);
      await refreshSideState(token, activeCharacterId, activeConversation.id);
    } catch (caught) {
      setError(readError(caught));
    } finally {
      setSending(false);
      setStreamingContent("");
    }
  }

  async function saveEditedMessage() {
    if (!token || !activeConversation || !editingMessageId || !messageDraft.trim()) {
      return;
    }
    setSending(true);
    setError(null);
    try {
      const updated = await apiJson<Message>(
        `/conversations/${activeConversation.id}/messages/${editingMessageId}`,
        {
          method: "PATCH",
          body: JSON.stringify({ content: messageDraft.trim() }),
          token
        }
      );
      setMessages((current) =>
        current.map((message) => (message.id === updated.id ? updated : message))
      );
      setEditingMessageId(null);
      setMessageDraft("");
      setNotice("Message edited.");
    } catch (caught) {
      setError(readError(caught));
    } finally {
      setSending(false);
    }
  }

  async function readEventStream(body: ReadableStream<Uint8Array>) {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        handleSseEvent(part);
      }
    }
    if (buffer.trim()) {
      handleSseEvent(buffer);
    }
  }

  function handleSseEvent(block: string) {
    const eventLine = block.split("\n").find((line) => line.startsWith("event:"));
    const dataLine = block.split("\n").find((line) => line.startsWith("data:"));
    const event = eventLine?.replace("event:", "").trim();
    const data = dataLine?.replace("data:", "").trim();
    if (!event || !data) {
      return;
    }
    const payload = JSON.parse(data) as Record<string, unknown>;
    if (event === "message_start" && isMessage(payload.user_message)) {
      appendMessage(payload.user_message);
    }
    if (event === "token" && typeof payload.content === "string") {
      setStreamingContent((current) => current + payload.content);
    }
    if (event === "message_done" && isMessage(payload.assistant_message)) {
      appendMessage(payload.assistant_message);
      setStreamingContent("");
    }
    if (event === "error" && typeof payload.detail === "string") {
      setError(payload.detail);
    }
  }

  function appendMessage(message: Message) {
    setMessages((current) => {
      if (current.some((item) => item.id === message.id)) {
        return current;
      }
      return [...current, message];
    });
  }

  async function rerollMessage(message: Message) {
    if (!token || !activeConversation || !activeCharacterId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const rerolled = await apiJson<Message>("/chat/reroll", {
        method: "POST",
        body: JSON.stringify({
          conversation_id: activeConversation.id,
          assistant_message_id: message.id,
          content_mode: contentMode
        }),
        token
      });
      appendMessage(rerolled);
      await refreshSideState(token, activeCharacterId, activeConversation.id);
    } catch (caught) {
      setError(readError(caught));
    } finally {
      setBusy(false);
    }
  }

  function startEditMessage(message: Message) {
    setEditingMessageId(message.id);
    setMessageDraft(message.content);
  }

  function cancelEditMessage() {
    setEditingMessageId(null);
    setMessageDraft("");
  }

  function resetChat() {
    setMessages([]);
    setMessageDraft("");
    setEditingMessageId(null);
    setStreamingContent("");
  }

  return {
    state: {
      messages,
      sortedMessages,
      messageDraft,
      editingMessageId,
      streamingContent,
      sending
    },
    actions: {
      setMessages,
      setMessageDraft,
      sendMessage,
      cancelEditMessage,
      startEditMessage,
      rerollMessage,
      resetChat
    }
  };
}
