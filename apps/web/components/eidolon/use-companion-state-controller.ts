"use client";

import { useState } from "react";

import { apiJson } from "@/lib/api";

import { emptyRelationship } from "./controller-utils";
import type {
  AdultStatus,
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
};

export function useCompanionStateController({
  setMemories,
  setJournals
}: UseCompanionStateControllerArgs) {
  const [relationship, setRelationship] = useState<Relationship>(emptyRelationship);
  const [adultStatus, setAdultStatus] = useState<AdultStatus | null>(null);
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [debug, setDebug] = useState<DebugPayload | null>(null);
  const [panel, setPanel] = useState<Panel>("overview");

  const timeline = relationship.metadata_json.timeline ?? debug?.relationship?.timeline ?? [];

  async function refreshCompanionState(authToken: string, characterId: string) {
    const [memoryResult, relationshipResult, debugResult, jobsResult, journalsResult, adultResult] =
      await Promise.allSettled([
        apiJson<MemoryItem[]>(`/characters/${characterId}/memories`, { token: authToken }),
        apiJson<Relationship>(`/characters/${characterId}/relationship`, { token: authToken }),
        apiJson<DebugPayload>(`/debug/character/${characterId}`, { token: authToken }),
        apiJson<ScheduledJob[]>("/debug/jobs", { token: authToken }),
        apiJson<Journal[]>(`/characters/${characterId}/journals`, { token: authToken }),
        apiJson<AdultStatus>(`/characters/${characterId}/adult-status`, { token: authToken })
      ]);

    if (memoryResult.status === "fulfilled") {
      setMemories(memoryResult.value);
    }
    if (relationshipResult.status === "fulfilled") {
      setRelationship(relationshipResult.value);
    }
    if (debugResult.status === "fulfilled") {
      setDebug(debugResult.value);
    }
    if (jobsResult.status === "fulfilled") {
      setJobs(jobsResult.value);
    }
    if (journalsResult.status === "fulfilled") {
      setJournals(journalsResult.value);
    }
    if (adultResult.status === "fulfilled") {
      setAdultStatus(adultResult.value);
    }
  }

  function resetCompanionState() {
    setRelationship(emptyRelationship);
    setAdultStatus(null);
    setJobs([]);
    setDebug(null);
    setPanel("overview");
  }

  return {
    state: {
      relationship,
      adultStatus,
      jobs,
      debug,
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
