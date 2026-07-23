"use client";

import { FormEvent, useLayoutEffect, useRef, useState } from "react";

import { apiJson } from "@/lib/api";

import {
  isCompleteContinuityThread,
  isCompleteContinuityThreadList,
  isCompleteJournal as isJournal,
  isCompleteJournalList as isJournalArray,
  isCompleteMemoryItem as isMemoryItem,
  isCompleteMemoryList as isMemoryItemArray
} from "./companion-state-contract";
import { readError } from "./controller-utils";
import type {
  ContinuityThread,
  Conversation,
  Journal,
  MemoryCategory,
  MemoryItem,
  MemoryResolveResult,
  Message
} from "./types";

export type MemoryView = "active" | "forgotten";

function parseDecimal(value: string, fallback: number): number {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

type MemoryActionKind =
  | "add"
  | "edit"
  | "pin"
  | "delete"
  | "forget"
  | "restore"
  | "resolve"
  | "remember"
  | "clear-category"
  | "clear"
  | "clear-adult"
  | "forget-stale";

type MemoryAction = {
  kind: MemoryActionKind;
  key: string;
  characterId: string;
  conversationId: string | null;
  targetId: string | null;
};

type JournalActionKind = "add" | "edit" | "delete";

type JournalAction = {
  kind: JournalActionKind;
  key: string;
  characterId: string;
  conversationId: string | null;
  targetId: string | null;
  title: string | null;
  summary: string | null;
  knownIds: ReadonlySet<string>;
};

type ThreadAction = {
  kind: "add" | "delete" | "resolve" | "reopen";
  key: string;
  characterId: string;
  conversationId: string | null;
  targetId: string | null;
};

type UseKnowledgeControllerArgs = {
  token: string | null;
  activeCharacterId: string | null;
  activeConversation: Conversation | null;
  setError: (value: string | null) => void;
  setNotice: (value: string | null) => void;
  refreshSideState: (
    authToken: string,
    characterId: string,
    conversationId: string,
    shouldApply?: () => boolean
  ) => Promise<void>;
};

export function useKnowledgeController({
  token,
  activeCharacterId,
  activeConversation,
  setError,
  setNotice,
  refreshSideState
}: UseKnowledgeControllerArgs) {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [memoryContent, setMemoryContent] = useState("");
  const [memoryType, setMemoryType] = useState("preference");
  const [memoryImportance, setMemoryImportance] = useState("0.6");
  const [memoryPinned, setMemoryPinned] = useState(false);
  const [editingMemoryId, setEditingMemoryId] = useState<string | null>(null);
  const [memoryEditContent, setMemoryEditContent] = useState("");
  const [rememberingMessageId, setRememberingMessageId] = useState<string | null>(null);
  const [forgottenMemories, setForgottenMemories] = useState<MemoryItem[]>([]);
  const [forgottenMemoriesCharacterId, setForgottenMemoriesCharacterId] = useState<string | null>(
    null
  );
  const [memoryView, setMemoryView] = useState<MemoryView>("active");
  const [memoryViewCharacterId, setMemoryViewCharacterId] = useState<string | null>(null);
  const [memoryActionId, setMemoryActionId] = useState<string | null>(null);
  const [forgottenMemoriesLoading, setForgottenMemoriesLoading] = useState(false);

  const [journals, setJournals] = useState<Journal[]>([]);
  const [journalTitle, setJournalTitle] = useState("");
  const [journalSummary, setJournalSummary] = useState("");
  const [editingJournalId, setEditingJournalId] = useState<string | null>(null);
  const [journalEditTitle, setJournalEditTitle] = useState("");
  const [journalEditSummary, setJournalEditSummary] = useState("");
  const [journalActionId, setJournalActionId] = useState<string | null>(null);
  const [continuityThreads, setContinuityThreads] = useState<ContinuityThread[]>([]);
  const [threadDraft, setThreadDraft] = useState("");
  const [threadActionId, setThreadActionId] = useState<string | null>(null);
  const activeCharacterIdRef = useRef(activeCharacterId);
  const activeConversationId = activeConversation?.id ?? null;
  const activeConversationIdRef = useRef(activeConversationId);
  const memoryActionInFlight = useRef<MemoryAction | null>(null);
  const journalActionInFlight = useRef<JournalAction | null>(null);
  const threadActionInFlight = useRef<ThreadAction | null>(null);
  const forgottenMemoriesCharacterIdRef = useRef<string | null>(null);
  const forgottenRequestVersionRef = useRef(0);

  useLayoutEffect(() => {
    const previousCharacterId = activeCharacterIdRef.current;
    activeCharacterIdRef.current = activeCharacterId;
    forgottenRequestVersionRef.current += 1;
    if (previousCharacterId === activeCharacterId) {
      return;
    }
    const action = memoryActionInFlight.current;
    if (action && action.characterId !== activeCharacterId) {
      memoryActionInFlight.current = null;
      setMemoryActionId(null);
      setRememberingMessageId(null);
    }
    const journalAction = journalActionInFlight.current;
    if (journalAction && journalAction.characterId !== activeCharacterId) {
      journalActionInFlight.current = null;
      setJournalActionId(null);
    }
    const threadAction = threadActionInFlight.current;
    if (threadAction && threadAction.characterId !== activeCharacterId) {
      threadActionInFlight.current = null;
      setThreadActionId(null);
    }
    setMemories([]);
    setMemoryContent("");
    setMemoryPinned(false);
    setEditingMemoryId(null);
    setMemoryEditContent("");
    forgottenMemoriesCharacterIdRef.current = null;
    setForgottenMemories([]);
    setForgottenMemoriesCharacterId(null);
    setMemoryView("active");
    setMemoryViewCharacterId(activeCharacterId);
    setForgottenMemoriesLoading(false);
    setJournals([]);
    setJournalTitle("");
    setJournalSummary("");
    setEditingJournalId(null);
    setJournalEditTitle("");
    setJournalEditSummary("");
    setContinuityThreads([]);
    setThreadDraft("");
  }, [activeCharacterId]);

  useLayoutEffect(() => {
    activeConversationIdRef.current = activeConversationId;
    const action = memoryActionInFlight.current;
    if (
      action?.kind === "remember" &&
      action.conversationId !== activeConversationId
    ) {
      memoryActionInFlight.current = null;
      setRememberingMessageId(null);
    }
  }, [activeConversationId]);

  const currentForgottenMemories =
    forgottenMemoriesCharacterId === activeCharacterId ? forgottenMemories : [];
  const currentMemoryView = memoryViewCharacterId === activeCharacterId ? memoryView : "active";

  function requestStillApplies(characterId: string): boolean {
    return activeCharacterIdRef.current === characterId;
  }

  function beginMemoryAction(action: MemoryAction): boolean {
    if (memoryActionInFlight.current !== null) {
      return false;
    }
    memoryActionInFlight.current = action;
    if (action.kind === "remember") {
      setRememberingMessageId(action.key);
    } else {
      setMemoryActionId(action.key);
    }
    return true;
  }

  function memoryActionStillApplies(action: MemoryAction): boolean {
    return (
      memoryActionInFlight.current === action &&
      activeCharacterIdRef.current === action.characterId
    );
  }

  function memoryActionConversationStillApplies(action: MemoryAction): boolean {
    return (
      memoryActionStillApplies(action) &&
      activeConversationIdRef.current === action.conversationId
    );
  }

  function finishMemoryAction(action: MemoryAction) {
    if (memoryActionInFlight.current !== action) {
      return;
    }
    memoryActionInFlight.current = null;
    if (action.kind === "remember") {
      setRememberingMessageId(null);
    } else {
      setMemoryActionId(null);
    }
  }

  function beginJournalAction(action: JournalAction): boolean {
    if (journalActionInFlight.current !== null) {
      return false;
    }
    journalActionInFlight.current = action;
    setJournalActionId(action.key);
    return true;
  }

  function journalActionStillApplies(action: JournalAction): boolean {
    return (
      journalActionInFlight.current === action &&
      activeCharacterIdRef.current === action.characterId
    );
  }

  function finishJournalAction(action: JournalAction) {
    if (journalActionInFlight.current !== action) {
      return;
    }
    journalActionInFlight.current = null;
    setJournalActionId(null);
  }

  function beginThreadAction(action: ThreadAction): boolean {
    if (threadActionInFlight.current !== null) {
      return false;
    }
    threadActionInFlight.current = action;
    setThreadActionId(action.key);
    return true;
  }

  function threadActionStillApplies(action: ThreadAction): boolean {
    return (
      threadActionInFlight.current === action &&
      activeCharacterIdRef.current === action.characterId
    );
  }

  function finishThreadAction(action: ThreadAction) {
    if (threadActionInFlight.current !== action) {
      return;
    }
    threadActionInFlight.current = null;
    setThreadActionId(null);
  }

  async function recoverCanonicalThreads(
    authToken: string,
    action: ThreadAction
  ): Promise<ContinuityThread[] | null> {
    if (!threadActionStillApplies(action)) {
      return null;
    }
    const value = await apiJson<unknown>(
      `/characters/${action.characterId}/threads?status=all`,
      { token: authToken }
    );
    if (!isCompleteContinuityThreadList(value, action.characterId)) {
      throw new Error("The living threads returned in an unexpected shape.");
    }
    if (!threadActionStillApplies(action)) {
      return null;
    }
    setContinuityThreads(value);
    return value;
  }

  async function recoverCanonicalJournals(
    authToken: string,
    action: JournalAction
  ): Promise<Journal[] | null> {
    if (!journalActionStillApplies(action)) {
      return null;
    }
    const value = await apiJson<unknown>(
      `/characters/${action.characterId}/journals`,
      { token: authToken }
    );
    if (!isJournalArray(value, action.characterId)) {
      throw new Error("Your shared moments could not be opened safely.");
    }
    if (!journalActionStillApplies(action)) {
      return null;
    }
    setJournals(value);
    return value;
  }

  function setForgottenMemoriesForCharacter(
    characterId: string,
    update: (current: MemoryItem[]) => MemoryItem[]
  ) {
    setForgottenMemories((current) => {
      const owned =
        forgottenMemoriesCharacterIdRef.current === characterId ? current : [];
      return update(owned);
    });
    forgottenMemoriesCharacterIdRef.current = characterId;
    setForgottenMemoriesCharacterId(characterId);
  }

  function applyMemory(action: MemoryAction, memory: MemoryItem): boolean {
    if (!memoryActionStillApplies(action)) {
      return false;
    }
    if (memory.forgotten_at === null) {
      setMemories((current) => upsertMemory(current, memory));
      setForgottenMemoriesForCharacter(action.characterId, (current) =>
        current.filter((item) => item.id !== memory.id)
      );
    } else {
      setMemories((current) => current.filter((item) => item.id !== memory.id));
      setForgottenMemoriesForCharacter(action.characterId, (current) =>
        upsertMemory(current, memory)
      );
    }
    return true;
  }

  async function recoverCanonicalMemories(
    authToken: string,
    action: MemoryAction
  ): Promise<{ active: MemoryItem[]; forgotten: MemoryItem[] } | null> {
    if (!memoryActionStillApplies(action)) {
      return null;
    }
    const [activeValue, forgottenValue] = await Promise.all([
      apiJson<unknown>(`/characters/${action.characterId}/memories`, {
        token: authToken
      }),
      apiJson<unknown>(`/characters/${action.characterId}/memories?state=forgotten`, {
        token: authToken
      })
    ]);
    if (
      !isMemoryItemArray(activeValue, action.characterId, "active") ||
      !isMemoryItemArray(forgottenValue, action.characterId, "forgotten")
    ) {
      throw new Error("The backend returned an invalid memory list.");
    }
    if (!memoryActionStillApplies(action)) {
      return null;
    }
    setMemories(activeValue);
    forgottenMemoriesCharacterIdRef.current = action.characterId;
    setForgottenMemoriesCharacterId(action.characterId);
    setForgottenMemories(forgottenValue);
    return { active: activeValue, forgotten: forgottenValue };
  }

  async function changeMemoryView(view: MemoryView) {
    setMemoryView(view);
    setMemoryViewCharacterId(activeCharacterId);
    if (view !== "forgotten" || !token || !activeCharacterId) {
      return;
    }
    const requestCharacterId = activeCharacterId;
    const requestVersion = ++forgottenRequestVersionRef.current;
    setForgottenMemoriesLoading(true);
    setError(null);
    try {
      const forgottenValue = await apiJson<unknown>(
        `/characters/${requestCharacterId}/memories?state=forgotten`,
        { token }
      );
      if (!isMemoryItemArray(forgottenValue, requestCharacterId, "forgotten")) {
        throw new Error("The backend returned an invalid forgotten-memory list.");
      }
      if (
        requestVersion === forgottenRequestVersionRef.current &&
        requestStillApplies(requestCharacterId)
      ) {
        forgottenMemoriesCharacterIdRef.current = requestCharacterId;
        setForgottenMemoriesCharacterId(requestCharacterId);
        setForgottenMemories(forgottenValue);
      }
    } catch (caught) {
      if (requestStillApplies(requestCharacterId)) {
        setError(readError(caught));
      }
    } finally {
      if (requestVersion === forgottenRequestVersionRef.current) {
        setForgottenMemoriesLoading(false);
      }
    }
  }

  async function addMemory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = memoryContent.trim();
    if (
      !token ||
      !activeCharacterId ||
      !activeConversation ||
      !content ||
      memoryActionInFlight.current
    ) {
      return;
    }
    if (content.length > 1000) {
      setError("Keep memories to 1,000 characters or fewer.");
      return;
    }
    const authToken = token;
    const requestCharacterId = activeCharacterId;
    const action: MemoryAction = {
      kind: "add",
      key: "add",
      characterId: requestCharacterId,
      conversationId: activeConversation.id,
      targetId: null
    };
    if (!beginMemoryAction(action)) {
      return;
    }
    let persisted = false;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>(
        `/characters/${requestCharacterId}/memories`,
        {
          method: "POST",
          body: JSON.stringify({
            memory_type: memoryType,
            content,
            importance: parseDecimal(memoryImportance, 0.6),
            confidence: 0.8,
            pinned: memoryPinned
          }),
          token: authToken
        }
      );
      persisted = true;
      if (isMemoryItem(value, requestCharacterId, "active")) {
        applyMemory(action, value);
      } else {
        await recoverCanonicalMemories(authToken, action);
      }
      if (memoryActionStillApplies(action)) {
        setMemoryContent("");
        setMemoryPinned(false);
        setNotice("Memory saved.");
      }
    } catch (caught) {
      if (memoryActionStillApplies(action)) {
        setError(
          persisted
            ? "The memory was saved, but recall could not refresh. Reload Eidolon before changing memories again."
            : readError(caught)
        );
      }
    } finally {
      finishMemoryAction(action);
    }
  }

  async function saveMemoryEdit(memory: MemoryItem) {
    const content = memoryEditContent.trim();
    if (
      !token ||
      !activeCharacterId ||
      !activeConversation ||
      !content ||
      memoryActionInFlight.current
    ) {
      return;
    }
    if (content.length > 1000) {
      setError("Keep memories to 1,000 characters or fewer.");
      return;
    }
    const authToken = token;
    const requestCharacterId = activeCharacterId;
    const action: MemoryAction = {
      kind: "edit",
      key: memory.id,
      characterId: requestCharacterId,
      conversationId: activeConversation.id,
      targetId: memory.id
    };
    if (!beginMemoryAction(action)) {
      return;
    }
    let persisted = false;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>(
        `/characters/${requestCharacterId}/memories/${memory.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({ content }),
          token: authToken
        }
      );
      persisted = true;
      if (
        isMemoryItem(value, requestCharacterId, "active") &&
        value.id === memory.id
      ) {
        applyMemory(action, value);
      } else {
        const recovered = await recoverCanonicalMemories(authToken, action);
        if (
          recovered !== null &&
          !recovered.active.some((item) => item.id === memory.id)
        ) {
          throw new Error("The updated memory was missing from active recall.");
        }
      }
      if (memoryActionStillApplies(action)) {
        setEditingMemoryId(null);
        setMemoryEditContent("");
        setNotice("Memory updated.");
      }
    } catch (caught) {
      if (memoryActionStillApplies(action)) {
        setError(
          persisted
            ? "The memory was updated, but recall could not refresh. Reload Eidolon before changing memories again."
            : readError(caught)
        );
      }
    } finally {
      finishMemoryAction(action);
    }
  }

  async function toggleMemoryPinned(memory: MemoryItem) {
    if (
      !token ||
      !activeCharacterId ||
      !activeConversation ||
      memoryActionInFlight.current
    ) {
      return;
    }
    const authToken = token;
    const requestCharacterId = activeCharacterId;
    const pinned = !memory.pinned;
    const action: MemoryAction = {
      kind: "pin",
      key: memory.id,
      characterId: requestCharacterId,
      conversationId: activeConversation.id,
      targetId: memory.id
    };
    if (!beginMemoryAction(action)) {
      return;
    }
    let persisted = false;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>(
        `/characters/${requestCharacterId}/memories/${memory.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({ pinned }),
          token: authToken
        }
      );
      persisted = true;
      if (
        isMemoryItem(value, requestCharacterId, "active") &&
        value.id === memory.id &&
        value.pinned === pinned
      ) {
        applyMemory(action, value);
      } else {
        const recovered = await recoverCanonicalMemories(authToken, action);
        if (
          recovered !== null &&
          !recovered.active.some(
            (item) => item.id === memory.id && item.pinned === pinned
          )
        ) {
          throw new Error("The pin change was missing from active recall.");
        }
      }
      if (memoryActionStillApplies(action)) {
        setNotice(pinned ? "Memory pinned." : "Memory unpinned.");
      }
    } catch (caught) {
      if (memoryActionStillApplies(action)) {
        setError(
          persisted
            ? "The memory changed, but recall could not refresh. Reload Eidolon before changing memories again."
            : readError(caught)
        );
      }
    } finally {
      finishMemoryAction(action);
    }
  }

  async function deleteMemory(memory: MemoryItem) {
    if (!token || !activeCharacterId || memoryActionInFlight.current) {
      return;
    }
    const authToken = token;
    const requestCharacterId = activeCharacterId;
    const action: MemoryAction = {
      kind: "delete",
      key: memory.id,
      characterId: requestCharacterId,
      conversationId: activeConversation?.id ?? null,
      targetId: memory.id
    };
    if (!beginMemoryAction(action)) {
      return;
    }
    let persisted = false;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>(
        `/characters/${requestCharacterId}/memories/${memory.id}`,
        { method: "DELETE", token: authToken }
      );
      persisted = true;
      if (isDeleteCountResponse(value) && value.deleted >= 1) {
        if (!memoryActionStillApplies(action)) {
          return;
        }
        setMemories((current) => current.filter((item) => item.id !== memory.id));
        setForgottenMemoriesForCharacter(requestCharacterId, (current) =>
          current.filter((item) => item.id !== memory.id)
        );
      } else {
        const recovered = await recoverCanonicalMemories(authToken, action);
        if (
          recovered !== null &&
          [...recovered.active, ...recovered.forgotten].some(
            (item) => item.id === memory.id
          )
        ) {
          throw new Error("The deleted memory was still present in recall.");
        }
      }
      if (memoryActionStillApplies(action)) {
        setNotice("Memory permanently deleted.");
      }
    } catch (caught) {
      if (memoryActionStillApplies(action)) {
        setError(
          persisted
            ? "The memory was deleted, but recall could not refresh. Reload Eidolon before changing memories again."
            : readError(caught)
        );
      }
    } finally {
      finishMemoryAction(action);
    }
  }

  async function forgetMemory(memory: MemoryItem) {
    if (!token || !activeCharacterId || memoryActionInFlight.current) {
      return;
    }
    const authToken = token;
    const requestCharacterId = activeCharacterId;
    const action: MemoryAction = {
      kind: "forget",
      key: memory.id,
      characterId: requestCharacterId,
      conversationId: activeConversation?.id ?? null,
      targetId: memory.id
    };
    if (!beginMemoryAction(action)) {
      return;
    }
    let persisted = false;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>(
        `/characters/${requestCharacterId}/memories/${memory.id}/forget`,
        { method: "POST", token: authToken }
      );
      persisted = true;
      if (
        isMemoryItem(value, requestCharacterId, "forgotten") &&
        value.id === memory.id
      ) {
        applyMemory(action, value);
      } else {
        const recovered = await recoverCanonicalMemories(authToken, action);
        if (
          recovered !== null &&
          (!recovered.forgotten.some((item) => item.id === memory.id) ||
            recovered.active.some((item) => item.id === memory.id))
        ) {
          throw new Error("The memory may have faded, but the change could not be confirmed.");
        }
      }
      if (memoryActionStillApplies(action)) {
        setNotice("Memory moved out of active recall.");
      }
    } catch (caught) {
      if (memoryActionStillApplies(action)) {
        setError(
          persisted
            ? "The memory left active recall, but the memory lists could not refresh. Reload Eidolon before changing memories again."
            : readError(caught)
        );
      }
    } finally {
      finishMemoryAction(action);
    }
  }

  async function restoreMemory(memory: MemoryItem) {
    if (!token || !activeCharacterId || memoryActionInFlight.current) {
      return;
    }
    const authToken = token;
    const requestCharacterId = activeCharacterId;
    const action: MemoryAction = {
      kind: "restore",
      key: memory.id,
      characterId: requestCharacterId,
      conversationId: activeConversation?.id ?? null,
      targetId: memory.id
    };
    if (!beginMemoryAction(action)) {
      return;
    }
    let persisted = false;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>(
        `/characters/${requestCharacterId}/memories/${memory.id}/restore`,
        { method: "POST", token: authToken }
      );
      persisted = true;
      if (
        isMemoryItem(value, requestCharacterId, "active") &&
        value.id === memory.id
      ) {
        applyMemory(action, value);
      } else {
        const recovered = await recoverCanonicalMemories(authToken, action);
        if (
          recovered !== null &&
          (!recovered.active.some((item) => item.id === memory.id) ||
            recovered.forgotten.some((item) => item.id === memory.id))
        ) {
          throw new Error("The memory may have returned, but the change could not be confirmed.");
        }
      }
      if (memoryActionStillApplies(action)) {
        setNotice("Memory restored to active recall.");
      }
    } catch (caught) {
      if (memoryActionStillApplies(action)) {
        setError(
          persisted
            ? "The memory was restored, but the memory lists could not refresh. Reload Eidolon before changing memories again."
            : readError(caught)
        );
      }
    } finally {
      finishMemoryAction(action);
    }
  }

  async function resolveMemoryConflict(memory: MemoryItem) {
    if (
      !token ||
      !activeCharacterId ||
      !activeConversation ||
      memoryActionInFlight.current
    ) {
      return;
    }
    const authToken = token;
    const requestCharacterId = activeCharacterId;
    const requestConversationId = activeConversation.id;
    const action: MemoryAction = {
      kind: "resolve",
      key: memory.id,
      characterId: requestCharacterId,
      conversationId: requestConversationId,
      targetId: memory.id
    };
    if (!beginMemoryAction(action)) {
      return;
    }
    let persisted = false;
    let removed: number | null = null;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>(
        `/characters/${requestCharacterId}/memories/${memory.id}/resolve`,
        {
          method: "POST",
          token: authToken
        }
      );
      persisted = true;
      if (
        isMemoryResolveResult(value, requestCharacterId) &&
        value.memory.id === memory.id
      ) {
        removed = value.removed;
        const removedIds = new Set(value.removed_memory_ids);
        if (!memoryActionStillApplies(action)) {
          return;
        }
        setMemories((current) =>
          current
            .filter((item) => item.id !== value.memory.id && !removedIds.has(item.id))
            .concat(value.memory)
        );
        setForgottenMemoriesForCharacter(requestCharacterId, (current) =>
          current.filter(
            (item) => item.id !== value.memory.id && !removedIds.has(item.id)
          )
        );
      } else {
        const recovered = await recoverCanonicalMemories(authToken, action);
        if (
          recovered !== null &&
          !recovered.active.some((item) => item.id === memory.id)
        ) {
          throw new Error("The resolved memory was missing from active recall.");
        }
      }
      if (memoryActionConversationStillApplies(action)) {
        await refreshSideState(
          authToken,
          requestCharacterId,
          requestConversationId,
          () => memoryActionConversationStillApplies(action)
        );
      }
      if (memoryActionStillApplies(action)) {
        setNotice(
          removed === null
            ? "Memory conflict resolved and recall refreshed."
            : removed === 1
            ? "Memory conflict resolved. Eidolon will keep this version."
            : `Memory conflict resolved. ${removed} older versions were removed.`
        );
      }
    } catch (caught) {
      if (memoryActionStillApplies(action)) {
        setError(
          persisted
            ? "The memory conflict was resolved, but recall could not refresh. Reload Eidolon before changing memories again."
            : readError(caught)
        );
      }
    } finally {
      finishMemoryAction(action);
    }
  }

  async function rememberMessage(message: Message) {
    if (
      !token ||
      !activeCharacterId ||
      !activeConversation ||
      message.conversation_id !== activeConversation.id ||
      memoryActionInFlight.current
    ) {
      return;
    }
    const authToken = token;
    const requestCharacterId = activeCharacterId;
    const requestConversationId = activeConversation.id;
    const action: MemoryAction = {
      kind: "remember",
      key: message.id,
      characterId: requestCharacterId,
      conversationId: requestConversationId,
      targetId: message.id
    };
    if (!beginMemoryAction(action)) {
      return;
    }
    let persisted = false;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>(
        `/conversations/${requestConversationId}/messages/${message.id}/remember`,
        {
          method: "POST",
          token: authToken
        }
      );
      persisted = true;
      if (
        isMemoryItem(value, requestCharacterId, "active") &&
        memoryReferencesMessage(value, message.id)
      ) {
        applyMemory(action, value);
      } else {
        const recovered = await recoverCanonicalMemories(authToken, action);
        if (
          recovered !== null &&
          !recovered.active.some((item) => memoryReferencesMessage(item, message.id))
        ) {
          throw new Error("The saved message memory was missing from active recall.");
        }
      }
      if (memoryActionConversationStillApplies(action)) {
        setNotice("That line is now kept in memory.");
      }
    } catch (caught) {
      if (memoryActionConversationStillApplies(action)) {
        setError(
          persisted
            ? "That line was saved, but memory could not refresh. Reload Eidolon before remembering another message."
            : readError(caught)
        );
      }
    } finally {
      finishMemoryAction(action);
    }
  }

  async function clearMemories(): Promise<boolean> {
    if (
      !token ||
      !activeCharacterId ||
      !activeConversation ||
      memoryActionInFlight.current
    ) {
      return false;
    }
    const authToken = token;
    const requestCharacterId = activeCharacterId;
    const requestConversationId = activeConversation.id;
    const action: MemoryAction = {
      kind: "clear",
      key: "clear",
      characterId: requestCharacterId,
      conversationId: requestConversationId,
      targetId: null
    };
    if (!beginMemoryAction(action)) {
      return false;
    }
    let persisted = false;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>(
        `/characters/${requestCharacterId}/memories`,
        { method: "DELETE", token: authToken }
      );
      persisted = true;
      if (memoryActionStillApplies(action)) {
        setMemories([]);
        forgottenMemoriesCharacterIdRef.current = requestCharacterId;
        setForgottenMemoriesCharacterId(requestCharacterId);
        setForgottenMemories([]);
      }
      if (memoryActionConversationStillApplies(action)) {
        await refreshSideState(
          authToken,
          requestCharacterId,
          requestConversationId,
          () => memoryActionConversationStillApplies(action)
        );
      }
      if (memoryActionStillApplies(action)) {
        setNotice(
          isDeleteCountResponse(value)
            ? `${value.deleted} ${value.deleted === 1 ? "memory" : "memories"} cleared.`
            : "Memories cleared."
        );
      }
      return true;
    } catch (caught) {
      if (memoryActionStillApplies(action)) {
        setError(
          persisted
            ? "Memories were cleared, but recall could not refresh. Reload Eidolon before continuing this conversation."
            : readError(caught)
        );
      }
      return persisted;
    } finally {
      finishMemoryAction(action);
    }
  }

  async function clearMemoryCategory(category: MemoryCategory): Promise<boolean> {
    if (!token || !activeCharacterId || !activeConversation || memoryActionInFlight.current) {
      return false;
    }
    const authToken = token;
    const requestCharacterId = activeCharacterId;
    const requestConversationId = activeConversation.id;
    const action: MemoryAction = {
      kind: "clear-category",
      key: `clear-${category}`,
      characterId: requestCharacterId,
      conversationId: requestConversationId,
      targetId: null
    };
    if (!beginMemoryAction(action)) {
      return false;
    }
    let persisted = false;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>(
        `/characters/${requestCharacterId}/memories/category/${category}`,
        { method: "DELETE", token: authToken }
      );
      persisted = true;
      if (memoryActionStillApplies(action)) {
        setMemories((current) =>
          current.filter((memory) => memoryArchiveCategory(memory) !== category)
        );
        setForgottenMemories((current) =>
          current.filter((memory) => memoryArchiveCategory(memory) !== category)
        );
      }
      if (memoryActionConversationStillApplies(action)) {
        await refreshSideState(
          authToken,
          requestCharacterId,
          requestConversationId,
          () => memoryActionConversationStillApplies(action)
        );
      }
      if (memoryActionStillApplies(action)) {
        const count = isDeleteCountResponse(value) ? value.deleted : 0;
        setNotice(
          count > 0
            ? `${count} ${count === 1 ? "memory" : "memories"} removed from that category.`
            : "That category was already empty."
        );
      }
      return true;
    } catch (caught) {
      if (memoryActionStillApplies(action)) {
        setError(
          persisted
            ? "The category was cleared, but recall could not refresh. Reload Eidolon before continuing."
            : readError(caught)
        );
      }
      return persisted;
    } finally {
      finishMemoryAction(action);
    }
  }

  async function clearAdultContinuity(): Promise<boolean> {
    if (
      !token ||
      !activeCharacterId ||
      !activeConversation ||
      memoryActionInFlight.current
    ) {
      return false;
    }
    const action: MemoryAction = {
      kind: "clear-adult",
      key: "clear-adult",
      characterId: activeCharacterId,
      conversationId: activeConversation.id,
      targetId: null
    };
    if (!beginMemoryAction(action)) {
      return false;
    }
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>(
        `/characters/${action.characterId}/adult-continuity`,
        { method: "DELETE", token }
      );
      if (memoryActionConversationStillApplies(action)) {
        await refreshSideState(token, action.characterId, action.conversationId!, () =>
          memoryActionConversationStillApplies(action)
        );
      }
      if (memoryActionStillApplies(action)) {
        setNotice(
          isDeleteCountResponse(value)
            ? `${value.deleted} intimate ${value.deleted === 1 ? "memory or moment" : "memories and moments"} removed.`
            : "Intimate memories and moments removed."
        );
      }
      return true;
    } catch (caught) {
      if (memoryActionStillApplies(action)) {
        setError(readError(caught));
      }
      return false;
    } finally {
      finishMemoryAction(action);
    }
  }

  async function forgetMemories() {
    if (
      !token ||
      !activeCharacterId ||
      !activeConversation ||
      memoryActionInFlight.current
    ) {
      return;
    }
    const authToken = token;
    const requestCharacterId = activeCharacterId;
    const action: MemoryAction = {
      kind: "forget-stale",
      key: "forget-stale",
      characterId: requestCharacterId,
      conversationId: activeConversation.id,
      targetId: null
    };
    if (!beginMemoryAction(action)) {
      return;
    }
    let persisted = false;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>(
        `/characters/${requestCharacterId}/memories/forget`,
        { method: "POST", token: authToken }
      );
      persisted = true;
      if (!memoryActionStillApplies(action)) {
        return;
      }
      await recoverCanonicalMemories(authToken, action);
      if (memoryActionStillApplies(action)) {
        setNotice(
          !isForgetCountResponse(value)
            ? "Memory fading review completed."
            : value.forgotten === 0
            ? "No unpinned memories are ready to fade."
            : `${value.forgotten} low-value ${value.forgotten === 1 ? "memory" : "memories"} moved out of active recall.`
        );
      }
    } catch (caught) {
      if (memoryActionStillApplies(action)) {
        setError(
          persisted
            ? "Memory fading completed, but the memory lists could not refresh. Reload Eidolon before changing memories again."
            : readError(caught)
        );
      }
    } finally {
      finishMemoryAction(action);
    }
  }

  async function addJournal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = normalizeJournalText(journalTitle);
    const summary = normalizeJournalText(journalSummary);
    if (
      !token ||
      !activeCharacterId ||
      !title ||
      !summary ||
      journalActionInFlight.current
    ) {
      return;
    }
    if (title.length > 200 || summary.length > 2000) {
      setError("Keep reflection titles to 200 characters and notes to 2,000 characters or fewer.");
      return;
    }
    const authToken = token;
    const requestCharacterId = activeCharacterId;
    const requestConversationId = activeConversation?.id ?? null;
    const action: JournalAction = {
      kind: "add",
      key: "add",
      characterId: requestCharacterId,
      conversationId: requestConversationId,
      targetId: null,
      title,
      summary,
      knownIds: new Set(journals.map((journal) => journal.id))
    };
    if (!beginJournalAction(action)) {
      return;
    }
    let persisted = false;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>(
        `/characters/${requestCharacterId}/journals`,
        {
          method: "POST",
          body: JSON.stringify({
            conversation_id: requestConversationId,
            title,
            summary,
            journal_type: "manual_note",
            importance: 0.6
          }),
          token: authToken
        }
      );
      persisted = true;
      if (isJournalForAction(value, action) && !action.knownIds.has(value.id)) {
        if (journalActionStillApplies(action)) {
          setJournals((current) => upsertJournal(current, value));
        }
      } else {
        const recovered = await recoverCanonicalJournals(authToken, action);
        if (
          recovered !== null &&
          !recovered.some(
            (journal) =>
              !action.knownIds.has(journal.id) && isJournalForAction(journal, action)
          )
        ) {
          throw new Error("The saved reflection could not be found again.");
        }
      }
      if (journalActionStillApplies(action)) {
        setJournalTitle("");
        setJournalSummary("");
        setNotice("Your reflection was saved.");
      }
    } catch (caught) {
      if (journalActionStillApplies(action)) {
        setError(
          persisted
            ? "The reflection was saved, but the change could not be confirmed. Reload Eidolon before changing it again."
            : readError(caught)
        );
      }
    } finally {
      finishJournalAction(action);
    }
  }

  function startJournalEdit(journal: Journal) {
    if (
      journalActionInFlight.current ||
      journal.character_id !== activeCharacterId ||
      journal.metadata_json.source !== "manual"
    ) {
      return;
    }
    setEditingJournalId(journal.id);
    setJournalEditTitle(journal.title);
    setJournalEditSummary(journal.summary);
  }

  function cancelJournalEdit() {
    if (journalActionInFlight.current) {
      return;
    }
    setEditingJournalId(null);
    setJournalEditTitle("");
    setJournalEditSummary("");
  }

  async function saveJournalEdit(journal: Journal) {
    const title = normalizeJournalText(journalEditTitle);
    const summary = normalizeJournalText(journalEditSummary);
    if (
      !token ||
      !activeCharacterId ||
      journal.character_id !== activeCharacterId ||
      journal.metadata_json.source !== "manual" ||
      !title ||
      !summary ||
      journalActionInFlight.current
    ) {
      return;
    }
    if (title.length > 200 || summary.length > 2000) {
      setError("Keep reflection titles to 200 characters and notes to 2,000 characters or fewer.");
      return;
    }
    const authToken = token;
    const requestCharacterId = activeCharacterId;
    const action: JournalAction = {
      kind: "edit",
      key: `save:${journal.id}`,
      characterId: requestCharacterId,
      conversationId: journal.conversation_id,
      targetId: journal.id,
      title,
      summary,
      knownIds: new Set(journals.map((item) => item.id))
    };
    if (!beginJournalAction(action)) {
      return;
    }
    let persisted = false;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>(
        `/characters/${requestCharacterId}/journals/${journal.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({ title, summary }),
          token: authToken
        }
      );
      persisted = true;
      if (isJournalForAction(value, action)) {
        if (journalActionStillApplies(action)) {
          setJournals((current) => upsertJournal(current, value));
        }
      } else {
        const recovered = await recoverCanonicalJournals(authToken, action);
        if (
          recovered !== null &&
          !recovered.some((item) => isJournalForAction(item, action))
        ) {
          throw new Error("The updated reflection could not be found again.");
        }
      }
      if (journalActionStillApplies(action)) {
        setEditingJournalId(null);
        setJournalEditTitle("");
        setJournalEditSummary("");
        setNotice("Your reflection was updated.");
      }
    } catch (caught) {
      if (journalActionStillApplies(action)) {
        setError(
          persisted
            ? "The reflection was updated, but the change could not be confirmed. Reload Eidolon before changing it again."
            : readError(caught)
        );
      }
    } finally {
      finishJournalAction(action);
    }
  }

  async function deleteJournal(journal: Journal) {
    if (
      !token ||
      !activeCharacterId ||
      journal.character_id !== activeCharacterId ||
      journal.metadata_json.source !== "manual" ||
      journalActionInFlight.current
    ) {
      return;
    }
    const authToken = token;
    const requestCharacterId = activeCharacterId;
    const action: JournalAction = {
      kind: "delete",
      key: `delete:${journal.id}`,
      characterId: requestCharacterId,
      conversationId: journal.conversation_id,
      targetId: journal.id,
      title: null,
      summary: null,
      knownIds: new Set(journals.map((item) => item.id))
    };
    if (!beginJournalAction(action)) {
      return;
    }
    let persisted = false;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>(
        `/characters/${requestCharacterId}/journals/${journal.id}`,
        { method: "DELETE", token: authToken }
      );
      persisted = true;
      if (isDeleteCountResponse(value) && value.deleted >= 1) {
        if (!journalActionStillApplies(action)) {
          return;
        }
        setJournals((current) => current.filter((item) => item.id !== journal.id));
      } else {
        const recovered = await recoverCanonicalJournals(authToken, action);
        if (recovered !== null && recovered.some((item) => item.id === journal.id)) {
          throw new Error("The reflection could not be confirmed as deleted.");
        }
      }
      if (journalActionStillApplies(action)) {
        if (editingJournalId === journal.id) {
          setEditingJournalId(null);
          setJournalEditTitle("");
          setJournalEditSummary("");
        }
        setNotice("Your reflection was deleted.");
      }
    } catch (caught) {
      if (journalActionStillApplies(action)) {
        setError(
          persisted
            ? "The reflection was deleted, but the change could not be confirmed. Reload Eidolon before changing another."
            : readError(caught)
        );
      }
    } finally {
      finishJournalAction(action);
    }
  }

  async function addContinuityThread(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = threadDraft.trim().replace(/\s+/g, " ");
    if (
      !token ||
      !activeCharacterId ||
      !content ||
      threadActionInFlight.current
    ) {
      return;
    }
    if (content.length > 600) {
      setError("Keep living threads to 600 characters or fewer.");
      return;
    }
    const authToken = token;
    const requestCharacterId = activeCharacterId;
    const requestConversationId = activeConversation?.id ?? null;
    const action: ThreadAction = {
      kind: "add",
      key: "thread:add",
      characterId: requestCharacterId,
      conversationId: requestConversationId,
      targetId: null
    };
    if (!beginThreadAction(action)) {
      return;
    }
    let persisted = false;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>(
        `/characters/${requestCharacterId}/threads`,
        {
          method: "POST",
          body: JSON.stringify({
            conversation_id: requestConversationId,
            thread_kind: "follow_up",
            content,
            salience: 0.75
          }),
          token: authToken
        }
      );
      persisted = true;
      if (isCompleteContinuityThread(value, requestCharacterId)) {
        if (threadActionStillApplies(action)) {
          setContinuityThreads((current) => upsertContinuityThread(current, value));
        }
      } else {
        const recovered = await recoverCanonicalThreads(authToken, action);
        if (recovered !== null && !recovered.some((thread) => thread.content === content)) {
          throw new Error("The new living thread could not be found again.");
        }
      }
      if (threadActionStillApplies(action)) {
        setThreadDraft("");
        setNotice("That thread will stay in view until you close it.");
      }
    } catch (caught) {
      if (threadActionStillApplies(action)) {
        setError(
          persisted
            ? "The thread was kept, but continuity could not refresh. Reload Eidolon before changing it again."
            : readError(caught)
        );
      }
    } finally {
      finishThreadAction(action);
    }
  }

  async function setContinuityThreadStatus(
    thread: ContinuityThread,
    status: "open" | "resolved"
  ) {
    if (
      !token ||
      !activeCharacterId ||
      thread.character_id !== activeCharacterId ||
      threadActionInFlight.current
    ) {
      return;
    }
    const authToken = token;
    const requestCharacterId = activeCharacterId;
    const action: ThreadAction = {
      kind: status === "resolved" ? "resolve" : "reopen",
      key: `thread:${status}:${thread.id}`,
      characterId: requestCharacterId,
      conversationId: thread.conversation_id,
      targetId: thread.id
    };
    if (!beginThreadAction(action)) {
      return;
    }
    let persisted = false;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>(
        `/characters/${requestCharacterId}/threads/${thread.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({ status }),
          token: authToken
        }
      );
      persisted = true;
      if (
        isCompleteContinuityThread(value, requestCharacterId) &&
        value.id === thread.id &&
        value.status === status
      ) {
        if (threadActionStillApplies(action)) {
          setContinuityThreads((current) => upsertContinuityThread(current, value));
        }
      } else {
        const recovered = await recoverCanonicalThreads(authToken, action);
        if (
          recovered !== null &&
          !recovered.some((item) => item.id === thread.id && item.status === status)
        ) {
          throw new Error("The living thread status could not be confirmed.");
        }
      }
      if (threadActionStillApplies(action)) {
        setNotice(
          status === "resolved"
            ? "That loop is now part of your settled history."
            : "That thread is open again."
        );
      }
    } catch (caught) {
      if (threadActionStillApplies(action)) {
        setError(
          persisted
            ? "The thread changed, but continuity could not refresh. Reload Eidolon before changing it again."
            : readError(caught)
        );
      }
    } finally {
      finishThreadAction(action);
    }
  }

  async function deleteContinuityThread(thread: ContinuityThread) {
    if (
      !token ||
      !activeCharacterId ||
      thread.character_id !== activeCharacterId ||
      threadActionInFlight.current
    ) {
      return;
    }
    const authToken = token;
    const requestCharacterId = activeCharacterId;
    const action: ThreadAction = {
      kind: "delete",
      key: `thread:delete:${thread.id}`,
      characterId: requestCharacterId,
      conversationId: thread.conversation_id,
      targetId: thread.id
    };
    if (!beginThreadAction(action)) {
      return;
    }
    let persisted = false;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>(
        `/characters/${requestCharacterId}/threads/${thread.id}`,
        { method: "DELETE", token: authToken }
      );
      persisted = true;
      if (isDeleteCountResponse(value) && value.deleted >= 1) {
        if (threadActionStillApplies(action)) {
          setContinuityThreads((current) =>
            current.filter((item) => item.id !== thread.id)
          );
        }
      } else {
        const recovered = await recoverCanonicalThreads(authToken, action);
        if (recovered !== null && recovered.some((item) => item.id === thread.id)) {
          throw new Error("The living thread could not be confirmed as deleted.");
        }
      }
      if (threadActionStillApplies(action)) {
        setNotice("That thread was permanently released.");
      }
    } catch (caught) {
      if (threadActionStillApplies(action)) {
        setError(
          persisted
            ? "The thread was released, but continuity could not refresh. Reload Eidolon before changing another."
            : readError(caught)
        );
      }
    } finally {
      finishThreadAction(action);
    }
  }

  function resetKnowledge() {
    memoryActionInFlight.current = null;
    journalActionInFlight.current = null;
    threadActionInFlight.current = null;
    setMemories([]);
    setMemoryContent("");
    setMemoryPinned(false);
    setEditingMemoryId(null);
    setMemoryEditContent("");
    setRememberingMessageId(null);
    forgottenRequestVersionRef.current += 1;
    forgottenMemoriesCharacterIdRef.current = null;
    setForgottenMemories([]);
    setForgottenMemoriesCharacterId(null);
    setMemoryView("active");
    setMemoryViewCharacterId(null);
    setMemoryActionId(null);
    setForgottenMemoriesLoading(false);
    setJournals([]);
    setJournalTitle("");
    setJournalSummary("");
    setEditingJournalId(null);
    setJournalEditTitle("");
    setJournalEditSummary("");
    setJournalActionId(null);
    setContinuityThreads([]);
    setThreadDraft("");
    setThreadActionId(null);
  }

  return {
    state: {
      memories,
      memoryContent,
      memoryType,
      memoryImportance,
      memoryPinned,
      editingMemoryId,
      memoryEditContent,
      rememberingMessageId,
      forgottenMemories: currentForgottenMemories,
      memoryView: currentMemoryView,
      memoryActionId,
      memoryMutating: memoryActionId !== null || rememberingMessageId !== null,
      forgottenMemoriesLoading:
        memoryViewCharacterId === activeCharacterId && forgottenMemoriesLoading,
      journals,
      journalTitle,
      journalSummary,
      editingJournalId,
      journalEditTitle,
      journalEditSummary,
      journalActionId,
      journalMutating: journalActionId !== null,
      continuityThreads,
      threadDraft,
      threadActionId,
      threadMutating: threadActionId !== null
    },
    actions: {
      setMemories,
      setMemoryContent,
      setMemoryType,
      setMemoryImportance,
      setMemoryPinned,
      setEditingMemoryId,
      setMemoryEditContent,
      changeMemoryView,
      setJournals,
      setContinuityThreads,
      setJournalTitle,
      setJournalSummary,
      setJournalEditTitle,
      setJournalEditSummary,
      setThreadDraft,
      addMemory,
      saveMemoryEdit,
      toggleMemoryPinned,
      deleteMemory,
      forgetMemory,
      restoreMemory,
      resolveMemoryConflict,
      rememberMessage,
      clearMemories,
      clearMemoryCategory,
      clearAdultContinuity,
      forgetMemories,
      addJournal,
      startJournalEdit,
      cancelJournalEdit,
      saveJournalEdit,
      deleteJournal,
      addContinuityThread,
      resolveContinuityThread: (thread: ContinuityThread) =>
        setContinuityThreadStatus(thread, "resolved"),
      reopenContinuityThread: (thread: ContinuityThread) =>
        setContinuityThreadStatus(thread, "open"),
      deleteContinuityThread,
      resetKnowledge
    }
  };
}

function upsertMemory(memories: MemoryItem[], memory: MemoryItem): MemoryItem[] {
  const existingIndex = memories.findIndex((item) => item.id === memory.id);
  if (existingIndex < 0) {
    return [memory, ...memories];
  }
  return memories.map((item) => (item.id === memory.id ? memory : item));
}

function upsertJournal(journals: Journal[], journal: Journal): Journal[] {
  const existingIndex = journals.findIndex((item) => item.id === journal.id);
  if (existingIndex < 0) {
    return [journal, ...journals];
  }
  return journals.map((item) => (item.id === journal.id ? journal : item));
}

function upsertContinuityThread(
  threads: ContinuityThread[],
  thread: ContinuityThread
): ContinuityThread[] {
  if (!threads.some((item) => item.id === thread.id)) {
    return [thread, ...threads];
  }
  return threads.map((item) => (item.id === thread.id ? thread : item));
}

function isJournalForAction(value: unknown, action: JournalAction): value is Journal {
  if (!isJournal(value, action.characterId) || value.metadata_json.source !== "manual") {
    return false;
  }
  if (action.kind === "add") {
    return (
      value.conversation_id === action.conversationId &&
      value.title === action.title &&
      value.summary === action.summary
    );
  }
  if (action.kind === "edit") {
    return (
      value.id === action.targetId &&
      value.conversation_id === action.conversationId &&
      value.title === action.title &&
      value.summary === action.summary
    );
  }
  return false;
}

function normalizeJournalText(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

function isMemoryResolveResult(
  value: unknown,
  characterId: string
): value is MemoryResolveResult {
  if (!isRecord(value) || !isMemoryItem(value.memory, characterId, "active")) {
    return false;
  }
  if (
    typeof value.removed !== "number" ||
    !Number.isInteger(value.removed) ||
    value.removed < 0 ||
    !Array.isArray(value.removed_memory_ids) ||
    !value.removed_memory_ids.every(isNonemptyString)
  ) {
    return false;
  }
  const uniqueIds = new Set(value.removed_memory_ids);
  return (
    uniqueIds.size === value.removed_memory_ids.length &&
    value.removed === value.removed_memory_ids.length &&
    !uniqueIds.has(value.memory.id)
  );
}

function isDeleteCountResponse(value: unknown): value is { deleted: number } {
  return (
    isRecord(value) &&
    typeof value.deleted === "number" &&
    Number.isInteger(value.deleted) &&
    value.deleted >= 0
  );
}

function isForgetCountResponse(value: unknown): value is { forgotten: number } {
  return (
    isRecord(value) &&
    typeof value.forgotten === "number" &&
    Number.isInteger(value.forgotten) &&
    value.forgotten >= 0
  );
}

function memoryReferencesMessage(memory: MemoryItem, messageId: string): boolean {
  if (memory.source_message_id === messageId) {
    return true;
  }
  const sourceIds = memory.metadata_json.source_message_ids;
  return Array.isArray(sourceIds) && sourceIds.includes(messageId);
}

function memoryArchiveCategory(memory: MemoryItem): MemoryCategory {
  if (memory.memory_type === "person") return "people";
  if (memory.memory_type === "inside_joke") return "inside_jokes";
  if (["event", "shared_moment", "date", "place", "shared_lore"].includes(memory.memory_type)) {
    return "moments";
  }
  if (["boundary", "promise"].includes(memory.memory_type)) return "promises";
  return "patterns";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonemptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}
