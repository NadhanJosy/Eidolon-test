"use client";

import { FormEvent, useLayoutEffect, useMemo, useRef, useState } from "react";

import { ApiError, apiErrorFromResponse, apiFetch, apiJson, getApiBaseUrl } from "@/lib/api";

import { readError } from "./controller-utils";
import {
  completeContinuityReceipt,
  completeMessage,
  completeMessageList
} from "./message-contract";
import type {
  ChatResponse,
  ContentMode,
  Conversation,
  Message,
  StreamFailure,
  StreamPhase
} from "./types";

type UseChatControllerArgs = {
  token: string | null;
  sessionOwnerId: string | null;
  activeConversation: Conversation | null;
  activeCharacterId: string | null;
  contentMode: ContentMode;
  setError: (value: string | null) => void;
  setNotice: (value: string | null) => void;
  refreshSideState: (
    authToken: string,
    characterId: string,
    conversationId: string,
    shouldApply?: () => boolean
  ) => Promise<void>;
};

type ActiveStream = {
  id: number;
  ownerUserId: string;
  token: string;
  sessionGeneration: number;
  conversationId: string;
  outgoingContent: string;
  retryUserMessageId: string | null;
  knownMessageIds: Set<string>;
  userMessageId: string | null;
  assistantMessageId: string | null;
  receivedCharacters: number;
  controller: AbortController;
  completed: boolean;
  serverErrored: boolean;
};

type EditMutation = {
  id: number;
  ownerUserId: string;
  token: string;
  sessionGeneration: number;
  conversationId: string;
  characterId: string;
  messageId: string;
  content: string;
};

type MessageMutation = {
  id: number;
  ownerUserId: string;
  token: string;
  sessionGeneration: number;
  kind: "reroll" | "delete";
  conversationId: string;
  characterId: string;
  messageId: string;
  messageRole: Message["role"];
  knownMessageIds: Set<string>;
};

export function useChatController({
  token,
  sessionOwnerId,
  activeConversation,
  activeCharacterId,
  contentMode,
  setError,
  setNotice,
  refreshSideState
}: UseChatControllerArgs) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [messageDraft, setMessageDraft] = useState("");
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [privateTurn, setPrivateTurn] = useState(false);
  const [pendingOutgoingContent, setPendingOutgoingContent] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState("");
  const [sending, setSending] = useState(false);
  const [messageMutating, setMessageMutating] = useState(false);
  const [streamPhase, setStreamPhase] = useState<StreamPhase | null>(null);
  const [failedTurn, setFailedTurn] = useState<StreamFailure | null>(null);
  const activeStreamRef = useRef<ActiveStream | null>(null);
  const editSaveInFlight = useRef<EditMutation | null>(null);
  const messageMutationInFlight = useRef<MessageMutation | null>(null);
  const sessionGeneration = useRef(0);
  const sessionOwnerIdRef = useRef(sessionOwnerId);
  const nextActionId = useRef(0);
  const activeConversationId = activeConversation?.id ?? null;
  const activeConversationIdRef = useRef(activeConversationId);

  useLayoutEffect(() => {
    if (sessionOwnerIdRef.current === sessionOwnerId) {
      return;
    }
    sessionOwnerIdRef.current = sessionOwnerId;
    invalidateChatActions();
  }, [sessionOwnerId]);

  const sortedMessages = useMemo(
    () =>
      [...messages].sort(
        (left, right) =>
          new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
      ),
    [messages]
  );

  useLayoutEffect(() => {
    activeConversationIdRef.current = activeConversationId;
    const composerReset = window.setTimeout(() => {
      setPrivateTurn(false);
      setEditingMessageId(null);
      setMessageDraft("");
      setFailedTurn(null);
      setPendingOutgoingContent(null);
    }, 0);
    const stream = activeStreamRef.current;
    if (stream && stream.conversationId !== activeConversationId) {
      stream.controller.abort();
      activeStreamRef.current = null;
      setSending(false);
      setPendingOutgoingContent(null);
      setStreamingContent("");
      setStreamPhase(null);
      setFailedTurn(null);
    }
    const mutation = messageMutationInFlight.current;
    if (mutation && mutation.conversationId !== activeConversationId) {
      messageMutationInFlight.current = null;
      setMessageMutating(false);
    }
    const editMutation = editSaveInFlight.current;
    if (editMutation && editMutation.conversationId !== activeConversationId) {
      editSaveInFlight.current = null;
      setSending(false);
    }
    return () => {
      window.clearTimeout(composerReset);
      const current = activeStreamRef.current;
      if (current?.conversationId === activeConversationId) {
        current.controller.abort();
      }
    };
  }, [activeConversationId]);

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      !token ||
      !sessionOwnerId ||
      sessionOwnerIdRef.current !== sessionOwnerId ||
      !activeConversation ||
      !activeCharacterId ||
      !messageDraft.trim() ||
      activeStreamRef.current ||
      editSaveInFlight.current ||
      messageMutationInFlight.current
    ) {
      return;
    }
    if (messageDraft.trim().length > 6000) {
      setError("Keep messages to 6,000 characters or fewer.");
      return;
    }
    if (editingMessageId) {
      await saveEditedMessage();
      return;
    }
    await startMessageStream(messageDraft.trim(), null);
  }

  async function retryFailedTurn() {
    if (!failedTurn || !failedTurn.retryable) {
      return;
    }
    await startMessageStream(failedTurn.content, failedTurn.userMessageId);
  }

  async function startMessageStream(
    outgoingContent: string,
    retryUserMessageId: string | null
  ) {
    if (
      !token ||
      !sessionOwnerId ||
      sessionOwnerIdRef.current !== sessionOwnerId ||
      !activeConversation ||
      !activeCharacterId ||
      activeStreamRef.current ||
      editSaveInFlight.current ||
      messageMutationInFlight.current
    ) {
      return;
    }
    const authToken = token;
    const conversationId = activeConversation.id;
    const characterId = activeCharacterId;
    const stream: ActiveStream = {
      id: ++nextActionId.current,
      ownerUserId: sessionOwnerId,
      token: authToken,
      sessionGeneration: sessionGeneration.current,
      conversationId,
      outgoingContent,
      retryUserMessageId,
      knownMessageIds: new Set(messages.map((message) => message.id)),
      userMessageId: retryUserMessageId,
      assistantMessageId: null,
      receivedCharacters: 0,
      controller: new AbortController(),
      completed: false,
      serverErrored: false
    };
    activeStreamRef.current = stream;
    setSending(true);
    setStreamPhase("connecting");
    setError(null);
    setNotice(null);
    setPendingOutgoingContent(retryUserMessageId ? null : outgoingContent);
    setStreamingContent("");
    setFailedTurn(null);

    try {
      const response = await apiFetch("/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify({
          conversation_id: conversationId,
          content: outgoingContent,
          content_mode: contentMode,
          privacy_mode: privateTurn ? "private" : "normal",
          retry_user_message_id: retryUserMessageId
        }),
        signal: stream.controller.signal
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
      await readEventStream(response.body, stream);
      if (isCurrentStream(stream)) {
        await refreshSideState(authToken, characterId, conversationId);
        if (stream.assistantMessageId) {
          void settleContinuityReceipt(stream, characterId);
        }
      }
    } catch (caught) {
      if (!stream.controller.signal.aborted && isCurrentStream(stream)) {
        const detail = readError(caught);
        setError(detail);
        if (stream.userMessageId) {
          setFailedTurn({
            userMessageId: stream.userMessageId,
            content: stream.outgoingContent,
            detail,
            failureType: "connection_closed",
            retryable: true
          });
        }
      }
    } finally {
      if (activeStreamRef.current === stream) {
        activeStreamRef.current = null;
        setSending(false);
        setPendingOutgoingContent(null);
        setStreamingContent("");
        setStreamPhase(null);
      }
    }
  }

  async function saveEditedMessage() {
    if (
      !token ||
      !sessionOwnerId ||
      sessionOwnerIdRef.current !== sessionOwnerId ||
      !activeConversation ||
      !activeCharacterId ||
      !editingMessageId ||
      !messageDraft.trim() ||
      editSaveInFlight.current ||
      messageMutationInFlight.current
    ) {
      return;
    }
    const authToken = token;
    const conversationId = activeConversation.id;
    const characterId = activeCharacterId;
    const messageId = editingMessageId;
    const content = messageDraft.trim();
    if (content.length > 6000) {
      setError("Keep messages to 6,000 characters or fewer.");
      return;
    }
    const mutation: EditMutation = {
      id: ++nextActionId.current,
      ownerUserId: sessionOwnerId,
      token: authToken,
      sessionGeneration: sessionGeneration.current,
      conversationId,
      characterId,
      messageId,
      content
    };
    const shouldApply = () =>
      editMutationStillApplies(mutation) &&
      activeConversationIdRef.current === conversationId;
    let persisted = false;
    editSaveInFlight.current = mutation;
    setSending(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await acceptedJsonMutation(
        `/conversations/${conversationId}/messages/${messageId}`,
        "PATCH",
        { content },
        mutation.token
      );
      persisted = true;
      if (!shouldApply()) {
        return;
      }
      let editedTurn = isExpectedEditedTurn(
        updated,
        conversationId,
        messageId,
        content
      )
        ? updated
        : null;
      let canonicalMessages: Message[] | null = null;
      if (!editedTurn) {
        canonicalMessages = await readCanonicalTranscript(mutation.token, conversationId);
        editedTurn = recoveredEditedTurn(canonicalMessages, mutation);
        if (!editedTurn) {
          throw new Error(
            "Your revision may have been saved, but the new reply could not be confirmed. Your words are still here; reload Eidolon before trying again."
          );
        }
      }
      if (!shouldApply()) {
        return;
      }
      if (canonicalMessages) {
        setMessages(canonicalMessages);
      } else {
        setMessages((current) =>
          shouldApply()
            ? replaceEditedTurn(
                current,
                editedTurn.user_message,
                editedTurn.assistant_message
              )
            : current
        );
      }
      setEditingMessageId(null);
      setMessageDraft("");
      await refreshSideState(authToken, characterId, conversationId, shouldApply);
      if (shouldApply()) {
        setNotice("Message edited. The reply was refreshed.");
      }
    } catch (caught) {
      if (shouldApply()) {
        setError(
          persisted
            ? "Message edited, but the conversation could not refresh. Reload Eidolon before continuing this conversation."
            : readError(caught)
        );
      }
    } finally {
      if (editMutationStillApplies(mutation)) {
        editSaveInFlight.current = null;
        setSending(false);
      }
    }
  }

  async function readEventStream(
    body: ReadableStream<Uint8Array>,
    stream: ActiveStream
  ) {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (isCurrentStream(stream)) {
        const { value, done } = await reader.read();
        if (done) {
          buffer += decoder.decode();
          break;
        }
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          handleSseEvent(part, stream);
        }
      }
      if (buffer.trim() && isCurrentStream(stream)) {
        handleSseEvent(buffer, stream);
      }
      if (
        isCurrentStream(stream) &&
        !stream.completed &&
        !stream.serverErrored
      ) {
        throw new ApiError(
          "The reply stream closed before Eidolon finished the message.",
          0
        );
      }
    } finally {
      if (stream.controller.signal.aborted) {
        await reader.cancel().catch(() => undefined);
      }
      reader.releaseLock();
    }
  }

  function handleSseEvent(block: string, stream: ActiveStream) {
    if (!isCurrentStream(stream) || stream.completed || stream.serverErrored) {
      return;
    }
    const lines = block.split("\n");
    const eventLine = lines.find((line) => line.startsWith("event:"));
    const dataLines = lines
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trim());
    const event = eventLine?.replace("event:", "").trim();
    const data = dataLines.join("\n");
    if (!event || !data) {
      return;
    }
    let decoded: unknown;
    try {
      decoded = JSON.parse(data);
    } catch {
      failStreamBoundary(
        stream,
        "A streamed reply arrived in a shape Eidolon could not read."
      );
      return;
    }
    if (typeof decoded !== "object" || decoded === null || Array.isArray(decoded)) {
      failStreamBoundary(
        stream,
        "A streamed reply arrived in a shape Eidolon could not read."
      );
      return;
    }
    const payload = decoded as Record<string, unknown>;
    if (event === "message_start") {
      const userMessage = completeMessage(payload.user_message, stream.conversationId);
      const freshBoundary =
        userMessage?.role === "user" &&
        userMessage.content === stream.outgoingContent &&
        !stream.knownMessageIds.has(userMessage.id) &&
        stream.userMessageId === null;
      const retryBoundary =
        userMessage?.role === "user" &&
        userMessage.content === stream.outgoingContent &&
        stream.retryUserMessageId !== null &&
        userMessage.id === stream.retryUserMessageId &&
        payload.retry === true;
      if (freshBoundary || retryBoundary) {
        stream.userMessageId = userMessage.id;
        upsertMessage(userMessage);
        if (!stream.retryUserMessageId) {
          setMessageDraft("");
          setPrivateTurn(false);
        }
        setPendingOutgoingContent(null);
        setStreamPhase("composing");
      } else {
        failStreamBoundary(
          stream,
          "Eidolon accepted the turn but returned an unreadable message boundary."
        );
      }
      return;
    }
    if (event === "token") {
      if (stream.userMessageId === null) {
        return;
      }
      if (typeof payload.content !== "string" || payload.content.length === 0) {
        failStreamBoundary(stream, "A reply fragment arrived in an unreadable shape.");
        return;
      }
      stream.receivedCharacters += payload.content.length;
      if (stream.receivedCharacters > 24_000) {
        failStreamBoundary(
          stream,
          "The streamed reply exceeded Eidolon's readable message limit."
        );
        return;
      }
      setStreamPhase("streaming");
      setStreamingContent((current) => current + payload.content);
      return;
    }
    if (event === "message_done") {
      const assistantMessage = completeMessage(
        payload.assistant_message,
        stream.conversationId
      );
      if (
        assistantMessage?.role === "assistant" &&
        !stream.serverErrored &&
        stream.userMessageId !== null &&
        !stream.knownMessageIds.has(assistantMessage.id) &&
        assistantMessage.id !== stream.userMessageId
      ) {
        stream.completed = true;
        stream.assistantMessageId = assistantMessage.id;
        appendMessage(assistantMessage);
        setFailedTurn(null);
        setStreamingContent("");
        setStreamPhase(null);
      } else {
        failStreamBoundary(
          stream,
          "Eidolon finished the reply with an unreadable message boundary."
        );
      }
      return;
    }
    if (event === "error") {
      const detail = payload.detail;
      failStreamBoundary(
        stream,
        typeof detail === "string" && detail.length > 0 && detail.length <= 500
          ? detail
          : "Eidolon could not finish this reply.",
        {
          failureType:
            typeof payload.failure_type === "string"
              ? payload.failure_type
              : "provider_unavailable",
          retryable: payload.retryable !== false
        }
      );
    }
  }

  function failStreamBoundary(
    stream: ActiveStream,
    detail: string,
    options: { failureType?: string; retryable?: boolean } = {}
  ) {
    stream.serverErrored = true;
    setError(detail);
    setStreamPhase(null);
    setStreamingContent("");
    if (stream.userMessageId) {
      setFailedTurn({
        userMessageId: stream.userMessageId,
        content: stream.outgoingContent,
        detail,
        failureType: options.failureType || "stream_error",
        retryable: options.retryable !== false
      });
    }
    stream.controller.abort();
  }

  function isCurrentStream(stream: ActiveStream): boolean {
    return (
      activeStreamRef.current === stream &&
      sessionGeneration.current === stream.sessionGeneration &&
      sessionOwnerIdRef.current === stream.ownerUserId &&
      activeConversationIdRef.current === stream.conversationId &&
      !stream.controller.signal.aborted
    );
  }

  function streamContextStillApplies(stream: ActiveStream): boolean {
    return (
      sessionGeneration.current === stream.sessionGeneration &&
      sessionOwnerIdRef.current === stream.ownerUserId &&
      activeConversationIdRef.current === stream.conversationId
    );
  }

  async function settleContinuityReceipt(stream: ActiveStream, characterId: string) {
    const assistantMessageId = stream.assistantMessageId;
    if (!assistantMessageId) {
      return;
    }
    const delays = [350, 650, 1100, 1800, 2600];
    for (const delay of delays) {
      if (!streamContextStillApplies(stream)) {
        return;
      }
      await new Promise<void>((resolve) => window.setTimeout(resolve, delay));
      try {
        const value = await apiJson<unknown>(
          `/chat/turns/${assistantMessageId}/continuity`,
          { token: stream.token }
        );
        const receipt = completeContinuityReceipt(value);
        if (!receipt) {
          return;
        }
        if (receipt.state === "pending") {
          continue;
        }
        if (!streamContextStillApplies(stream)) {
          return;
        }
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantMessageId
              ? {
                  ...message,
                  metadata_json: {
                    ...message.metadata_json,
                    continuity_receipt: receipt
                  }
                }
              : message
          )
        );
        await refreshSideState(
          stream.token,
          characterId,
          stream.conversationId,
          () => streamContextStillApplies(stream)
        );
        return;
      } catch {
        // The reply remains usable even when its optional continuity receipt is delayed.
      }
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

  function upsertMessage(message: Message) {
    setMessages((current) => {
      const index = current.findIndex((item) => item.id === message.id);
      if (index === -1) {
        return [...current, message];
      }
      return [...current.slice(0, index), message, ...current.slice(index + 1)];
    });
  }

  function replaceEditedTurn(
    current: Message[],
    userMessage: Message,
    assistantMessage: Message
  ): Message[] {
    const editedIndex = current.findIndex((message) => message.id === userMessage.id);
    if (editedIndex === -1) {
      return [...current, userMessage, assistantMessage];
    }
    return [...current.slice(0, editedIndex), userMessage, assistantMessage];
  }

  async function rerollMessage(message: Message) {
    if (
      !token ||
      !sessionOwnerId ||
      sessionOwnerIdRef.current !== sessionOwnerId ||
      !activeConversation ||
      !activeCharacterId ||
      activeStreamRef.current ||
      editSaveInFlight.current ||
      messageMutationInFlight.current ||
      message.role !== "assistant" ||
      message.conversation_id !== activeConversation.id
    ) {
      return;
    }
    const authToken = token;
    const conversationId = activeConversation.id;
    const characterId = activeCharacterId;
    const messageId = message.id;
    const requestedContentMode = contentMode;
    const mutation: MessageMutation = {
      id: ++nextActionId.current,
      ownerUserId: sessionOwnerId,
      token: authToken,
      sessionGeneration: sessionGeneration.current,
      kind: "reroll",
      conversationId,
      characterId,
      messageId,
      messageRole: message.role,
      knownMessageIds: new Set(messages.map((item) => item.id))
    };
    const shouldApply = () =>
      messageMutationStillApplies(mutation) &&
      activeConversationIdRef.current === conversationId;
    let persisted = false;
    messageMutationInFlight.current = mutation;
    setMessageMutating(true);
    setError(null);
    setNotice(null);
    try {
      const rerolled = await acceptedJsonMutation(
        "/chat/reroll",
        "POST",
        {
          conversation_id: conversationId,
          assistant_message_id: messageId,
          content_mode: requestedContentMode
        },
        mutation.token
      );
      persisted = true;
      if (!shouldApply()) {
        return;
      }
      let rerolledMessage = isExpectedReroll(rerolled, mutation) ? rerolled : null;
      let canonicalMessages: Message[] | null = null;
      if (!rerolledMessage) {
        canonicalMessages = await readCanonicalTranscript(mutation.token, conversationId);
        rerolledMessage = recoveredReroll(canonicalMessages, mutation);
        if (!rerolledMessage) {
          throw new Error(
            "A fresh reply may have been saved, but it could not be confirmed. Reload Eidolon before asking again."
          );
        }
      }
      if (canonicalMessages) {
        setMessages(canonicalMessages);
      } else {
        setMessages((current) =>
          shouldApply() && !current.some((item) => item.id === rerolledMessage.id)
            ? [...current, rerolledMessage]
            : current
        );
      }
      await refreshSideState(authToken, characterId, conversationId, shouldApply);
      if (shouldApply()) {
        setNotice("A fresh reply was added.");
      }
    } catch (caught) {
      if (shouldApply()) {
        setError(
          persisted
            ? "A fresh reply was saved, but the conversation could not refresh. Reload Eidolon before continuing this conversation."
            : readError(caught)
        );
      }
    } finally {
      if (messageMutationStillApplies(mutation)) {
        messageMutationInFlight.current = null;
        setMessageMutating(false);
      }
    }
  }

  async function deleteMessage(message: Message) {
    if (
      !token ||
      !sessionOwnerId ||
      sessionOwnerIdRef.current !== sessionOwnerId ||
      !activeConversation ||
      !activeCharacterId ||
      activeStreamRef.current ||
      editSaveInFlight.current ||
      messageMutationInFlight.current ||
      message.conversation_id !== activeConversation.id
    ) {
      return;
    }
    const authToken = token;
    const conversationId = activeConversation.id;
    const characterId = activeCharacterId;
    const messageId = message.id;
    const messageRole = message.role;
    const mutation: MessageMutation = {
      id: ++nextActionId.current,
      ownerUserId: sessionOwnerId,
      token: authToken,
      sessionGeneration: sessionGeneration.current,
      kind: "delete",
      conversationId,
      characterId,
      messageId,
      messageRole,
      knownMessageIds: new Set(messages.map((item) => item.id))
    };
    const shouldApply = () =>
      messageMutationStillApplies(mutation) &&
      activeConversationIdRef.current === conversationId;
    let persisted = false;
    messageMutationInFlight.current = mutation;
    setMessageMutating(true);
    setError(null);
    setNotice(null);
    try {
      const response = await acceptedJsonMutation(
        `/conversations/${conversationId}/messages/${messageId}`,
        "DELETE",
        null,
        mutation.token
      );
      persisted = true;
      if (!shouldApply()) {
        return;
      }
      if (isDeleteResponse(response)) {
        setMessages((current) =>
          shouldApply() ? removeDeletedMessage(current, message) : current
        );
      } else {
        const canonicalMessages = await readCanonicalTranscript(
          mutation.token,
          conversationId
        );
        if (canonicalMessages.some((item) => item.id === messageId)) {
          throw new Error(
            `${messageRole === "user" ? "The turn" : "The message"} may have been removed, but the canonical conversation still contains it. Reload Eidolon before deleting again.`
          );
        }
        if (!shouldApply()) {
          return;
        }
        setMessages(canonicalMessages);
      }
      await refreshSideState(authToken, characterId, conversationId, shouldApply);
      if (shouldApply()) {
        setNotice(messageRole === "user" ? "Turn removed." : "Message removed.");
      }
    } catch (caught) {
      if (shouldApply()) {
        setError(
          persisted
            ? `${messageRole === "user" ? "The turn" : "The message"} was removed, but the conversation could not refresh. Reload Eidolon before continuing this conversation.`
            : readError(caught)
        );
      }
    } finally {
      if (messageMutationStillApplies(mutation)) {
        messageMutationInFlight.current = null;
        setMessageMutating(false);
      }
    }
  }

  function removeDeletedMessage(current: Message[], message: Message): Message[] {
    if (message.role !== "user") {
      return current.filter((item) => item.id !== message.id);
    }
    const deletedIndex = current.findIndex((item) => item.id === message.id);
    if (deletedIndex === -1) {
      return current;
    }
    return current.slice(0, deletedIndex);
  }

  function startEditMessage(message: Message) {
    if (
      activeStreamRef.current ||
      editSaveInFlight.current ||
      messageMutationInFlight.current
    ) {
      return;
    }
    setPrivateTurn(false);
    setEditingMessageId(message.id);
    setMessageDraft(message.content);
  }

  function cancelEditMessage() {
    if (editSaveInFlight.current || messageMutationInFlight.current) {
      return;
    }
    setEditingMessageId(null);
    setMessageDraft("");
  }

  function cancelActiveStream() {
    const stream = activeStreamRef.current;
    if (!stream) {
      return;
    }
    stream.controller.abort();
    activeStreamRef.current = null;
    if (stream.userMessageId) {
      setFailedTurn({
        userMessageId: stream.userMessageId,
        content: stream.outgoingContent,
        detail: "You stopped this response.",
        failureType: "cancelled",
        retryable: true
      });
    }
    setError(null);
    setSending(false);
    setPendingOutgoingContent(null);
    setStreamingContent("");
    setStreamPhase(null);
  }

  function resetChat() {
    invalidateChatActions();
    setMessages([]);
    setMessageDraft("");
    setEditingMessageId(null);
    setPrivateTurn(false);
    setFailedTurn(null);
    setPendingOutgoingContent(null);
  }

  function loadMessages(nextMessages: Message[]) {
    setMessages(nextMessages);
    setPendingOutgoingContent(null);
    setFailedTurn(failureFromTranscript(nextMessages));
  }

  function editMutationStillApplies(mutation: EditMutation): boolean {
    return (
      editSaveInFlight.current === mutation &&
      sessionGeneration.current === mutation.sessionGeneration &&
      sessionOwnerIdRef.current === mutation.ownerUserId
    );
  }

  function messageMutationStillApplies(mutation: MessageMutation): boolean {
    return (
      messageMutationInFlight.current === mutation &&
      sessionGeneration.current === mutation.sessionGeneration &&
      sessionOwnerIdRef.current === mutation.ownerUserId
    );
  }

  function invalidateChatActions() {
    sessionGeneration.current += 1;
    activeStreamRef.current?.controller.abort();
    activeStreamRef.current = null;
    editSaveInFlight.current = null;
    messageMutationInFlight.current = null;
    setSending(false);
    setMessageMutating(false);
    setPendingOutgoingContent(null);
    setStreamingContent("");
    setStreamPhase(null);
    setFailedTurn(null);
  }

  async function readCanonicalTranscript(
    authToken: string,
    conversationId: string
  ): Promise<Message[]> {
    const value = await apiJson<unknown>(`/conversations/${conversationId}/messages`, {
      token: authToken
    });
    const canonical = completeMessageList(value, conversationId);
    if (!canonical) {
      throw new Error("The conversation could not be reopened safely.");
    }
    return canonical;
  }

  return {
    state: {
      messages,
      sortedMessages,
      messageDraft,
      editingMessageId,
      privateTurn,
      pendingOutgoingContent,
      streamingContent,
      streamPhase,
      failedTurn,
      sending,
      messageMutating
    },
    actions: {
      setMessages: loadMessages,
      setMessageDraft,
      setPrivateTurn,
      sendMessage,
      retryFailedTurn,
      cancelEditMessage,
      startEditMessage,
      rerollMessage,
      deleteMessage,
      appendMessage,
      cancelActiveStream,
      resetChat
    }
  };
}

function isExpectedEditedTurn(
  value: unknown,
  conversationId: string,
  messageId: string,
  content: string
): value is ChatResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  const userMessage = completeMessage(candidate.user_message, conversationId);
  const assistantMessage = completeMessage(candidate.assistant_message, conversationId);
  return (
    userMessage !== null &&
    assistantMessage !== null &&
    userMessage.id === messageId &&
    userMessage.content === content &&
    userMessage.conversation_id === conversationId &&
    userMessage.role === "user" &&
    assistantMessage.conversation_id === conversationId &&
    assistantMessage.role === "assistant" &&
    assistantMessage.id !== userMessage.id &&
    Date.parse(assistantMessage.created_at) >= Date.parse(userMessage.created_at)
  );
}

function isExpectedReroll(
  value: unknown,
  mutation: MessageMutation
): value is Message {
  const message = completeMessage(value, mutation.conversationId);
  return (
    message !== null &&
    message.role === "assistant" &&
    !mutation.knownMessageIds.has(message.id) &&
    message.metadata_json.reroll_of === mutation.messageId
  );
}

function recoveredEditedTurn(
  messages: Message[],
  mutation: EditMutation
): ChatResponse | null {
  const userIndex = messages.findIndex(
    (message) =>
      message.id === mutation.messageId &&
      message.role === "user" &&
      message.content === mutation.content
  );
  const assistantMessage = userIndex >= 0 ? messages[userIndex + 1] : undefined;
  return assistantMessage?.role === "assistant"
    ? { user_message: messages[userIndex], assistant_message: assistantMessage }
    : null;
}

function recoveredReroll(
  messages: Message[],
  mutation: MessageMutation
): Message | null {
  const candidates = messages.filter(
    (message) =>
      message.role === "assistant" &&
      !mutation.knownMessageIds.has(message.id) &&
      message.metadata_json.reroll_of === mutation.messageId
  );
  return candidates.length === 1 ? candidates[0] : null;
}

function failureFromTranscript(messages: Message[]): StreamFailure | null {
  const latest = [...messages].sort(
    (left, right) =>
      new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
  ).at(-1);
  if (latest?.role !== "user") {
    return null;
  }
  const generationState = latest.metadata_json.generation_state;
  if (generationState !== "retryable" && generationState !== "cancelled") {
    return null;
  }
  return {
    userMessageId: latest.id,
    content: latest.content,
    detail:
      generationState === "cancelled"
        ? "You stopped this response."
        : "Eidolon could not finish this response.",
    failureType: latest.metadata_json.generation_failure_type || generationState,
    retryable: true
  };
}

function isDeleteResponse(value: unknown): value is { deleted: number } {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.deleted === "number" &&
    Number.isInteger(candidate.deleted) &&
    candidate.deleted >= 1
  );
}

async function acceptedJsonMutation(
  path: string,
  method: "POST" | "PATCH" | "DELETE",
  payload: unknown,
  token: string
): Promise<unknown> {
  const response = await apiFetch(path, {
    method,
    body: method === "DELETE" ? undefined : JSON.stringify(payload),
    headers: {
      Authorization: `Bearer ${token}`,
      ...(method === "DELETE" ? {} : { "Content-Type": "application/json" })
    }
  });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, path);
  }
  try {
    return await response.json();
  } catch {
    return null;
  }
}
