import type { AdultStatus, CharacterDraft, User } from "../types";
import { inputClass, primaryButtonClass, secondaryButtonClass } from "../ui";

export function AdultPanel({
  status,
  user,
  draft,
  setDraft,
  onToggleAgeGate,
  onSave
}: {
  status: AdultStatus | null;
  user: User;
  draft: CharacterDraft;
  setDraft: (value: CharacterDraft) => void;
  onToggleAgeGate: () => void;
  onSave: () => void;
}) {
  const parsedAge = Number.parseInt(draft.explicit_age, 10);
  const hasAdultAge = Number.isFinite(parsedAge) && parsedAge >= 18;

  function updateExplicitAge(value: string) {
    const nextAge = Number.parseInt(value, 10);
    const nextHasAdultAge = Number.isFinite(nextAge) && nextAge >= 18;
    setDraft({
      ...draft,
      explicit_age: value,
      adult_mode_allowed: nextHasAdultAge ? draft.adult_mode_allowed : false
    });
  }

  return (
    <>
      <div className="rounded-md border border-line bg-ink p-3 text-sm">
        <p>{status?.effective_mode === "adult" ? "Adult mode available" : "SFW enforced"}</p>
        <p className="mt-1 text-xs text-zinc-500">Intensity {status?.intensity ?? 0}/3</p>
        {status?.reasons.map((reason) => (
          <p className="mt-2 text-xs text-ember" key={reason}>
            {reason}
          </p>
        ))}
      </div>
      <button className={secondaryButtonClass} onClick={onToggleAgeGate} type="button">
        {user.age_gate_confirmed ? "Age gate confirmed" : "Confirm age gate"}
      </button>
      <div className="grid grid-cols-2 gap-2">
        <label className="block text-sm text-zinc-300">
          Age
          <input
            className={inputClass}
            value={draft.explicit_age}
            onChange={(event) => updateExplicitAge(event.target.value)}
            inputMode="numeric"
          />
        </label>
        <label className="block text-sm text-zinc-300">
          Intensity
          <select
            className={inputClass}
            value={draft.content_intensity}
            onChange={(event) => setDraft({ ...draft, content_intensity: event.target.value })}
          >
            <option value="0">0</option>
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3">3</option>
          </select>
        </label>
      </div>
      <label className="flex items-center gap-2 text-sm text-zinc-300">
          <input
            type="checkbox"
            checked={draft.adult_mode_allowed}
            disabled={!hasAdultAge}
            onChange={(event) => setDraft({ ...draft, adult_mode_allowed: event.target.checked })}
          />
          Character adult mode
      </label>
      {!hasAdultAge && (
        <p className="text-xs text-zinc-500">
          Adult mode requires an explicit character age of 18 or older.
        </p>
      )}
      <button className={primaryButtonClass} onClick={onSave} type="button">
        Save adult settings
      </button>
    </>
  );
}
