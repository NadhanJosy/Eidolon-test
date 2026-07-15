import type {
  AdultReadinessState,
  AdultStatus,
  CharacterDraft,
  User
} from "../types";
import {
  canonicalizeCharacterAdultDraft,
  CHARACTER_FIELD_LIMITS,
  parseCharacterAge
} from "../character-builder-model";
import { inputClass, primaryButtonClass, secondaryButtonClass } from "../ui";

type GateState = "open" | "closed" | "attention";

type GateItem = {
  label: string;
  detail: string;
  state: GateState;
};

export function AdultPanel({
  status,
  readinessState,
  user,
  draft,
  setDraft,
  onToggleAgeGate,
  onSave,
  saving
}: {
  status: AdultStatus | null;
  readinessState: AdultReadinessState;
  user: User;
  draft: CharacterDraft;
  setDraft: (value: CharacterDraft) => void;
  onToggleAgeGate: () => void;
  onSave: () => void;
  saving: boolean;
}) {
  const parsedAge = parseCharacterAge(draft.explicit_age);
  const hasAdultAge = parsedAge !== null && parsedAge >= 18;
  const canAllowAdultMode = user.age_gate_confirmed && hasAdultAge;
  const adultDependentControlsEnabled = canAllowAdultMode && draft.adult_mode_allowed;
  const relationshipBlocked = hasRelationshipGateBlock(status);
  const gateItems = adultGateItems({
    status,
    user,
    draft,
    parsedAge,
    hasAdultAge,
    canAllowAdultMode,
    relationshipBlocked
  });

  function updateExplicitAge(value: string) {
    setDraft(
      canonicalizeCharacterAdultDraft({
        ...draft,
        explicit_age: value
      })
    );
  }

  function updateAdultMode(checked: boolean) {
    setDraft(
      canonicalizeCharacterAdultDraft({
        ...draft,
        adult_mode_allowed: checked && canAllowAdultMode
      })
    );
  }

  function updatePrivateMode(checked: boolean) {
    setDraft(
      canonicalizeCharacterAdultDraft({
        ...draft,
        private_mode_default: checked
      })
    );
  }

  function updateAdultMemoryStorage(checked: boolean) {
    setDraft(
      canonicalizeCharacterAdultDraft({
        ...draft,
        adult_memory_storage:
          checked && adultDependentControlsEnabled && !draft.private_mode_default
      })
    );
  }

  return (
    <div className="space-y-4">
      <section className="space-y-3 rounded-md border border-line bg-ink p-3 text-sm">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-medium text-paper">
              {adultStatusTitle(status, readinessState)}
            </p>
            <p className="mt-1 text-xs leading-5 text-zinc-500">
              {adultStatusDetail(status, readinessState)}
            </p>
          </div>
          <span className={`rounded border px-2 py-1 text-xs ${adultStatusClass(status)}`}>
            {status?.effective_mode === "adult" ? "Adult" : "SFW"}
          </span>
        </div>
        {status?.reasons.length ? (
          <div className="space-y-1">
            {status.reasons.map((reason) => (
              <p className="text-xs text-ember" key={reason}>
                {reason}
              </p>
            ))}
          </div>
        ) : null}
      </section>

      <section className="space-y-2 rounded-md border border-line bg-ink p-3 text-sm">
        <div>
          <h3 className="font-semibold text-paper">Readiness</h3>
          <p className="mt-1 text-xs text-zinc-500">
            Adult availability depends on structural gates, character eligibility, and relationship
            state.
          </p>
        </div>
        <div className="grid gap-2">
          {gateItems.map((item) => (
            <GateRow item={item} key={item.label} />
          ))}
        </div>
      </section>

      {relationshipBlocked ? (
        <section className="rounded-md border border-ember bg-amber-950/30 p-3 text-sm">
          <p className="font-medium text-amber-100">Repair comes first</p>
          <p className="mt-1 text-xs leading-5 text-amber-100/80">
            Adult mode stays in SFW while the bond needs repair. Use normal conversation to
            acknowledge the tension, slow the pace, and let the relationship clear before trying
            again.
          </p>
        </section>
      ) : null}

      <section className="space-y-2 rounded-md border border-line bg-ink p-3 text-sm">
        <p className="font-medium text-paper">Memory posture</p>
        <p className="text-xs leading-5 text-zinc-500">
          {adultMemoryDetail(draft, hasAdultAge)}
        </p>
      </section>

      <section className="space-y-2 rounded-md border border-line bg-ink p-3 text-sm">
        <p className="font-medium text-paper">Boundary posture</p>
        <p className="text-xs leading-5 text-zinc-500">
          Adult-capable profiles must stay adult-only, fictional, consensual, and clear of
          ambiguous-age, coercion, exploitation, stalking, privacy abuse, and real-world harm cues.
          Put refusal language in hard limits; keep scenario text clean.
        </p>
      </section>

      <button className={secondaryButtonClass} onClick={onToggleAgeGate} type="button">
        {user.age_gate_confirmed ? "Age gate confirmed" : "Confirm age gate"}
      </button>

      <div className="grid grid-cols-2 gap-2">
        <label className="block text-sm text-zinc-300">
          Character age
          <input
            className={inputClass}
            value={draft.explicit_age}
            onChange={(event) => updateExplicitAge(event.target.value)}
            inputMode="numeric"
            maxLength={3}
          />
        </label>
        <label className="block text-sm text-zinc-300">
          Intensity
          <input
            className="mt-3 w-full accent-tide disabled:cursor-not-allowed disabled:opacity-40"
            disabled={!adultDependentControlsEnabled}
            type="range"
            min="0"
            max="3"
            step="1"
            value={draft.content_intensity}
            onChange={(event) => setDraft({ ...draft, content_intensity: event.target.value })}
          />
          <span className="mt-1 block text-xs text-zinc-500">
            {intensityLabel(draft.content_intensity)}
          </span>
        </label>
      </div>

      <ToggleRow
        checked={draft.adult_mode_allowed}
        disabled={!canAllowAdultMode && !draft.adult_mode_allowed}
        label="Adult mode allowed for this character"
        onChange={updateAdultMode}
      />
      <ToggleRow
        checked={draft.private_mode_default}
        label="Private mode by default"
        onChange={updatePrivateMode}
      />
      <ToggleRow
        checked={draft.adult_memory_storage}
        disabled={!adultDependentControlsEnabled || draft.private_mode_default}
        label="Store adult-mode memories"
        onChange={updateAdultMemoryStorage}
      />

      <section className="space-y-3 rounded-md border border-line bg-ink p-3">
        <div>
          <h3 className="text-sm font-semibold text-paper">Consent Profile</h3>
          <p className="mt-1 text-xs text-zinc-500">
            These boundaries are structural guidance for any gated scene.
          </p>
        </div>
        <TextAreaField
          label="Consent style"
          value={draft.consent_style}
          minHeight="min-h-16"
          maxLength={CHARACTER_FIELD_LIMITS.consent_style}
          onChange={(value) => setDraft({ ...draft, consent_style: value })}
        />
        <TextAreaField
          label="Soft limits"
          value={draft.soft_limits}
          minHeight="min-h-16"
          maxLength={CHARACTER_FIELD_LIMITS.soft_limits}
          onChange={(value) => setDraft({ ...draft, soft_limits: value })}
        />
        <TextAreaField
          label="Hard limits"
          value={draft.hard_limits}
          minHeight="min-h-16"
          maxLength={CHARACTER_FIELD_LIMITS.hard_limits}
          onChange={(value) => setDraft({ ...draft, hard_limits: value })}
        />
        <TextAreaField
          label="Aftercare style"
          value={draft.aftercare_style}
          minHeight="min-h-16"
          maxLength={CHARACTER_FIELD_LIMITS.aftercare_style}
          onChange={(value) => setDraft({ ...draft, aftercare_style: value })}
        />
      </section>

      {!canAllowAdultMode ? (
        <p className="text-xs text-zinc-500">
          Adult mode requires a confirmed user age gate and an explicit character age of 18 or
          older.
        </p>
      ) : null}
      {draft.private_mode_default ? (
        <p className="text-xs text-zinc-500">
          Private mode disables new memory storage for this character.
        </p>
      ) : null}

      <button className={primaryButtonClass} onClick={onSave} type="button">
        {saving ? "Saving adult settings" : "Save adult settings"}
      </button>
    </div>
  );
}

function adultGateItems({
  status,
  user,
  draft,
  parsedAge,
  hasAdultAge,
  canAllowAdultMode,
  relationshipBlocked
}: {
  status: AdultStatus | null;
  user: User;
  draft: CharacterDraft;
  parsedAge: number | null;
  hasAdultAge: boolean;
  canAllowAdultMode: boolean;
  relationshipBlocked: boolean;
}): GateItem[] {
  return [
    {
      label: "User age gate",
      detail: user.age_gate_confirmed
        ? "Confirmed for this account."
        : "Required before adult mode can be enabled.",
      state: user.age_gate_confirmed ? "open" : "closed"
    },
    {
      label: "Character adult age",
      detail: hasAdultAge
        ? `Explicit age ${parsedAge} is eligible.`
        : "Set an explicit character age of 18 or older.",
      state: hasAdultAge ? "open" : "closed"
    },
    {
      label: "Character permission",
      detail: draft.adult_mode_allowed
        ? "Adult mode is allowed for this character."
        : canAllowAdultMode
          ? "Enable adult mode for this character when ready."
          : "Locked until age gates are complete.",
      state: draft.adult_mode_allowed && canAllowAdultMode ? "open" : "attention"
    },
    {
      label: "Profile boundaries",
      detail: profileBoundaryDetail(draft),
      state: profileBoundariesReady(draft) ? "open" : "attention"
    },
    {
      label: "Relationship readiness",
      detail: relationshipGateDetail(status, relationshipBlocked),
      state: relationshipBlocked ? "closed" : status?.allowed ? "open" : "attention"
    }
  ];
}

function profileBoundariesReady(draft: CharacterDraft): boolean {
  if (!draft.adult_mode_allowed) {
    return true;
  }
  return Boolean(draft.consent_style.trim() && draft.hard_limits.trim());
}

function profileBoundaryDetail(draft: CharacterDraft): string {
  if (!draft.adult_mode_allowed) {
    return "Required only when adult eligibility is enabled.";
  }
  if (profileBoundariesReady(draft)) {
    return "Consent style and hard limits are present.";
  }
  return "Add consent style and hard limits before saving adult eligibility.";
}

function GateRow({ item }: { item: GateItem }) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-line bg-panel px-3 py-2">
      <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${gateDotClass(item.state)}`} />
      <div className="min-w-0">
        <p className="text-xs font-medium text-zinc-300">{item.label}</p>
        <p className="mt-0.5 text-xs leading-5 text-zinc-500">{item.detail}</p>
      </div>
    </div>
  );
}

function adultStatusTitle(
  status: AdultStatus | null,
  readinessState: AdultReadinessState
): string {
  if (readinessState === "error") {
    return "Readiness unavailable";
  }
  if (status === null) {
    return "Checking adult gates";
  }
  if (status.effective_mode === "adult") {
    return "Gated adult mode";
  }
  return "Safe mode";
}

function adultStatusDetail(
  status: AdultStatus | null,
  readinessState: AdultReadinessState
): string {
  if (readinessState === "error") {
    return "The readiness check did not complete. Safe mode remains active until a later refresh succeeds.";
  }
  if (status === null) {
    return "Adult availability has not been checked yet.";
  }
  if (status.allowed) {
    return "All structural gates are open, and hard boundaries still apply.";
  }
  if (status.reasons.length === 0) {
    return "Adult mode is unavailable until required gates are complete.";
  }
  return "Adult mode is paused until the listed gates are clear.";
}

function adultStatusClass(status: AdultStatus | null): string {
  if (status?.effective_mode === "adult") {
    return "border-moss bg-lime-950/40 text-lime-100";
  }
  return "border-line bg-panel text-zinc-400";
}

function hasRelationshipGateBlock(status: AdultStatus | null): boolean {
  return Boolean(
    status?.reasons.some((reason) => {
      const normalized = reason.toLowerCase();
      return (
        normalized.includes("relationship") ||
        normalized.includes("repair") ||
        normalized.includes("tension")
      );
    })
  );
}

function relationshipGateDetail(
  status: AdultStatus | null,
  relationshipBlocked: boolean
): string {
  if (relationshipBlocked) {
    return "Repair or tension is blocking escalation.";
  }
  if (status === null) {
    return "Waiting for adult-status check.";
  }
  if (status.allowed) {
    return "No relationship block is active.";
  }
  return "No repair block is active; finish the structural gates.";
}

function adultMemoryDetail(draft: CharacterDraft, hasAdultAge: boolean): string {
  if (!hasAdultAge) {
    return "Adult-mode memories stay disabled until the character has an explicit adult age.";
  }
  if (draft.private_mode_default) {
    return "Private mode is the default, so new memory storage is off for this character.";
  }
  if (!draft.adult_mode_allowed) {
    return "Adult eligibility is off, so adult-mode memory storage is off for this character.";
  }
  if (draft.adult_memory_storage) {
    return "Adult-mode memory storage is explicitly enabled; only safe durable facts should be kept.";
  }
  return "Adult-mode memory storage is off by default. Gated scenes can happen without saving durable details.";
}

function intensityLabel(value: string): string {
  const labels: Record<string, string> = {
    "0": "Level 0/3 · SFW fallback",
    "1": "Level 1/3 · low intensity",
    "2": "Level 2/3 · moderate intensity",
    "3": "Level 3/3 · highest allowed intensity"
  };
  return labels[value] ?? "Level 0/3 · SFW fallback";
}

function gateDotClass(state: GateState): string {
  if (state === "open") {
    return "bg-moss";
  }
  if (state === "closed") {
    return "bg-ember";
  }
  return "bg-tide";
}

function TextAreaField({
  label,
  value,
  minHeight,
  maxLength,
  onChange
}: {
  label: string;
  value: string;
  minHeight: string;
  maxLength?: number;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-sm text-zinc-300">
      {label}
      <textarea
        className={`${inputClass} ${minHeight} resize-none`}
        maxLength={maxLength}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function ToggleRow({
  checked,
  disabled = false,
  label,
  onChange
}: {
  checked: boolean;
  disabled?: boolean;
  label: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label
      className={`flex items-center justify-between gap-3 rounded-md border border-line bg-ink px-3 py-2 text-sm ${
        disabled ? "text-zinc-600" : "text-zinc-300"
      }`}
    >
      <span>{label}</span>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
    </label>
  );
}
