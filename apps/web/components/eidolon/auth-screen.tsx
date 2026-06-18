import type { Dispatch, SetStateAction } from "react";

import type { AuthMode, SubmitHandler } from "./types";
import { errorClass, inputClass, noticeClass, primaryButtonClass, tabClass } from "./ui";

export function AuthScreen({
  authMode,
  setAuthMode,
  email,
  setEmail,
  password,
  setPassword,
  displayName,
  setDisplayName,
  busy,
  error,
  notice,
  onSubmit
}: {
  authMode: AuthMode;
  setAuthMode: Dispatch<SetStateAction<AuthMode>>;
  email: string;
  setEmail: (value: string) => void;
  password: string;
  setPassword: (value: string) => void;
  displayName: string;
  setDisplayName: (value: string) => void;
  busy: boolean;
  error: string | null;
  notice: string | null;
  onSubmit: SubmitHandler;
}) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-ink px-4 py-8 text-paper">
      <section className="w-full max-w-md rounded-xl border border-line bg-panel/95 p-5 shadow-2xl shadow-black/40">
        <div className="mb-6 flex items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase text-zinc-500">Private text companion</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-normal">Eidolon</h1>
          </div>
          <div className="grid grid-cols-2 gap-1 rounded-lg border border-line bg-ink p-1">
            <button
              type="button"
              onClick={() => setAuthMode("login")}
              className={tabClass(authMode === "login")}
            >
              Login
            </button>
            <button
              type="button"
              onClick={() => setAuthMode("register")}
              className={tabClass(authMode === "register")}
            >
              Register
            </button>
          </div>
        </div>

        <form className="space-y-3" onSubmit={onSubmit}>
          <label className="block text-sm text-zinc-300">
            Email
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={inputClass}
              type="email"
              autoComplete="email"
            />
          </label>
          <label className="block text-sm text-zinc-300">
            Password
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={inputClass}
              type="password"
              autoComplete={authMode === "register" ? "new-password" : "current-password"}
            />
          </label>
          {authMode === "register" ? (
            <label className="block text-sm text-zinc-300">
              Name
              <input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                className={inputClass}
                autoComplete="name"
              />
            </label>
          ) : null}
          {error ? <p className={errorClass}>{error}</p> : null}
          {notice ? <p className={noticeClass}>{notice}</p> : null}
          <button className={`${primaryButtonClass} w-full`} disabled={busy} type="submit">
            {busy ? "Working" : authMode === "register" ? "Create account" : "Enter"}
          </button>
        </form>
      </section>
    </main>
  );
}
