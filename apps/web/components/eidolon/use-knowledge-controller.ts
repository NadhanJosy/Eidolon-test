"use client";

import { FormEvent, useState } from "react";

import { apiJson } from "@/lib/api";

import { readError } from "./controller-utils";
import type { Conversation, Journal, MemoryItem } from "./types";
import { parseDecimal } from "./ui";

type UseKnowledgeControllerArgs = {
  token: string | null;
  activeCharacterId: string | null;
  activeConversation: Conversation | null;
  setError: (value: string | null) => void;
  setNotice: (value: string | null) => void;
  refreshSideState: (
    authToken: string,
    characterId: string,
    conversationId: string
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

  const [journals, setJournals] = useState<Journal[]>([]);
  const [journalTitle, setJournalTitle] = useState("");
  const [journalSummary, setJournalSummary] = useState("");

  async function addMemory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !activeCharacterId || !activeConversation || !memoryContent.trim()) {
      return;
    }
    setError(null);
    await apiJson<MemoryItem>(`/characters/${activeCharacterId}/memories`, {
      method: "POST",
      body: JSON.stringify({
        memory_type: memoryType,
        content: memoryContent.trim(),
        importance: parseDecimal(memoryImportance, 0.6),
        confidence: 0.8,
        pinned: memoryPinned
      }),
      token
    });
    setMemoryContent("");
    setMemoryPinned(false);
    await refreshSideState(token, activeCharacterId, activeConversation.id);
  }

  async function saveMemoryEdit(memory: MemoryItem) {
    if (!token || !activeCharacterId || !activeConversation || !memoryEditContent.trim()) {
      return;
    }
    const updated = await apiJson<MemoryItem>(
      `/characters/${activeCharacterId}/memories/${memory.id}`,
      {
        method: "PATCH",
        body: JSON.stringify({ content: memoryEditContent.trim() }),
        token
      }
    );
    setMemories((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    setEditingMemoryId(null);
    setMemoryEditContent("");
  }

  async function toggleMemoryPinned(memory: MemoryItem) {
    if (!token || !activeCharacterId || !activeConversation) {
      return;
    }
    const updated = await apiJson<MemoryItem>(
      `/characters/${activeCharacterId}/memories/${memory.id}`,
      {
        method: "PATCH",
        body: JSON.stringify({ pinned: !memory.pinned }),
        token
      }
    );
    setMemories((current) => current.map((item) => (item.id === updated.id ? updated : item)));
  }

  async function deleteMemory(memory: MemoryItem) {
    if (!token || !activeCharacterId) {
      return;
    }
    await apiJson<{ deleted: number }>(`/characters/${activeCharacterId}/memories/${memory.id}`, {
      method: "DELETE",
      token
    });
    setMemories((current) => current.filter((item) => item.id !== memory.id));
  }

  async function clearMemories() {
    if (!token || !activeCharacterId || !activeConversation) {
      return;
    }
    const response = await apiJson<{ deleted: number }>(`/characters/${activeCharacterId}/memories`, {
      method: "DELETE",
      token
    });
    setMemories([]);
    setNotice(`${response.deleted} memories cleared.`);
    await refreshSideState(token, activeCharacterId, activeConversation.id);
  }

  async function forgetMemories() {
    if (!token || !activeCharacterId || !activeConversation) {
      return;
    }
    const response = await apiJson<{ forgotten: number }>(
      `/characters/${activeCharacterId}/memories/forget`,
      {
        method: "POST",
        token
      }
    );
    setNotice(`${response.forgotten} low-value memories forgotten.`);
    await refreshSideState(token, activeCharacterId, activeConversation.id);
  }

  async function addJournal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !activeCharacterId || !journalTitle.trim() || !journalSummary.trim()) {
      return;
    }
    await apiJson<Journal>(`/characters/${activeCharacterId}/journals`, {
      method: "POST",
      body: JSON.stringify({
        conversation_id: activeConversation?.id ?? null,
        title: journalTitle.trim(),
        summary: journalSummary.trim(),
        journal_type: "manual_note",
        importance: 0.6
      }),
      token
    });
    setJournalTitle("");
    setJournalSummary("");
    if (activeConversation) {
      await refreshSideState(token, activeCharacterId, activeConversation.id);
    }
  }

  function resetKnowledge() {
    setMemories([]);
    setMemoryContent("");
    setMemoryPinned(false);
    setEditingMemoryId(null);
    setMemoryEditContent("");
    setJournals([]);
    setJournalTitle("");
    setJournalSummary("");
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
      journals,
      journalTitle,
      journalSummary
    },
    actions: {
      setMemories,
      setMemoryContent,
      setMemoryType,
      setMemoryImportance,
      setMemoryPinned,
      setEditingMemoryId,
      setMemoryEditContent,
      setJournals,
      setJournalTitle,
      setJournalSummary,
      addMemory,
      saveMemoryEdit,
      toggleMemoryPinned,
      deleteMemory,
      clearMemories,
      forgetMemories,
      addJournal,
      resetKnowledge
    }
  };
}
