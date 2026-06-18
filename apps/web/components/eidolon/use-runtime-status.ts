"use client";

import { useCallback, useEffect, useState } from "react";

import { apiJson } from "@/lib/api";

import type { RuntimeHealthState, RuntimeStatus } from "./types";

const initialRuntimeStatus: RuntimeStatus = {
  api: "checking",
  db: "checking",
  llm: "checking",
  llmProvider: null,
  checkedAt: null
};

type HealthPayload = {
  status?: unknown;
  provider?: unknown;
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
  result: PromiseSettledResult<HealthPayload>
): RuntimeHealthState {
  if (result.status === "rejected") {
    return "offline";
  }
  return result.value.status === "ok" || result.value.status === "degraded"
    ? result.value.status
    : "degraded";
}

function providerFromResult(result: PromiseSettledResult<HealthPayload>): string | null {
  if (result.status === "fulfilled" && typeof result.value.provider === "string") {
    return result.value.provider;
  }
  return null;
}

async function fetchRuntimeStatus(): Promise<RuntimeStatus> {
  const [apiResult, dbResult, llmResult] = await Promise.allSettled([
    apiJson<HealthPayload>("/health"),
    apiJson<HealthPayload>("/health/db"),
    apiJson<HealthPayload>("/health/llm")
  ]);

  return {
    api: healthStateFromResult(apiResult),
    db: healthStateFromResult(dbResult),
    llm: healthStateFromResult(llmResult),
    llmProvider: providerFromResult(llmResult),
    checkedAt: new Date().toISOString()
  };
}
