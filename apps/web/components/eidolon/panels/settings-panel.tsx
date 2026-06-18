import type { User } from "../types";
import { inputClass, primaryButtonClass, secondaryButtonClass } from "../ui";

export function SettingsPanel({
  user,
  displayName,
  setDisplayName,
  onSaveName,
  onLogout
}: {
  user: User;
  displayName: string;
  setDisplayName: (value: string) => void;
  onSaveName: () => void;
  onLogout: () => void;
}) {
  return (
    <>
      <section className="rounded-md border border-line bg-ink p-3 text-sm">
        <p className="font-medium">{user.email}</p>
        <p className="mt-1 text-xs text-zinc-500">
          Local account auth · {user.age_gate_confirmed ? "age gate confirmed" : "SFW gate active"}
        </p>
      </section>
      <label className="block text-sm text-zinc-300">
        Display name
        <input
          className={inputClass}
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
        />
      </label>
      <button className={primaryButtonClass} onClick={onSaveName} type="button">
        Save settings
      </button>
      <p className="rounded-md border border-line bg-ink p-3 text-xs leading-5 text-zinc-500">
        Logout clears the browser token only. PostgreSQL remains the source of truth for messages,
        memories, journals, relationship state, and scheduled jobs.
      </p>
      <button className={secondaryButtonClass} onClick={onLogout} type="button">
        Logout
      </button>
    </>
  );
}
