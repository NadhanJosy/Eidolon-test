import { RuntimeStatusStrip } from "../runtime-status-strip";
import type {
  Conversation,
  ConversationDebugPayload,
  DebugPayload,
  RuntimeStatus,
  ScheduledJob
} from "../types";
import { EmptyState, formatTimestamp } from "../ui";

export function DebugPanel({
  debug,
  conversationDebug,
  jobs,
  conversations,
  runtimeStatus,
  onRefreshRuntime
}: {
  debug: DebugPayload | null;
  conversationDebug: ConversationDebugPayload | null;
  jobs: ScheduledJob[];
  conversations: Conversation[];
  runtimeStatus: RuntimeStatus;
  onRefreshRuntime: () => void;
}) {
  const pendingJobs = jobs.filter((job) => job.status === "pending").length;
  const failedJobs = jobs.filter((job) => job.status === "failed").length;
  const provider = debug?.prompt_context?.llm_provider ?? "unknown";
  const schedulerState = !debug?.runtime
    ? "unknown"
    : debug.runtime.scheduler_running
      ? "running"
      : debug.runtime.scheduler_enabled
        ? "waiting"
        : "off";
  const promptVersion = debug?.prompt_context?.prompt_version ?? "not loaded";
  const currentSummary = debug?.prompt_context?.current_summary;
  const errors = debug?.errors ?? [];
  const lastContext = conversationDebug?.last_assembled_context;
  const manifest = lastContext?.context_manifest;
  const relationship = debug?.relationship;
  const retrievedMemories = Array.isArray(debug?.memories)
    ? debug.memories.slice(0, 10)
    : [];
  const selectedMemoryIds = new Set(
    manifest?.memory_items
      .map((item) => item.id)
      .filter((id): id is string => typeof id === "string") ?? []
  );

  return (
    <>
      <section className="space-y-2">
        <div>
          <h2 className="text-sm font-semibold">Runtime Health</h2>
          <p className="mt-1 text-xs text-zinc-500">
            Private operational status for this installation
          </p>
        </div>
        <RuntimeStatusStrip status={runtimeStatus} onRefresh={onRefreshRuntime} />
      </section>
      <section className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <DebugStat label="Provider" value={provider} />
        <DebugStat label="Scheduler" value={schedulerState} />
        <DebugStat label="Pending" value={pendingJobs.toString()} />
        <DebugStat label="Failed" value={failedJobs.toString()} />
      </section>
      <section className="space-y-2">
        <div>
          <h2 className="text-sm font-semibold">Response Plan</h2>
          <p className="mt-1 text-xs text-zinc-500">
            {lastContext
              ? `${generationLabel(lastContext.generation_kind)} · ${formatTimestamp(lastContext.assembled_at)}`
              : "No completed context assembly for this thread"}
          </p>
        </div>
        {manifest?.orchestration ? (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <DebugStat label="Intent" value={manifest.orchestration.intent} />
            <DebugStat label="Strategy" value={manifest.orchestration.strategy} />
            <DebugStat label="Rhythm" value={manifest.orchestration.rhythm} />
            <DebugStat label="Initiative" value={manifest.orchestration.initiative} />
          </div>
        ) : null}
        <pre className="max-h-40 overflow-y-auto rounded-md border border-line bg-ink p-3 text-xs leading-5">
          {lastContext?.response_plan_summary ?? "No response plan loaded."}
        </pre>
      </section>
      <section className="space-y-2">
        <div>
          <h2 className="text-sm font-semibold">Relationship State</h2>
          <p className="mt-1 text-xs text-zinc-500">
            Raw private relationship state for this companion
          </p>
        </div>
        {relationship ? (
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <DebugStat label="Trust" value={debugMetric(relationship.trust)} />
              <DebugStat label="Warmth" value={debugMetric(relationship.warmth)} />
              <DebugStat label="Familiarity" value={debugMetric(relationship.familiarity)} />
              <DebugStat label="Intimacy" value={debugMetric(relationship.intimacy)} />
              <DebugStat label="Attachment" value={debugMetric(relationship.attachment)} />
              <DebugStat label="Tension" value={debugMetric(relationship.tension)} />
            </div>
            <ContextLine
              label="Posture"
              values={[
                debugLabel(relationship.mood, "unknown mood"),
                debugLabel(relationship.conflict_state, "unknown conflict"),
                relationship.repair_needed ? "repair needed" : "no repair flag"
              ]}
            />
            <ContextLine label="Tags" values={debugLabels(relationship.tags_json)} />
          </div>
        ) : (
          <EmptyState text="No relationship Debug snapshot is loaded." />
        )}
      </section>
      <section className="space-y-2">
        <div>
          <h2 className="text-sm font-semibold">Retrieved Memories</h2>
          <p className="mt-1 text-xs text-zinc-500">
            Current active recall snapshot; open a row to inspect private content
          </p>
        </div>
        {retrievedMemories.length > 0 ? (
          <div className="space-y-2">
            {retrievedMemories.map((memory, index) => (
              <details
                className="rounded-md border border-line bg-ink p-2 text-xs"
                key={debugMemoryKey(memory.id, index)}
              >
                <summary className="cursor-pointer select-none text-zinc-300">
                  <span className="font-medium">
                    {debugLabel(memory.memory_type, "unknown type")}
                  </span>
                  <span className="ml-2 text-zinc-600">
                    importance {debugMetric(memory.importance)} · confidence{" "}
                    {debugMetric(memory.confidence)}
                  </span>
                  {memory.pinned ? (
                    <span className="ml-2 text-lime-200">pinned</span>
                  ) : null}
                  {typeof memory.id === "string" && selectedMemoryIds.has(memory.id) ? (
                    <span className="ml-2 text-cyan-200">used last turn</span>
                  ) : null}
                </summary>
                <p className="mt-2 max-h-40 overflow-y-auto whitespace-pre-wrap break-words border-t border-line pt-2 leading-5 text-zinc-400">
                  {debugMemoryContent(memory.content)}
                </p>
              </details>
            ))}
          </div>
        ) : (
          <EmptyState text="No active memories are available in the current Debug snapshot." />
        )}
      </section>
      <section className="space-y-2">
        <div>
          <h2 className="text-sm font-semibold">Memory Pipeline</h2>
          <p className="mt-1 text-xs text-zinc-500">
            Private per-turn learning decisions for the active thread
          </p>
        </div>
        {conversationDebug?.memory_pipeline?.length ? (
          <div className="space-y-2">
            {conversationDebug.memory_pipeline.slice(-6).map((row) => (
              <article className="rounded-md border border-line bg-ink p-2 text-xs" key={row.message_id}>
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={
                      row.decision.accepted ? "text-paper" : "text-zinc-500"
                    }
                  >
                    {memoryDecisionLabel(row.decision.reason)}
                  </span>
                  <span className="text-zinc-600">{formatTimestamp(row.created_at)}</span>
                </div>
                <p className="mt-1 text-zinc-500">
                  {row.decision.memory_type ?? row.stored_memory?.memory_type ?? "not stored"} ·{" "}
                  {row.privacy_mode}
                  {row.decision.trigger ? ` · ${row.decision.trigger}` : ""}
                </p>
                {row.stored_memory ? (
                  <p className="mt-1 text-zinc-400">
                    stored {row.stored_memory.memory_type} · confidence{" "}
                    {row.stored_memory.confidence.toFixed(2)}
                  </p>
                ) : null}
              </article>
            ))}
          </div>
        ) : (
          <EmptyState text="No memory pipeline events for this thread." />
        )}
      </section>
      <section className="space-y-2">
        <div>
          <h2 className="text-sm font-semibold">Last Assembled Context</h2>
          <p className="mt-1 text-xs text-zinc-500">
            {lastContext
              ? `${lastContext.prompt_version} · ${lastContext.prompt_chars.toLocaleString()} chars`
              : `${promptVersion} · waiting for a turn`}
          </p>
        </div>
        {lastContext && manifest ? (
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              <DebugStat label="Provider" value={lastContext.provider} />
              <DebugStat label="Mode" value={lastContext.content_mode} />
              <DebugStat label="Memories" value={manifest.memory_items.length.toString()} />
              <DebugStat label="Episodes" value={manifest.journal_items.length.toString()} />
              <DebugStat label="Scene" value={manifest.scenario?.mode ?? "legacy"} />
            </div>
            <ContextLine
              label="Memory types"
              values={manifest.memory_items.map((item) => item.memory_type)}
            />
            <ContextLine
              label="Episode types"
              values={manifest.journal_items.map((item) => item.journal_type)}
            />
            <ContextLine
              label="Recent roles"
              values={manifest.recent_messages.map(
                (message) => `${message.role}:${message.privacy_mode}`
              )}
            />
            <ContextLine label="Safety gates" values={manifest.safety.reasons} />
          </div>
        ) : (
          <EmptyState text="No assembled context for this thread." />
        )}
      </section>
      <section className="space-y-2">
        <div>
          <h2 className="text-sm font-semibold">Current Retrieval</h2>
          <p className="mt-1 text-xs text-zinc-500">
            {currentSummary
              ? `${currentSummary.character.name} · ${formatTimestamp(currentSummary.snapshot_at)}`
              : "Current character state is not loaded"}
          </p>
        </div>
        {currentSummary ? (
          <div className="space-y-2">
            <ContextLine
              label="Memories"
              values={currentSummary.retrieved_memories.map((item) => item.memory_type)}
            />
            <ContextLine
              label="Episodes"
              values={currentSummary.journals.map((item) => item.journal_type)}
            />
            <ContextLine label="Pending" values={currentSummary.pending_proactive_events} />
          </div>
        ) : (
          <EmptyState text="No current retrieval summary." />
        )}
      </section>
      <section className="space-y-2">
        <div>
          <h2 className="text-sm font-semibold">Errors</h2>
          <p className="mt-1 text-xs text-zinc-500">
            Safe recent generation failures for this companion
          </p>
        </div>
        {errors.length > 0 ? (
          <div className="space-y-2">
            {errors.map((event) => (
              <article className="rounded-md border border-line bg-ink p-2 text-xs" key={event.id}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-amber-200">{errorOperationLabel(event.operation)}</span>
                  <span className="text-zinc-600">{formatTimestamp(event.created_at)}</span>
                </div>
                <p className="mt-1 text-zinc-300">{event.safe_message}</p>
                <p className="mt-1 break-words font-mono text-zinc-500">
                  {event.provider} · {event.code}
                </p>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState text="No recent generation errors." />
        )}
      </section>
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Jobs</h2>
        {jobs.length === 0 ? <EmptyState text="No jobs." /> : null}
        {jobs.map((job) => (
          <article className="rounded-md border border-line bg-ink p-2 text-xs" key={job.id}>
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-zinc-300">{jobTypeLabel(job.job_type)}</span>
              <span className={job.status === "failed" ? "text-ember" : "text-zinc-500"}>
                {jobStatusLabel(job)}
              </span>
            </div>
            <p className="mt-1 text-zinc-500">
              {job.status === "pending" ? "Due" : "Scheduled"} {formatTimestamp(job.run_at)}
            </p>
            {jobResultLabel(job) ? (
              <p className="mt-1 text-zinc-400">{jobResultLabel(job)}</p>
            ) : null}
            {job.last_error ? (
              <p className="mt-1 text-amber-200">{job.last_error}</p>
            ) : null}
          </article>
        ))}
      </section>
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Conversations</h2>
        {conversations.length === 0 ? <EmptyState text="No conversations." /> : null}
        {conversations.map((conversation) => (
          <p className="rounded-md border border-line bg-ink p-2 text-xs" key={conversation.id}>
            <span className="block truncate text-zinc-300">
              {conversation.title ?? conversation.id}
            </span>
            <span className="text-zinc-500">
              {conversation.updated_at ? formatTimestamp(conversation.updated_at) : conversation.id}
            </span>
          </p>
        ))}
      </section>
    </>
  );
}

function DebugStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-ink p-2">
      <p className="text-[11px] uppercase text-zinc-600">{label}</p>
      <p className="mt-1 truncate font-mono text-xs text-zinc-200">{value}</p>
    </div>
  );
}

function ContextLine({ label, values }: { label: string; values: string[] }) {
  const uniqueValues = [...new Set(values.filter(Boolean))].slice(0, 8);
  return (
    <p className="rounded-md border border-line bg-ink p-2 text-xs">
      <span className="text-zinc-500">{label}</span>
      <span className="mt-1 block break-words text-zinc-300">
        {uniqueValues.length > 0 ? uniqueValues.join(" · ") : "None selected"}
      </span>
    </p>
  );
}

function debugMetric(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "unknown";
  }
  return Math.max(-999, Math.min(999, value)).toFixed(1);
}

function debugLabel(value: unknown, fallback: string): string {
  if (typeof value !== "string") {
    return fallback;
  }
  const normalized = value.trim().replace(/\s+/g, " ");
  return normalized ? normalized.slice(0, 80) : fallback;
}

function debugLabels(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is string => typeof item === "string")
    .map((item) => debugLabel(item, ""))
    .filter(Boolean)
    .slice(0, 8);
}

function debugMemoryContent(value: unknown): string {
  if (typeof value !== "string") {
    return "Memory content is unavailable.";
  }
  const content = value.trim();
  return content ? content.slice(0, 2000) : "Memory content is empty.";
}

function debugMemoryKey(value: unknown, index: number): string {
  return typeof value === "string" && value ? value : `debug-memory-${index}`;
}

function generationLabel(kind: "chat" | "stream" | "reroll" | "edit"): string {
  const labels = {
    chat: "Message",
    stream: "Stream",
    reroll: "Reroll",
    edit: "Edited turn"
  } satisfies Record<typeof kind, string>;
  return labels[kind];
}

function memoryDecisionLabel(reason: string) {
  const labels: Record<string, string> = {
    accepted: "Accepted",
    too_short: "Skipped: too short",
    unsafe_term: "Skipped: unsafe term",
    blocked_content: "Skipped: safety block",
    no_trigger: "Skipped: no durable cue",
    empty_content: "Skipped: empty",
    disabled_by_preferences: "Skipped: memory preference",
    conversation_private: "Skipped: private thread",
    character_private_memory_default: "Skipped: character privacy",
    adult_memory_storage_disabled: "Skipped: adult memory disabled",
    storage_blocked: "Skipped: storage blocked"
  };
  return labels[reason] ?? `Skipped: ${reason}`;
}

function jobTypeLabel(jobType: string): string {
  const labels: Record<string, string> = {
    maintenance_noop: "Maintenance check",
    memory_extract: "Memory review",
    relationship_decay: "Relationship drift",
    proactive_inactivity_check: "Quiet check-in",
    proactive_morning_check: "Morning note",
    proactive_goodnight_check: "Goodnight note",
    proactive_thinking_of_you: "Thinking-of-you note",
    proactive_milestone_check: "Milestone note",
    proactive_unresolved_thread_nudge: "Open-thread follow-up",
    proactive_delayed_double_text: "Delayed follow-up",
    proactive_message_create: "Manual companion note"
  };
  return labels[jobType] ?? jobType;
}

function errorOperationLabel(operation: "message" | "stream" | "reroll" | "edit"): string {
  const labels = {
    message: "Message generation",
    stream: "Streamed generation",
    reroll: "Alternate reply",
    edit: "Edited reply"
  } satisfies Record<typeof operation, string>;
  return labels[operation];
}

function jobStatusLabel(job: ScheduledJob): string {
  if (job.status === "pending" && job.retry_count > 0) {
    return `retry ${job.retry_count}`;
  }
  return job.status;
}

function jobResultLabel(job: ScheduledJob): string | null {
  const result = job.payload_json?.result;
  if (typeof result !== "string") {
    return null;
  }
  const labels: Record<string, string> = {
    noop: "Maintenance completed.",
    message_created: "Companion note delivered.",
    skipped_private_conversation: "Skipped because the thread is private.",
    skipped_private_turn: "Skipped because the latest turn is private.",
    skipped_user_returned: "Skipped because the user returned.",
    skipped_by_user_controls: "Skipped by presence preferences.",
    skipped_by_cooldown_or_state: "Skipped by cooldown or current thread state.",
    cancelled_by_user_controls: "Cancelled after presence preferences changed.",
    deferred_for_local_time: "Waiting for the next allowed local time.",
    memory_extract_complete: "Memory review completed.",
    relationship_decay_applied: "Relationship drift applied."
  };
  return labels[result] ?? result.replaceAll("_", " ");
}
