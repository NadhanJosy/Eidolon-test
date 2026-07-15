import {
  canonicalizeCharacterAdultDraft,
  CHARACTER_FIELD_LIMITS,
  resolvedDeviceTimeZone,
  SCENARIO_PRESETS
} from "../character-builder-model";
import type { CharacterDraft } from "../types";
import { inputClass, primaryButtonClass, secondaryButtonClass } from "../ui";

export function CharacterPanel({
  draft,
  setDraft,
  onSave,
  saving
}: {
  draft: CharacterDraft;
  setDraft: (value: CharacterDraft) => void;
  onSave: () => void;
  saving: boolean;
}) {
  function setPresenceSnooze(hours: number) {
    const snoozedUntil = new Date(Date.now() + hours * 60 * 60 * 1000).toISOString();
    setDraft({ ...draft, proactive_snoozed_until: snoozedUntil });
  }

  function clearPresenceSnooze() {
    setDraft({ ...draft, proactive_snoozed_until: "" });
  }

  function updateExplicitAge(value: string) {
    setDraft(
      canonicalizeCharacterAdultDraft({
        ...draft,
        explicit_age: value
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

  return (
    <div className="space-y-5">
      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-paper">Identity</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField
            label="Name"
            maxLength={CHARACTER_FIELD_LIMITS.name}
            value={draft.name}
            onChange={(value) => setDraft({ ...draft, name: value })}
          />
          <TextField
            label="Explicit age"
            value={draft.explicit_age}
            inputMode="numeric"
            maxLength={3}
            onChange={updateExplicitAge}
          />
        </div>
        <TextAreaField
          label="Description"
          value={draft.description}
          minHeight="min-h-20"
          maxLength={CHARACTER_FIELD_LIMITS.description}
          onChange={(value) => setDraft({ ...draft, description: value })}
        />
        <TextField
          label="Relationship type"
          maxLength={CHARACTER_FIELD_LIMITS.relationship_type}
          value={draft.relationship_type}
          onChange={(value) => setDraft({ ...draft, relationship_type: value })}
        />
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-paper">Inner Life</h3>
        <TextAreaField
          label="Personality core"
          maxLength={CHARACTER_FIELD_LIMITS.personality_core}
          value={draft.personality_core}
          onChange={(value) => setDraft({ ...draft, personality_core: value })}
        />
        <TextAreaField
          label="Flaws"
          value={draft.flaws}
          minHeight="min-h-16"
          maxLength={CHARACTER_FIELD_LIMITS.flaws}
          onChange={(value) => setDraft({ ...draft, flaws: value })}
        />
        <TextAreaField
          label="Values"
          value={draft.values}
          minHeight="min-h-16"
          maxLength={CHARACTER_FIELD_LIMITS.values}
          onChange={(value) => setDraft({ ...draft, values: value })}
        />
        <TextAreaField
          label="Backstory"
          maxLength={CHARACTER_FIELD_LIMITS.backstory}
          value={draft.backstory}
          onChange={(value) => setDraft({ ...draft, backstory: value })}
        />
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-paper">Voice</h3>
        <TextAreaField
          label="Speech style"
          value={draft.speech_style}
          minHeight="min-h-16"
          maxLength={CHARACTER_FIELD_LIMITS.speech_style}
          onChange={(value) => setDraft({ ...draft, speech_style: value })}
        />
        <TextField
          label="Humor style"
          maxLength={CHARACTER_FIELD_LIMITS.humor_style}
          value={draft.humor_style}
          onChange={(value) => setDraft({ ...draft, humor_style: value })}
        />
        <TextAreaField
          label="Greeting"
          value={draft.greeting}
          minHeight="min-h-16"
          maxLength={CHARACTER_FIELD_LIMITS.greeting}
          onChange={(value) => setDraft({ ...draft, greeting: value })}
        />
        <TextField
          label="Nicknames"
          maxLength={CHARACTER_FIELD_LIMITS.nicknames}
          value={draft.nicknames}
          onChange={(value) => setDraft({ ...draft, nicknames: value })}
        />
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-paper">World</h3>
        <TextAreaField
          label="Interests"
          value={draft.interests}
          minHeight="min-h-16"
          maxLength={CHARACTER_FIELD_LIMITS.interests}
          onChange={(value) => setDraft({ ...draft, interests: value })}
        />
        <ScenarioPresetPicker
          value={draft.scenario_preset}
          onChange={(value) => setDraft({ ...draft, scenario_preset: value })}
        />
        <TextField
          label="Custom scenario"
          maxLength={CHARACTER_FIELD_LIMITS.scenario_preset}
          value={draft.scenario_preset}
          onChange={(value) => setDraft({ ...draft, scenario_preset: value })}
        />
        <TextAreaField
          label="Boundaries"
          maxLength={CHARACTER_FIELD_LIMITS.boundary_notes}
          value={draft.boundary_notes}
          onChange={(value) => setDraft({ ...draft, boundary_notes: value })}
        />
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-paper">Memory</h3>
        <ToggleRow
          checked={draft.remember_preferences}
          label="Remember preferences"
          onChange={(checked) => setDraft({ ...draft, remember_preferences: checked })}
        />
        <ToggleRow
          checked={draft.remember_emotional_notes}
          label="Remember emotional notes"
          onChange={(checked) => setDraft({ ...draft, remember_emotional_notes: checked })}
        />
        <ToggleRow
          checked={draft.private_mode_default}
          label="Private mode by default"
          onChange={updatePrivateMode}
        />
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-paper">Presence</h3>
        <ToggleRow
          checked={draft.proactive_enabled}
          label="Allow companion notes"
          onChange={(checked) => setDraft({ ...draft, proactive_enabled: checked })}
        />
        <TextField
          inputMode="numeric"
          label="Minimum hours between notes"
          maxLength={CHARACTER_FIELD_LIMITS.proactive_cooldown_hours}
          value={draft.proactive_cooldown_hours}
          onChange={(value) => setDraft({ ...draft, proactive_cooldown_hours: value })}
        />
        <div className="rounded-md border border-line bg-ink p-3 text-sm text-zinc-300">
          <p className="text-xs text-zinc-500">
            {presenceSnoozeLabel(draft.proactive_snoozed_until)}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              className={secondaryButtonClass}
              onClick={() => setPresenceSnooze(24)}
              type="button"
            >
              Snooze 24h
            </button>
            <button
              className={secondaryButtonClass}
              onClick={() => setPresenceSnooze(24 * 7)}
              type="button"
            >
              Snooze 7d
            </button>
            <button className={secondaryButtonClass} onClick={clearPresenceSnooze} type="button">
              Clear snooze
            </button>
          </div>
        </div>
        <div className="rounded-md border border-line bg-ink p-3">
          <div className="flex flex-wrap items-end gap-2">
            <div className="min-w-56 flex-1">
              <TextField
                label="Your timezone"
                maxLength={CHARACTER_FIELD_LIMITS.proactive_timezone}
                value={draft.proactive_timezone}
                onChange={(value) => setDraft({ ...draft, proactive_timezone: value })}
              />
            </div>
            <button
              className={secondaryButtonClass}
              onClick={() =>
                setDraft({ ...draft, proactive_timezone: resolvedDeviceTimeZone() })
              }
              type="button"
            >
              Use device timezone
            </button>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <TextField
              label="Morning note time"
              onChange={(value) => setDraft({ ...draft, morning_time: value })}
              type="time"
              value={draft.morning_time}
            />
            <TextField
              label="Goodnight note time"
              onChange={(value) => setDraft({ ...draft, goodnight_time: value })}
              type="time"
              value={draft.goodnight_time}
            />
            <TextField
              label="Quiet hours begin"
              onChange={(value) => setDraft({ ...draft, quiet_hours_start: value })}
              type="time"
              value={draft.quiet_hours_start}
            />
            <TextField
              label="Quiet hours end"
              onChange={(value) => setDraft({ ...draft, quiet_hours_end: value })}
              type="time"
              value={draft.quiet_hours_end}
            />
          </div>
        </div>
        <div className="grid gap-2">
          <ToggleRow
            checked={draft.allow_inactivity_checkins}
            disabled={!draft.proactive_enabled}
            label="Quiet check-ins"
            onChange={(checked) => setDraft({ ...draft, allow_inactivity_checkins: checked })}
          />
          <ToggleRow
            checked={draft.allow_morning_notes}
            disabled={!draft.proactive_enabled}
            label="Morning notes"
            onChange={(checked) => setDraft({ ...draft, allow_morning_notes: checked })}
          />
          <ToggleRow
            checked={draft.allow_goodnight_notes}
            disabled={!draft.proactive_enabled}
            label="Goodnight notes"
            onChange={(checked) => setDraft({ ...draft, allow_goodnight_notes: checked })}
          />
          <ToggleRow
            checked={draft.allow_thinking_of_you}
            disabled={!draft.proactive_enabled}
            label="Thinking-of-you notes"
            onChange={(checked) => setDraft({ ...draft, allow_thinking_of_you: checked })}
          />
          <ToggleRow
            checked={draft.allow_milestone_notes}
            disabled={!draft.proactive_enabled}
            label="Milestone notes"
            onChange={(checked) => setDraft({ ...draft, allow_milestone_notes: checked })}
          />
          <ToggleRow
            checked={draft.allow_unresolved_thread_nudges}
            disabled={!draft.proactive_enabled}
            label="Open-thread follow-ups"
            onChange={(checked) =>
              setDraft({ ...draft, allow_unresolved_thread_nudges: checked })
            }
          />
          <ToggleRow
            checked={draft.allow_delayed_double_texts}
            disabled={!draft.proactive_enabled}
            label="Delayed follow-ups"
            onChange={(checked) => setDraft({ ...draft, allow_delayed_double_texts: checked })}
          />
          <ToggleRow
            checked={draft.allow_manual_notes}
            disabled={!draft.proactive_enabled}
            label="Manual check-in button"
            onChange={(checked) => setDraft({ ...draft, allow_manual_notes: checked })}
          />
        </div>
      </section>

      <button className={primaryButtonClass} onClick={onSave} type="button">
        {saving ? "Saving character" : "Save character"}
      </button>
    </div>
  );
}

function ScenarioPresetPicker({
  value,
  onChange
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const normalizedValue = normalizeScenario(value);

  return (
    <div className="space-y-2">
      <p className="text-sm text-zinc-300">Scenario preset</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {SCENARIO_PRESETS.map((preset) => {
          const selected = normalizeScenario(preset.value) === normalizedValue;
          return (
            <button
              aria-pressed={selected}
              className={`min-h-24 rounded-md border p-3 text-left transition ${
                selected
                  ? "border-paper bg-paper text-ink shadow-sm shadow-black/20"
                  : "border-line bg-ink text-zinc-300 hover:border-zinc-400"
              }`}
              key={preset.label}
              onClick={() => onChange(preset.value)}
              type="button"
            >
              <span className="block text-sm font-semibold">{preset.label}</span>
              <span
                className={`mt-2 block text-xs leading-5 ${
                  selected ? "text-zinc-700" : "text-zinc-500"
                }`}
              >
                {preset.detail}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function TextField({
  label,
  value,
  inputMode,
  maxLength,
  type = "text",
  onChange
}: {
  label: string;
  value: string;
  inputMode?: "numeric";
  maxLength?: number;
  type?: "text" | "time";
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-sm text-zinc-300">
      {label}
      <input
        className={inputClass}
        inputMode={inputMode}
        maxLength={maxLength}
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function TextAreaField({
  label,
  value,
  minHeight = "min-h-24",
  maxLength,
  onChange
}: {
  label: string;
  value: string;
  minHeight?: string;
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

function normalizeScenario(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

function presenceSnoozeLabel(value: string): string {
  if (!value) {
    return "Companion notes are not snoozed.";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime()) || parsed <= new Date()) {
    return "Snooze has expired.";
  }
  return `Snoozed until ${parsed.toLocaleString()}.`;
}
