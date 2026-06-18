import type { ReactNode } from "react";

export const inputClass =
  "mt-1 w-full rounded-md border border-line bg-ink/90 px-3 py-2 text-sm text-paper shadow-inner shadow-black/20 placeholder:text-zinc-600";

export const primaryButtonClass =
  "rounded-md bg-paper px-3 py-2 text-sm font-semibold text-ink shadow-sm shadow-black/20 disabled:cursor-not-allowed disabled:opacity-50";

export const secondaryButtonClass =
  "rounded-md border border-line bg-ink px-3 py-2 text-sm text-paper hover:border-zinc-400 disabled:cursor-not-allowed disabled:opacity-50";

export const quietButtonClass =
  "rounded-md px-2 py-1 text-xs text-zinc-400 hover:bg-ink hover:text-paper";

export const errorClass =
  "rounded-md border border-amber-700 bg-amber-950/70 px-3 py-2 text-sm text-amber-100";

export const noticeClass =
  "rounded-md border border-moss bg-lime-950/60 px-3 py-2 text-sm text-lime-100";

export function Surface({
  children,
  className = ""
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-lg border border-line bg-panel shadow-2xl shadow-black/20 ${className}`}>
      {children}
    </section>
  );
}

export function EmptyState({ text }: { text: string }) {
  return (
    <p className="rounded-md border border-dashed border-line bg-ink/70 p-3 text-sm text-zinc-500">
      {text}
    </p>
  );
}

export function TagRow({ tags }: { tags: string[] }) {
  if (tags.length === 0) {
    return null;
  }
  return (
    <div className="mt-2 flex flex-wrap gap-1">
      {tags.slice(0, 7).map((tag) => (
        <span
          className="rounded border border-line bg-panel px-2 py-1 text-xs text-zinc-400"
          key={tag}
        >
          {tag}
        </span>
      ))}
    </div>
  );
}

export function MetricCard({
  label,
  value,
  accent = "bg-tide"
}: {
  label: string;
  value: number;
  accent?: string;
}) {
  const percentage = Math.max(0, Math.min(100, value));
  return (
    <div className="rounded-md border border-line bg-ink p-2">
      <div className="flex items-center justify-between gap-2">
        <dt className="text-xs text-zinc-500">{label}</dt>
        <dd className="font-mono text-xs text-zinc-300">{formatMetric(value)}</dd>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-zinc-800">
        <div className={`h-full ${accent}`} style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}

export function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

export function formatMetric(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "0.0";
}

export function parseDecimal(value: string, fallback: number) {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function tabClass(active: boolean) {
  return `rounded-md px-2 py-2 text-xs capitalize sm:text-sm ${
    active ? "bg-paper text-ink" : "text-zinc-400 hover:bg-ink hover:text-paper"
  }`;
}
