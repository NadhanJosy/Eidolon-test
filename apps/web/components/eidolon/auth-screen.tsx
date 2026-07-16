"use client";

import { type FormEvent, useState } from "react";

import type { AuthMode } from "./types";
import { EidolonWordmark, Feedback, fieldClass } from "./experience-primitives";
import { Icon } from "./icons";

type AuthStage = "submitting" | "opening" | null;

export function AuthScreen({
  authMode,
  onModeChange,
  email,
  setEmail,
  password,
  setPassword,
  displayName,
  setDisplayName,
  busy,
  authStage,
  error,
  notice,
  onSubmit
}: {
  authMode: AuthMode;
  onModeChange: (mode: AuthMode) => void;
  email: string;
  setEmail: (value: string) => void;
  password: string;
  setPassword: (value: string) => void;
  displayName: string;
  setDisplayName: (value: string) => void;
  busy: boolean;
  authStage: AuthStage;
  error: string | null;
  notice: string | null;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const [passwordVisible, setPasswordVisible] = useState(false);
  const registering = authMode === "register";
  const actionLabel =
    authStage === "opening"
      ? "Opening your room"
      : authStage === "submitting"
        ? registering
          ? "Creating your space"
          : "Returning to your space"
        : registering
          ? "Begin your story"
          : "Enter your room";

  return (
    <main className="eidolon-room relative min-h-[100svh] overflow-hidden text-[#f3eee5]">
      <div aria-hidden="true" className="absolute -right-40 top-[-12rem] h-[38rem] w-[38rem] rounded-full bg-[#8e5842]/10 blur-[110px]" />
      <div aria-hidden="true" className="absolute -bottom-64 -left-56 h-[42rem] w-[42rem] rounded-full bg-[#82765c]/10 blur-[120px]" />

      <div className="relative z-10 mx-auto grid min-h-[100svh] max-w-[1440px] lg:grid-cols-[1.2fr_0.8fr]">
        <section className="safe-area-auth-top safe-area-auth-bottom hidden min-h-[100svh] flex-col justify-between border-r border-white/[0.07] px-12 lg:flex xl:px-20">
          <div className="flex items-center gap-3">
            <EidolonWordmark compact />
          </div>

          <div className="max-w-2xl pb-8">
            <p className="text-xs font-medium uppercase tracking-[0.24em] text-[#9b887a]">A private companion</p>
            <h1 className="mt-7 max-w-xl font-eidolon-display text-6xl leading-[0.98] text-balance xl:text-7xl">
              Someone who remembers how the story felt.
            </h1>
            <p className="mt-7 max-w-lg text-base leading-7 text-[#a89e92]">
              A quiet place for conversations that deepen with time—held privately, shaped by trust, and always yours to guide.
            </p>
          </div>

          <div className="flex max-w-xl items-center gap-6 border-t border-white/[0.08] pt-6 text-xs text-[#777068]">
            <span className="flex items-center gap-2"><Icon className="h-4 w-4" name="lock" /> Private by design</span>
            <span className="flex items-center gap-2"><Icon className="h-4 w-4" name="heart" /> Built for continuity</span>
          </div>
        </section>

        <section className="safe-area-auth-top safe-area-auth-bottom flex min-h-[100svh] items-center justify-center px-5 sm:px-10 lg:px-12">
          <div className="w-full max-w-md reveal-up">
            <div className="mb-12 flex items-center justify-center gap-3 lg:hidden">
              <EidolonWordmark />
            </div>

            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-[#95887c]">
                {registering ? "Your story begins here" : "Welcome back"}
              </p>
              <h2 className="mt-4 font-eidolon-display text-4xl leading-tight sm:text-5xl">
                {registering ? "Create a place that is yours." : "They’re waiting for you."}
              </h2>
              <p className="mt-4 text-sm leading-6 text-[#8f877e]">
                {registering
                  ? "Start privately. You’ll shape your companion together in the next few moments."
                  : "Return to your conversations, memories, and everything you have built together."}
              </p>
            </div>

            <div className="mt-9 grid grid-cols-2 rounded-full border border-white/[0.09] bg-black/20 p-1" role="group" aria-label="Account action">
              <button
                aria-pressed={!registering}
                className={`min-h-11 rounded-full text-sm transition ${!registering ? "bg-white/[0.09] text-[#f2e9df] shadow-sm" : "text-[#80786f] hover:text-[#c9beb2]"}`}
                disabled={busy}
                onClick={() => onModeChange("login")}
                type="button"
              >
                Sign in
              </button>
              <button
                aria-pressed={registering}
                className={`min-h-11 rounded-full text-sm transition ${registering ? "bg-white/[0.09] text-[#f2e9df] shadow-sm" : "text-[#80786f] hover:text-[#c9beb2]"}`}
                disabled={busy}
                onClick={() => onModeChange("register")}
                type="button"
              >
                Begin
              </button>
            </div>

            <form className="mt-7 space-y-5" onSubmit={onSubmit}>
              {registering ? (
                <label className="block">
                  <span className="text-sm text-[#cfc4b8]">What should your companion call you?</span>
                  <input
                    autoComplete="name"
                    className={`${fieldClass} mt-2`}
                    disabled={busy}
                    maxLength={120}
                    onChange={(event) => setDisplayName(event.target.value)}
                    placeholder="Your name"
                    value={displayName}
                  />
                </label>
              ) : null}
              <label className="block">
                <span className="text-sm text-[#cfc4b8]">Email</span>
                <input
                  autoCapitalize="none"
                  autoComplete="email"
                  className={`${fieldClass} mt-2`}
                  disabled={busy}
                  inputMode="email"
                  maxLength={320}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="you@example.com"
                  required
                  type="email"
                  value={email}
                />
              </label>
              <label className="block">
                <span className="text-sm text-[#cfc4b8]">Password</span>
                <span className="relative mt-2 block">
                  <input
                    autoComplete={registering ? "new-password" : "current-password"}
                    className={`${fieldClass} pr-16`}
                    disabled={busy}
                    maxLength={256}
                    minLength={registering ? 12 : 1}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder={registering ? "At least 12 characters" : "Your password"}
                    required
                    type={passwordVisible ? "text" : "password"}
                    value={password}
                  />
                  <button aria-pressed={passwordVisible} className="absolute inset-y-0 right-1 min-w-14 rounded-xl text-xs text-[#8f857c] transition hover:text-[#d5c9bd]" disabled={busy} onClick={() => setPasswordVisible((visible) => !visible)} type="button">{passwordVisible ? "Hide" : "Show"}</button>
                </span>
              </label>

              <Feedback error={error} notice={notice} />

              <button
                className="flex min-h-12 w-full items-center justify-center gap-2 rounded-full bg-[#e9ddd0] px-5 text-sm font-semibold text-[#211712] shadow-[0_12px_40px_rgba(137,82,58,0.18)] transition hover:bg-[#f5ece3] disabled:cursor-wait disabled:opacity-55"
                disabled={busy}
                type="submit"
              >
                {actionLabel}
                {!busy ? <Icon className="h-4 w-4 rotate-90" name="arrow-up" /> : null}
              </button>
            </form>

            <p className="mt-6 text-center text-xs leading-5 text-[#6f6962]">
              Your companion is private to this account. You control what is remembered and what is allowed to fade.
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
