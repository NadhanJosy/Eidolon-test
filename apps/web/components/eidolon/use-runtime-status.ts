"use client";

import { useCallback, useEffect, useState } from "react";

import { apiJson } from "@/lib/api";

import { completeHealthPayload } from "./companion-state-contract";
import type { RuntimeHealthState, RuntimeStatus } from "./types";

const initialRuntimeStatus: RuntimeStatus = {
  api: "checking",
  db: "checking",
  llm: "checking",
  llmProvider: null,
  checkedAt: null
};

export function useRuntimeStatus() {
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus>(initialRuntimeStatus);

  const refreshRuntimeStatus = useCallback(async () => {
    setRuntimeStatus((current) => ({
      ...current,
      api: "checking",
      db: "checking",
      llm: "checking"
    }));
    setRuntimeStatus(await fetchRuntimeStatus());
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function loadRuntimeStatus() {
      const nextStatus = await fetchRuntimeStatus();
      if (!cancelled) {
        setRuntimeStatus(nextStatus);
      }
    }
    void loadRuntimeStatus();
    return () => {
      cancelled = true;
    };
  }, []);

  return { runtimeStatus, refreshRuntimeStatus };
}

function healthStateFromResult(
  result: PromiseSettledResult<unknown>
): RuntimeHealthState {
  if (result.status === "rejected") {
    return "offline";
  }
  return completeHealthPayload(result.value)?.status ?? "degraded";
}

function providerFromResult(result: PromiseSettledResult<unknown>): string | null {
  if (result.status === "fulfilled") {
    return completeHealthPayload(result.value)?.provider ?? null;
  }
  return null;
}

async function fetchRuntimeStatus(): Promise<RuntimeStatus> {
  const [apiResult, dbResult, llmResult] = await Promise.allSettled([
    apiJson<unknown>("/health"),
    apiJson<unknown>("/health/db"),
    apiJson<unknown>("/health/llm")
  ]);

  return {
    api: healthStateFromResult(apiResult),
    db: healthStateFromResult(dbResult),
    llm: healthStateFromResult(llmResult),
    llmProvider: providerFromResult(llmResult),
    checkedAt: new Date().toISOString()
  };
}
