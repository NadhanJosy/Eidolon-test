import type { ButtonHTMLAttributes, ReactNode } from "react";

import { Icon, type IconName } from "./icons";

export function CompanionPortrait({
  name,
  theme,
  size = "medium",
  quiet = false
}: {
  name: string;
  theme?: string;
  size?: "small" | "medium" | "large";
  quiet?: boolean;
}) {
  const initial = name.trim().charAt(0).toUpperCase() || "E";
  const resolvedTheme = theme || themeFromName(name);
  const palette = portraitPalettes[resolvedTheme] ?? portraitPalettes.ember;
  const sizes = {
    small: "h-10 w-10 text-sm",
    medium: "h-14 w-14 text-lg",
    large: "h-28 w-28 text-4xl sm:h-32 sm:w-32"
  };
  return (
    <div className={`companion-aura shrink-0 ${quiet ? "opacity-80" : ""}`}>
      <div
        aria-label={`${name}’s presence`}
        className={`${sizes[size]} relative grid place-items-center overflow-hidden rounded-full border border-[rgba(225,199,181,0.22)] font-eidolon-display text-[#f0d9c9] shadow-[inset_0_0_28px_rgba(0,0,0,0.34),0_12px_36px_rgba(0,0,0,0.35)]`}
        style={{ background: palette }}
      >
        <span aria-hidden="true" className="relative z-10">{initial}</span>
        <span
          aria-hidden="true"
          className="ambient-drift absolute -bottom-5 -right-3 h-12 w-12 rounded-full bg-[#b98265]/15 blur-xl"
        />
      </div>
      {!quiet ? (
        <span
          aria-hidden="true"
          className="presence-dot absolute bottom-[5%] right-[5%] h-2.5 w-2.5 rounded-full border-2 border-[#16130f] bg-[#d39a79]"
        />
      ) : null}
    </div>
  );
}

const portraitPalettes: Record<string, string> = {
  ember: "radial-gradient(circle at 32% 23%, rgba(221,173,146,.38), transparent 25%), linear-gradient(145deg,#5d3b31,#211916 67%,#0e0d0c)",
  cedar: "radial-gradient(circle at 32% 23%, rgba(203,198,151,.3), transparent 25%), linear-gradient(145deg,#53533d,#202018 67%,#0e0d0c)",
  rain: "radial-gradient(circle at 32% 23%, rgba(159,194,197,.28), transparent 25%), linear-gradient(145deg,#405355,#192123 67%,#0e0d0c)",
  plum: "radial-gradient(circle at 32% 23%, rgba(208,166,196,.28), transparent 25%), linear-gradient(145deg,#59414f,#241a21 67%,#0e0d0c)"
};

function themeFromName(name: string): string {
  const themes = Object.keys(portraitPalettes);
  const hash = [...name].reduce((total, character) => total + character.codePointAt(0)!, 0);
  return themes[hash % themes.length];
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <p className="text-[0.67rem] font-medium uppercase tracking-[0.2em] text-[#9a8f82]">
      {children}
    </p>
  );
}

export function PageHeading({
  eyebrow,
  title,
  description,
  action
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-5 border-b border-white/[0.08] pb-8 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-2xl">
        <Eyebrow>{eyebrow}</Eyebrow>
        <h1 className="mt-3 font-eidolon-display text-4xl leading-none text-[#f5eee5] sm:text-5xl">
          {title}
        </h1>
        <p className="mt-4 max-w-xl text-sm leading-6 text-[#a89f93] sm:text-[0.95rem]">
          {description}
        </p>
      </div>
      {action}
    </header>
  );
}

export function IconButton({
  icon,
  label,
  className = "",
  ...props
}: {
  icon: IconName;
  label: string;
  className?: string;
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children">) {
  return (
    <button
      aria-label={label}
      className={`grid h-10 w-10 shrink-0 place-items-center rounded-full border border-white/[0.09] bg-white/[0.035] text-[#aaa095] transition hover:border-white/[0.2] hover:bg-white/[0.07] hover:text-[#f4ede4] disabled:cursor-not-allowed disabled:opacity-35 ${className}`}
      title={label}
      type="button"
      {...props}
    >
      <Icon name={icon} />
    </button>
  );
}

export function PrimaryButton({
  children,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`min-h-11 rounded-full bg-[#e9ddd0] px-5 text-sm font-semibold text-[#201713] shadow-[0_8px_28px_rgba(185,130,101,0.14)] transition hover:bg-[#f6eee6] disabled:cursor-not-allowed disabled:opacity-45 ${className}`}
      type="button"
      {...props}
    >
      {children}
    </button>
  );
}

export function QuietButton({
  children,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`min-h-10 rounded-full border border-white/[0.11] bg-white/[0.025] px-4 text-sm text-[#c1b7ab] transition hover:border-white/[0.22] hover:bg-white/[0.06] hover:text-[#f2eae1] disabled:cursor-not-allowed disabled:opacity-40 ${className}`}
      type="button"
      {...props}
    >
      {children}
    </button>
  );
}

export function Field({
  label,
  hint,
  children
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-[#d8cec3]">{label}</span>
      {hint ? <span className="ml-2 text-xs text-[#736d65]">{hint}</span> : null}
      <span className="mt-2 block">{children}</span>
    </label>
  );
}

export const fieldClass =
  "w-full rounded-2xl border border-white/[0.1] bg-black/20 px-4 py-3 text-sm leading-6 text-[#eee6dc] shadow-inner shadow-black/20 outline-none transition placeholder:text-[#69635c] hover:border-white/[0.16] focus:border-[#b98265]/70";

export function Toggle({
  checked,
  disabled = false,
  label,
  detail,
  onChange
}: {
  checked: boolean;
  disabled?: boolean;
  label: string;
  detail?: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className={`flex items-center justify-between gap-5 py-3 ${disabled ? "opacity-45" : ""}`}>
      <span>
        <span className="block text-sm text-[#dfd6cb]">{label}</span>
        {detail ? <span className="mt-1 block text-xs leading-5 text-[#7f776e]">{detail}</span> : null}
      </span>
      <span className="relative shrink-0">
        <input
          checked={checked}
          className="peer sr-only"
          disabled={disabled}
          onChange={(event) => onChange(event.target.checked)}
          type="checkbox"
        />
        <span className="block h-6 w-11 rounded-full border border-white/[0.12] bg-white/[0.07] transition peer-checked:border-[#b98265]/60 peer-checked:bg-[#8f5d47] peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[#deb59d]" />
        <span className="absolute left-1 top-1 h-4 w-4 rounded-full bg-[#a49a8f] transition peer-checked:translate-x-5 peer-checked:bg-[#f4e6dc]" />
      </span>
    </label>
  );
}

export function Feedback({ error, notice }: { error: string | null; notice: string | null }) {
  if (!error && !notice) {
    return null;
  }
  return (
    <div
      aria-live="polite"
      className={`rounded-2xl border px-4 py-3 text-sm leading-5 ${
        error
          ? "border-[#b96f61]/30 bg-[#6a332b]/15 text-[#e4ada1]"
          : "border-[#b98265]/25 bg-[#8f5d47]/10 text-[#d8b9a8]"
      }`}
      role={error ? "alert" : "status"}
    >
      {error ?? notice}
    </div>
  );
}

export function EmptyExperience({
  icon,
  title,
  children,
  action
}: {
  icon: IconName;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center px-6 py-16 text-center">
      <div className="grid h-12 w-12 place-items-center rounded-full border border-[#b98265]/20 bg-[#b98265]/[0.07] text-[#c99578]">
        <Icon name={icon} />
      </div>
      <h2 className="mt-5 font-eidolon-display text-2xl text-[#eee5da]">{title}</h2>
      <div className="mt-3 text-sm leading-6 text-[#91887e]">{children}</div>
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}
