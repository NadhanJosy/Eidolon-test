"use client";

import { useRef, useState } from "react";

import { apiJson } from "@/lib/api";

import {
  completeAdultStatus,
  completeRelationship,
  isCompleteContinuityThreadList,
  isCompleteJournalList,
  isCompleteMemoryList
} from "./companion-state-contract";
import { emptyRelationship } from "./controller-utils";
import type {
  AdultStatus,
  AdultReadinessState,
  ContinuityThread,
  Journal,
  MemoryItem,
  Relationship
} from "./types";

type UseCompanionStateControllerArgs = {
  setMemories: (memories: MemoryItem[]) => void;
  setJournals: (journals: Journal[]) => void;
  setContinuityThreads: (threads: ContinuityThread[]) => void;
  onAdultStatusChange: (characterId: string, status: AdultStatus | null) => void;
};

export function useCompanionStateController({
  setMemories,
  setJournals,
  setContinuityThreads,
  onAdultStatusChange
}: UseCompanionStateControllerArgs) {
  const refreshVersion = useRef(0);
  const stateCharacterIdRef = useRef<string | null>(null);
  const adultStatusCharacterIdRef = useRef<string | null>(null);
  const [relationship, setRelationship] = useState<Relationship>(emptyRelationship);
  const [adultStatus, setAdultStatus] = useState<AdultStatus | null>(null);
  const [adultStatusCharacterId, setAdultStatusCharacterId] = useState<string | null>(null);
  const [adultReadinessState, setAdultReadinessState] =
    useState<AdultReadinessState>("idle");
  const [supportingStateError, setSupportingStateError] = useState<string | null>(null);
  const timeline = relationship.metadata_json.timeline ?? [];

  async function refreshCompanionState(
    authToken: string,
    characterId: string,
    _conversationId?: string,
    shouldApply?: () => boolean
  ) {
    const requestVersion = ++refreshVersion.current;
    if (stateCharacterIdRef.current !== characterId) {
      stateCharacterIdRef.current = characterId;
      setMemories([]);
      setJournals([]);
      setContinuityThreads([]);
      setRelationship(emptyRelationship);
    }
    if (adultStatusCharacterIdRef.current !== characterId) {
      adultStatusCharacterIdRef.current = null;
      setAdultStatus(null);
      setAdultStatusCharacterId(null);
      setAdultReadinessState("loading");
    }
    const [
      memoryResult,
      relationshipResult,
      journalsResult,
      threadsResult,
      adultResult
    ] = await Promise.allSettled([
        apiJson<unknown>(`/characters/${characterId}/memories`, { token: authToken }),
        apiJson<unknown>(`/characters/${characterId}/relationship`, { token: authToken }),
        apiJson<unknown>(`/characters/${characterId}/journals`, { token: authToken }),
        apiJson<unknown>(`/characters/${characterId}/threads?status=all`, {
          token: authToken
        }),
        apiJson<unknown>(`/characters/${characterId}/adult-status`, { token: authToken })
      ]);

    if (
      requestVersion !== refreshVersion.current ||
      (shouldApply !== undefined && !shouldApply())
    ) {
      return;
    }
    if (
      memoryResult.status === "fulfilled" &&
      isCompleteMemoryList(memoryResult.value, characterId, "active")
    ) {
      setMemories(memoryResult.value);
    }
    const unavailable: string[] = [];
    if (
      memoryResult.status !== "fulfilled" ||
      !isCompleteMemoryList(memoryResult.value, characterId, "active")
    ) unavailable.push("memories");
    const completeRelationshipValue =
      relationshipResult.status === "fulfilled"
        ? completeRelationship(relationshipResult.value, characterId)
        : null;
    if (completeRelationshipValue) {
      setRelationship(completeRelationshipValue);
    } else {
      unavailable.push("relationship history");
    }
    if (
      journalsResult.status === "fulfilled" &&
      isCompleteJournalList(journalsResult.value, characterId)
    ) {
      setJournals(journalsResult.value);
    } else {
      unavailable.push("moments");
    }
    if (
      threadsResult.status === "fulfilled" &&
      isCompleteContinuityThreadList(threadsResult.value, characterId)
    ) {
      setContinuityThreads(threadsResult.value);
    } else {
      unavailable.push("living threads");
    }
    if (adultResult.status === "fulfilled") {
      const completeAdult = completeAdultStatus(adultResult.value);
      adultStatusCharacterIdRef.current = completeAdult ? characterId : null;
      setAdultStatus(completeAdult);
      setAdultStatusCharacterId(completeAdult ? characterId : null);
      setAdultReadinessState(completeAdult ? "ready" : "error");
      onAdultStatusChange(characterId, completeAdult);
    } else {
      adultStatusCharacterIdRef.current = null;
      setAdultStatus(null);
      setAdultStatusCharacterId(null);
      setAdultReadinessState("error");
      onAdultStatusChange(characterId, null);
    }
    setSupportingStateError(
      unavailable.length > 0
        ? `${humanList(unavailable)} could not be opened just now. Your conversation is safe; reopen this companion or try again in a moment.`
        : null
    );
  }

  function resetCompanionState() {
    refreshVersion.current += 1;
    stateCharacterIdRef.current = null;
    adultStatusCharacterIdRef.current = null;
    setRelationship(emptyRelationship);
    setAdultStatus(null);
    setAdultStatusCharacterId(null);
    setAdultReadinessState("idle");
    setSupportingStateError(null);
  }

  return {
    state: {
      relationship,
      adultStatus,
      adultStatusCharacterId,
      adultReadinessState,
      supportingStateError,
      timeline
    },
    actions: {
      refreshCompanionState,
      resetCompanionState
    }
  };
}

function humanList(items: string[]): string {
  if (items.length === 1) return items[0][0].toUpperCase() + items[0].slice(1);
  return `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`.replace(/^./u, (letter) => letter.toUpperCase());
}
