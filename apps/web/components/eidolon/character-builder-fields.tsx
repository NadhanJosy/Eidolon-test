import type { ReactNode, RefObject } from "react";

import type { CharacterDraftErrors } from "./character-builder-model";
import type { CharacterDraft } from "./types";
import { inputClass } from "./ui";

export type BuilderStepProps = {
  draft: CharacterDraft;
  errors: CharacterDraftErrors;
  onChange: <K extends keyof CharacterDraft>(field: K, value: CharacterDraft[K]) => void;
};

export function BuilderSection({
  eyebrow,
  title,
  summary,
  children
}: {
  eyebrow: string;
  title: string;
  summary: string;
  children: ReactNode;
}) {
  return (
    <section className="mx-auto max-w-3xl space-y-5">
      <div>
        <p className="text-xs uppercase text-moss">{eyebrow}</p>
        <h3 className="mt-1 text-lg font-semibold">{title}</h3>
        <p className="mt-1 max-w-2xl text-sm leading-6 text-zinc-500">{summary}</p>
      </div>
      {children}
    </section>
  );
}

export function BuilderField({
  field,
  label,
  value,
  error,
  required = false,
  inputMode,
  type = "text",
  maxLength,
  inputRef,
  onChange
}: {
  field: keyof CharacterDraft;
  label: string;
  value: string;
  error?: string;
  required?: boolean;
  inputMode?: "numeric";
  type?: "text" | "time";
  maxLength?: number;
  inputRef?: RefObject<HTMLInputElement | null>;
  onChange: (value: string) => void;
}) {
  const inputId = `character-builder-${field}`;
  const errorId = `${inputId}-error`;
  return (
    <label className="block text-sm text-zinc-300" htmlFor={inputId}>
      <span>
        {label}
        {required ? <span className="text-moss"> required</span> : null}
      </span>
      <input
        aria-describedby={error ? errorId : undefined}
        aria-invalid={Boolean(error)}
        className={`${inputClass} ${error ? "border-amber-700" : ""}`}
        id={inputId}
        inputMode={inputMode}
        maxLength={maxLength}
        onChange={(event) => onChange(event.target.value)}
        ref={inputRef}
        type={type}
        value={value}
      />
      {error ? (
        <span className="mt-1 block text-xs text-amber-200" id={errorId}>
          {error}
        </span>
      ) : null}
    </label>
  );
}

export function BuilderArea({
  field,
  label,
  value,
  error,
  required = false,
  rows,
  maxLength,
  onChange
}: {
  field: keyof CharacterDraft;
  label: string;
  value: string;
  error?: string;
  required?: boolean;
  rows: number;
  maxLength?: number;
  onChange: (value: string) => void;
}) {
  const inputId = `character-builder-${field}`;
  const errorId = `${inputId}-error`;
  return (
    <label className="block text-sm text-zinc-300" htmlFor={inputId}>
      <span>
        {label}
        {required ? <span className="text-moss"> required</span> : null}
      </span>
      <textarea
        aria-describedby={error ? errorId : undefined}
        aria-invalid={Boolean(error)}
        className={`${inputClass} resize-y ${error ? "border-amber-700" : ""}`}
        id={inputId}
        maxLength={maxLength}
        onChange={(event) => onChange(event.target.value)}
        rows={rows}
        value={value}
      />
      {error ? (
        <span className="mt-1 block text-xs text-amber-200" id={errorId}>
          {error}
        </span>
      ) : null}
    </label>
  );
}

export function BuilderToggle({
  checked,
  label,
  detail,
  error,
  disabled = false,
  onChange
}: {
  checked: boolean;
  label: string;
  detail?: string;
  error?: string;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label
      className={`flex min-h-14 items-center justify-between gap-4 rounded-md border bg-ink px-3 py-2 ${
        error
          ? "border-amber-700"
          : disabled
            ? "border-line text-zinc-600"
            : "border-line text-zinc-300"
      }`}
    >
      <span>
        <span className="block text-sm">{label}</span>
        {detail ? (
          <span className="mt-1 block text-xs leading-5 text-zinc-500">{detail}</span>
        ) : null}
        {error ? <span className="mt-1 block text-xs text-amber-200">{error}</span> : null}
      </span>
      <input
        aria-invalid={Boolean(error)}
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        type="checkbox"
      />
    </label>
  );
}
