"use client";

import { useRef, useState } from "react";

import { apiJson } from "@/lib/api";

import {
  completeAdultStatus,
  completeConversationDebugPayload,
  completeDebugPayload,
  completeRelationship,
  completeScheduledJobs,
  isCompleteJournalList,
  isCompleteMemoryList
} from "./companion-state-contract";
import { emptyRelationship } from "./controller-utils";
import type {
  AdultStatus,
  AdultReadinessState,
  ConversationDebugPayload,
  DebugPayload,
  Journal,
  MemoryItem,
  Panel,
  Relationship,
  ScheduledJob
} from "./types";

type UseCompanionStateControllerArgs = {
  setMemories: (memories: MemoryItem[]) => void;
  setJournals: (journals: Journal[]) => void;
  onAdultStatusChange: (characterId: string, status: AdultStatus | null) => void;
};

export function useCompanionStateController({
  setMemories,
  setJournals,
  onAdultStatusChange
}: UseCompanionStateControllerArgs) {
  const refreshVersion = useRef(0);
  const stateCharacterIdRef = useRef<string | null>(null);
  const debugCharacterIdRef = useRef<string | null>(null);
  const adultStatusCharacterIdRef = useRef<string | null>(null);
  const [relationship, setRelationship] = useState<Relationship>(emptyRelationship);
  const [adultStatus, setAdultStatus] = useState<AdultStatus | null>(null);
  const [adultStatusCharacterId, setAdultStatusCharacterId] = useState<string | null>(null);
  const [adultReadinessState, setAdultReadinessState] =
    useState<AdultReadinessState>("idle");
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [debug, setDebug] = useState<DebugPayload | null>(null);
  const [conversationDebug, setConversationDebug] = useState<ConversationDebugPayload | null>(null);
  const [panel, setPanel] = useState<Panel>("overview");

  const timeline = relationship.metadata_json.timeline ?? debug?.relationship?.timeline ?? [];

  async function refreshCompanionState(
    authToken: string,
    characterId: string,
    conversationId?: string,
    shouldApply?: () => boolean
  ) {
    const requestVersion = ++refreshVersion.current;
    if (stateCharacterIdRef.current !== characterId) {
      stateCharacterIdRef.current = characterId;
      setMemories([]);
      setJournals([]);
      setRelationship(emptyRelationship);
    }
    if (debugCharacterIdRef.current !== characterId) {
      debugCharacterIdRef.current = null;
      setDebug(null);
      setConversationDebug(null);
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
      debugResult,
      jobsResult,
      journalsResult,
      adultResult,
      conversationDebugResult
    ] = await Promise.allSettled([
        apiJson<unknown>(`/characters/${characterId}/memories`, { token: authToken }),
        apiJson<unknown>(`/characters/${characterId}/relationship`, { token: authToken }),
        apiJson<unknown>(`/debug/character/${characterId}`, { token: authToken }),
        apiJson<unknown>("/debug/jobs", { token: authToken }),
        apiJson<unknown>(`/characters/${characterId}/journals`, { token: authToken }),
        apiJson<unknown>(`/characters/${characterId}/adult-status`, { token: authToken }),
        conversationId
          ? apiJson<unknown>(`/debug/conversation/${conversationId}`, {
              token: authToken
            })
          : Promise.resolve(null)
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
    const completeRelationshipValue =
      relationshipResult.status === "fulfilled"
        ? completeRelationship(relationshipResult.value, characterId)
        : null;
    if (completeRelationshipValue) {
      setRelationship(completeRelationshipValue);
    }
    if (debugResult.status === "fulfilled") {
      const completeDebug = completeDebugPayload(debugResult.value, characterId);
      debugCharacterIdRef.current = completeDebug ? characterId : null;
      setDebug(completeDebug);
    } else {
      debugCharacterIdRef.current = null;
      setDebug(null);
    }
    if (jobsResult.status === "fulfilled") {
      const completeJobs = completeScheduledJobs(jobsResult.value);
      if (completeJobs) {
        setJobs(completeJobs);
      }
    }
    if (
      journalsResult.status === "fulfilled" &&
      isCompleteJournalList(journalsResult.value, characterId)
    ) {
      setJournals(journalsResult.value);
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
    if (conversationId && conversationDebugResult.status === "fulfilled") {
      setConversationDebug(
        completeConversationDebugPayload(
          conversationDebugResult.value,
          conversationId,
          characterId
        )
      );
    } else {
      setConversationDebug(null);
    }
  }

  function resetCompanionState() {
    refreshVersion.current += 1;
    stateCharacterIdRef.current = null;
    debugCharacterIdRef.current = null;
    adultStatusCharacterIdRef.current = null;
    setRelationship(emptyRelationship);
    setAdultStatus(null);
    setAdultStatusCharacterId(null);
    setAdultReadinessState("idle");
    setJobs([]);
    setDebug(null);
    setConversationDebug(null);
    setPanel("overview");
  }

  return {
    state: {
      relationship,
      adultStatus,
      adultStatusCharacterId,
      adultReadinessState,
      jobs,
      debug,
      conversationDebug,
      panel,
      timeline
    },
    actions: {
      setPanel,
      refreshCompanionState,
      resetCompanionState
    }
  };
}
