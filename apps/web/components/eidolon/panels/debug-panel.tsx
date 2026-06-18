import type { Conversation, DebugPayload, ScheduledJob } from "../types";
import { EmptyState, formatTimestamp } from "../ui";

export function DebugPanel({
  debug,
  jobs,
  conversations
}: {
  debug: DebugPayload | null;
  jobs: ScheduledJob[];
  conversations: Conversation[];
}) {
  const pendingJobs = jobs.filter((job) => job.status === "pending").length;
  const failedJobs = jobs.filter((job) => job.status === "failed").length;
  const provider = debug?.prompt_context?.llm_provider ?? "unknown";
  const promptVersion = debug?.prompt_context?.prompt_version ?? "not loaded";
  const promptChars = debug?.prompt_context?.prompt_chars ?? 0;

  return (
    <>
      <section className="grid grid-cols-3 gap-2">
        <DebugStat label="Provider" value={provider} />
        <DebugStat label="Pending" value={pendingJobs.toString()} />
        <DebugStat label="Failed" value={failedJobs.toString()} />
      </section>
      <section className="space-y-2">
        <div>
          <h2 className="text-sm font-semibold">Prompt Preview</h2>
          <p className="mt-1 text-xs text-zinc-500">
            Private debug only · {promptVersion} · {promptChars} chars
          </p>
        </div>
        <pre className="max-h-72 overflow-y-auto rounded-md border border-line bg-ink p-3 text-xs leading-5">
          {debug?.prompt_context?.prompt_preview ?? "No prompt preview loaded."}
        </pre>
      </section>
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Jobs</h2>
        {jobs.length === 0 ? <EmptyState text="No jobs." /> : null}
        {jobs.map((job) => (
          <article className="rounded-md border border-line bg-ink p-2 text-xs" key={job.id}>
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-zinc-300">{job.job_type}</span>
              <span className={job.status === "failed" ? "text-ember" : "text-zinc-500"}>
                {job.status}
              </span>
            </div>
            <p className="mt-1 text-zinc-500">{formatTimestamp(job.run_at)}</p>
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
