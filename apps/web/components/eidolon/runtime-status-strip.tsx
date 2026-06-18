import type { RuntimeHealthState, RuntimeStatus } from "./types";

export function RuntimeStatusStrip({
  status,
  onRefresh
}: {
  status: RuntimeStatus;
  onRefresh: () => void;
}) {
  const checkedAt = status.checkedAt ? formatStatusTime(status.checkedAt) : "not checked yet";

  return (
    <div
      className="flex flex-wrap items-center gap-1"
      aria-label={`Runtime status, checked ${checkedAt}`}
    >
      <RuntimePill label="API" state={status.api} />
      <RuntimePill label="DB" state={status.db} />
      <RuntimePill
        label={status.llmProvider ? `LLM ${status.llmProvider}` : "LLM"}
        state={status.llm}
      />
      <button
        className="rounded-md border border-line bg-ink px-2 py-2 text-xs text-zinc-400 hover:border-zinc-400 hover:text-paper"
        onClick={onRefresh}
        title={`Last checked ${checkedAt}`}
        type="button"
      >
        Check
      </button>
    </div>
  );
}

function RuntimePill({ label, state }: { label: string; state: RuntimeHealthState }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-2 text-xs ${runtimePillClass(
        state
      )}`}
      title={`${label}: ${state}`}
    >
      <span className={`h-2 w-2 rounded-full ${runtimeDotClass(state)}`} aria-hidden="true" />
      {label}
    </span>
  );
}

function runtimePillClass(state: RuntimeHealthState) {
  if (state === "ok") {
    return "border-moss bg-lime-950/50 text-lime-100";
  }
  if (state === "checking") {
    return "border-line bg-ink text-zinc-400";
  }
  if (state === "degraded") {
    return "border-amber-700 bg-amber-950/60 text-amber-100";
  }
  return "border-red-900 bg-red-950/60 text-red-100";
}

function runtimeDotClass(state: RuntimeHealthState) {
  if (state === "ok") {
    return "bg-moss";
  }
  if (state === "checking") {
    return "bg-zinc-500";
  }
  if (state === "degraded") {
    return "bg-amber-400";
  }
  return "bg-red-400";
}

function formatStatusTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}
