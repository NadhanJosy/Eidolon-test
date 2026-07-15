import type { RefObject } from "react";

import {
  BuilderArea,
  BuilderField,
  BuilderSection,
  BuilderSelect,
  type BuilderStepProps,
  BuilderToggle
} from "./character-builder-fields";
import {
  CHARACTER_FIELD_LIMITS,
  resolvedDeviceTimeZone,
  SCENARIO_PRESETS
} from "./character-builder-model";
import type { CharacterDraft } from "./types";

export function IdentityStep({
  draft,
  errors,
  firstFieldRef,
  adultAgeReady,
  onAgeChange,
  onAdultEligibilityChange,
  onChange
}: BuilderStepProps & {
  firstFieldRef: RefObject<HTMLInputElement | null>;
  adultAgeReady: boolean;
  onAgeChange: (value: string) => void;
  onAdultEligibilityChange: (enabled: boolean) => void;
}) {
  return (
    <BuilderSection
      eyebrow="Presence"
      title="Who enters the room?"
      summary="A name, a relational posture, and the first outline of who they are."
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <BuilderField
          error={errors.name}
          field="name"
          label="Name"
          maxLength={CHARACTER_FIELD_LIMITS.name}
          onChange={(value) => onChange("name", value)}
          required
          value={draft.name}
          inputRef={firstFieldRef}
        />
        <BuilderField
          error={errors.relationship_type}
          field="relationship_type"
          label="Relationship type"
          maxLength={CHARACTER_FIELD_LIMITS.relationship_type}
          onChange={(value) => onChange("relationship_type", value)}
          required
          value={draft.relationship_type}
        />
      </div>
      <BuilderArea
        error={errors.description}
        field="description"
        label="One-line presence"
        maxLength={CHARACTER_FIELD_LIMITS.description}
        onChange={(value) => onChange("description", value)}
        rows={3}
        value={draft.description}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <BuilderField
          error={errors.explicit_age}
        field="explicit_age"
        inputMode="numeric"
        label="Explicit age"
        maxLength={3}
        onChange={onAgeChange}
          value={draft.explicit_age}
        />
        <BuilderToggle
          checked={draft.adult_mode_allowed}
          detail={
            adultAgeReady
              ? "Allows the separate age, consent, relationship, and safety gates to evaluate."
              : "Available only with an explicit age of 18 or older."
          }
          error={errors.adult_mode_allowed}
          label="Eligible for gated adult mode"
          onChange={onAdultEligibilityChange}
        />
      </div>
    </BuilderSection>
  );
}

export function InnerLifeStep({ draft, errors, onChange }: BuilderStepProps) {
  return (
    <BuilderSection
      eyebrow="Inner life"
      title="Give them a point of view"
      summary="Temperament becomes convincing when strengths, flaws, and values can pull against each other."
    >
      <BuilderArea
        error={errors.personality_core}
        field="personality_core"
        label="Personality core"
        maxLength={CHARACTER_FIELD_LIMITS.personality_core}
        onChange={(value) => onChange("personality_core", value)}
        required
        rows={4}
        value={draft.personality_core}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <BuilderArea
          error={errors.worldview}
          field="worldview"
          label="Worldview"
          maxLength={CHARACTER_FIELD_LIMITS.worldview}
          onChange={(value) => onChange("worldview", value)}
          required
          rows={4}
          value={draft.worldview}
        />
        <BuilderArea
          error={errors.temperament}
          field="temperament"
          label="Temperament"
          maxLength={CHARACTER_FIELD_LIMITS.temperament}
          onChange={(value) => onChange("temperament", value)}
          required
          rows={4}
          value={draft.temperament}
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <BuilderArea
          error={errors.flaws}
          field="flaws"
          label="Flaws"
          maxLength={CHARACTER_FIELD_LIMITS.flaws}
          onChange={(value) => onChange("flaws", value)}
          rows={4}
          value={draft.flaws}
        />
        <BuilderArea
          error={errors.values}
          field="values"
          label="Values"
          maxLength={CHARACTER_FIELD_LIMITS.values}
          onChange={(value) => onChange("values", value)}
          rows={4}
          value={draft.values}
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <BuilderArea
          error={errors.affection_style}
          field="affection_style"
          label="Affection style"
          maxLength={CHARACTER_FIELD_LIMITS.affection_style}
          onChange={(value) => onChange("affection_style", value)}
          required
          rows={3}
          value={draft.affection_style}
        />
        <BuilderArea
          error={errors.conflict_style}
          field="conflict_style"
          label="Conflict and repair style"
          maxLength={CHARACTER_FIELD_LIMITS.conflict_style}
          onChange={(value) => onChange("conflict_style", value)}
          required
          rows={3}
          value={draft.conflict_style}
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <BuilderArea
          error={errors.insecurities}
          field="insecurities"
          label="Insecurities"
          maxLength={CHARACTER_FIELD_LIMITS.insecurities}
          onChange={(value) => onChange("insecurities", value)}
          rows={3}
          value={draft.insecurities}
        />
        <BuilderArea
          error={errors.habits}
          field="habits"
          label="Conversational habits"
          maxLength={CHARACTER_FIELD_LIMITS.habits}
          onChange={(value) => onChange("habits", value)}
          rows={3}
          value={draft.habits}
        />
      </div>
      <BuilderArea
        error={errors.initiative_style}
        field="initiative_style"
        label="Initiative style"
        maxLength={CHARACTER_FIELD_LIMITS.initiative_style}
        onChange={(value) => onChange("initiative_style", value)}
        required
        rows={3}
        value={draft.initiative_style}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <BuilderSelect
          error={errors.relationship_path}
          field="relationship_path"
          label="Relationship path"
          onChange={(value) =>
            onChange("relationship_path", value as CharacterDraft["relationship_path"])
          }
          options={[
            { label: "Friendship", value: "friendship" },
            { label: "Romantic, if earned", value: "romantic" },
            { label: "Custom", value: "custom" }
          ]}
          value={draft.relationship_path}
        />
        <BuilderSelect
          error={errors.emoji_style}
          field="emoji_style"
          label="Emoji use"
          onChange={(value) =>
            onChange("emoji_style", value as CharacterDraft["emoji_style"])
          }
          options={[
            { label: "None", value: "none" },
            { label: "Rare", value: "rare" },
            { label: "Light", value: "light" },
            { label: "Expressive", value: "expressive" }
          ]}
          value={draft.emoji_style}
        />
      </div>
      {draft.relationship_path === "custom" ? (
        <BuilderArea
          error={errors.custom_relationship}
          field="custom_relationship"
          label="Custom relationship path"
          maxLength={CHARACTER_FIELD_LIMITS.custom_relationship}
          onChange={(value) => onChange("custom_relationship", value)}
          required
          rows={3}
          value={draft.custom_relationship}
        />
      ) : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <BuilderArea
          error={errors.speech_style}
          field="speech_style"
          label="Speech style"
          maxLength={CHARACTER_FIELD_LIMITS.speech_style}
          onChange={(value) => onChange("speech_style", value)}
          required
          rows={3}
          value={draft.speech_style}
        />
        <BuilderArea
          error={errors.humor_style}
          field="humor_style"
          label="Humor style"
          maxLength={CHARACTER_FIELD_LIMITS.humor_style}
          onChange={(value) => onChange("humor_style", value)}
          rows={3}
          value={draft.humor_style}
        />
      </div>
    </BuilderSection>
  );
}

export function WorldStep({ draft, errors, onChange }: BuilderStepProps) {
  return (
    <BuilderSection
      eyebrow="Shared world"
      title="Set the first piece of continuity"
      summary="These details ground callbacks without pretending a history that has not happened."
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <BuilderArea
          error={errors.interests}
          field="interests"
          label="Interests"
          maxLength={CHARACTER_FIELD_LIMITS.interests}
          onChange={(value) => onChange("interests", value)}
          rows={3}
          value={draft.interests}
        />
        <BuilderArea
          error={errors.nicknames}
          field="nicknames"
          label="Nickname posture"
          maxLength={CHARACTER_FIELD_LIMITS.nicknames}
          onChange={(value) => onChange("nicknames", value)}
          rows={3}
          value={draft.nicknames}
        />
      </div>
      <BuilderArea
        error={errors.backstory}
        field="backstory"
        label="Backstory"
        maxLength={CHARACTER_FIELD_LIMITS.backstory}
        onChange={(value) => onChange("backstory", value)}
        rows={4}
        value={draft.backstory}
      />
      <BuilderArea
        error={errors.greeting}
        field="greeting"
        label="Opening line"
        maxLength={CHARACTER_FIELD_LIMITS.greeting}
        onChange={(value) => onChange("greeting", value)}
        required
        rows={3}
        value={draft.greeting}
      />
      <div className="space-y-2">
        <p className="text-sm text-zinc-300">Opening scenario</p>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {SCENARIO_PRESETS.map((preset) => {
            const selected = normalizeText(preset.value) === normalizeText(draft.scenario_preset);
            return (
              <button
                aria-pressed={selected}
                className={`min-h-24 rounded-md border p-3 text-left ${
                  selected
                    ? "border-paper bg-paper text-ink"
                    : "border-line bg-ink text-zinc-300 hover:border-zinc-400"
                }`}
                key={preset.label}
                onClick={() => onChange("scenario_preset", preset.value)}
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
      <BuilderArea
        error={errors.scenario_preset}
        field="scenario_preset"
        label="Scenario text"
        maxLength={CHARACTER_FIELD_LIMITS.scenario_preset}
        onChange={(value) => onChange("scenario_preset", value)}
        rows={3}
        value={draft.scenario_preset}
      />
    </BuilderSection>
  );
}

export function TrustStep({
  draft,
  errors,
  onAdultEligibilityChange,
  onChange
}: BuilderStepProps & {
  onAdultEligibilityChange: (enabled: boolean) => void;
}) {
  const intensityOptions = [
    { value: "0", label: "Off" },
    { value: "1", label: "Gentle" },
    { value: "2", label: "Expressive" },
    { value: "3", label: "Intense" }
  ];

  return (
    <BuilderSection
      eyebrow="Trust"
      title="Decide what continuity is allowed to hold"
      summary="Consent and privacy are profile state, not promises delegated to generated text."
    >
      <BuilderArea
        error={errors.boundary_notes}
        field="boundary_notes"
        label="Relationship boundaries"
        maxLength={CHARACTER_FIELD_LIMITS.boundary_notes}
        onChange={(value) => onChange("boundary_notes", value)}
        required
        rows={4}
        value={draft.boundary_notes}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <BuilderArea
          error={errors.consent_style}
          field="consent_style"
          label="Consent style"
          maxLength={CHARACTER_FIELD_LIMITS.consent_style}
          onChange={(value) => onChange("consent_style", value)}
          rows={4}
          value={draft.consent_style}
        />
        <BuilderArea
          error={errors.aftercare_style}
          field="aftercare_style"
          label="Return-to-calm style"
          maxLength={CHARACTER_FIELD_LIMITS.aftercare_style}
          onChange={(value) => onChange("aftercare_style", value)}
          rows={4}
          value={draft.aftercare_style}
        />
        <BuilderArea
          error={errors.soft_limits}
          field="soft_limits"
          label="Soft limits"
          maxLength={CHARACTER_FIELD_LIMITS.soft_limits}
          onChange={(value) => onChange("soft_limits", value)}
          rows={4}
          value={draft.soft_limits}
        />
        <BuilderArea
          error={errors.hard_limits}
          field="hard_limits"
          label="Hard limits"
          maxLength={CHARACTER_FIELD_LIMITS.hard_limits}
          onChange={(value) => onChange("hard_limits", value)}
          rows={4}
          value={draft.hard_limits}
        />
      </div>

      <section className="border-t border-line pt-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <BuilderToggle
            checked={draft.adult_mode_allowed}
            detail="Profile eligibility only. User age, relationship, consent, and safety gates still apply."
            error={errors.adult_mode_allowed}
            label="Eligible for gated adult mode"
            onChange={onAdultEligibilityChange}
          />
          <div>
            <p className="text-sm text-zinc-300">Content intensity ceiling</p>
            <div
              aria-label="Content intensity ceiling"
              className="mt-1 grid grid-cols-2 gap-1 rounded-md border border-line bg-ink p-1 sm:grid-cols-4"
              role="group"
            >
              {intensityOptions.map((option) => (
                <button
                  aria-pressed={draft.content_intensity === option.value}
                  className={`min-h-9 rounded px-2 text-xs ${
                    draft.content_intensity === option.value
                      ? "bg-paper font-semibold text-ink"
                      : "text-zinc-500 hover:text-paper"
                  }`}
                  disabled={!draft.adult_mode_allowed}
                  key={option.value}
                  onClick={() => onChange("content_intensity", option.value)}
                  type="button"
                >
                  {option.label}
                </button>
              ))}
            </div>
            {errors.content_intensity ? (
              <p className="mt-1 text-xs text-amber-200">{errors.content_intensity}</p>
            ) : null}
          </div>
        </div>
      </section>

      <section className="border-t border-line pt-5">
        <h3 className="text-sm font-semibold">Memory and privacy</h3>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <BuilderToggle
            checked={draft.remember_preferences}
            label="Remember preferences"
            onChange={(value) => onChange("remember_preferences", value)}
          />
          <BuilderToggle
            checked={draft.remember_emotional_notes}
            label="Remember emotional notes"
            onChange={(value) => onChange("remember_emotional_notes", value)}
          />
          <BuilderToggle
            checked={draft.private_mode_default}
            detail="New conversations can begin with durable cognition paused."
            label="Private by default"
            onChange={(value) => onChange("private_mode_default", value)}
          />
          <BuilderToggle
            checked={draft.adult_memory_storage}
            detail={
              draft.private_mode_default
                ? "Unavailable while new conversations default to private."
                : "Off by default even when adult mode is eligible."
            }
            disabled={!draft.adult_mode_allowed || draft.private_mode_default}
            error={errors.adult_memory_storage}
            label="Allow adult memory storage"
            onChange={(value) => onChange("adult_memory_storage", value)}
          />
        </div>
      </section>

      <section className="border-t border-line pt-5">
        <h3 className="text-sm font-semibold">Presence</h3>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <BuilderToggle
            checked={draft.proactive_enabled}
            detail="Allows bounded, cooldown-protected companion notes."
            label="Companion notes"
            onChange={(value) => onChange("proactive_enabled", value)}
          />
          <BuilderField
            error={errors.proactive_cooldown_hours}
            field="proactive_cooldown_hours"
            inputMode="numeric"
            label="Minimum hours between notes"
            maxLength={CHARACTER_FIELD_LIMITS.proactive_cooldown_hours}
            onChange={(value) => onChange("proactive_cooldown_hours", value)}
            value={draft.proactive_cooldown_hours}
          />
          <BuilderToggle
            checked={draft.allow_unresolved_thread_nudges}
            disabled={!draft.proactive_enabled}
            label="Follow up on open threads"
            onChange={(value) => onChange("allow_unresolved_thread_nudges", value)}
          />
          <BuilderToggle
            checked={draft.allow_morning_notes}
            disabled={!draft.proactive_enabled}
            label="Morning notes"
            onChange={(value) => onChange("allow_morning_notes", value)}
          />
          <BuilderToggle
            checked={draft.allow_goodnight_notes}
            disabled={!draft.proactive_enabled}
            label="Goodnight notes"
            onChange={(value) => onChange("allow_goodnight_notes", value)}
          />
        </div>
        <div className="mt-4 rounded-md border border-line bg-ink p-3">
          <div className="flex flex-wrap items-end gap-2">
            <div className="min-w-56 flex-1">
              <BuilderField
                error={errors.proactive_timezone}
                field="proactive_timezone"
                label="Your timezone"
                maxLength={CHARACTER_FIELD_LIMITS.proactive_timezone}
                onChange={(value) => onChange("proactive_timezone", value)}
                value={draft.proactive_timezone}
              />
            </div>
            <button
              className="min-h-10 rounded-md border border-line px-3 text-xs text-zinc-300 hover:border-zinc-400"
              onClick={() => onChange("proactive_timezone", resolvedDeviceTimeZone())}
              type="button"
            >
              Use device timezone
            </button>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <BuilderField
              error={errors.morning_time}
              field="morning_time"
              label="Morning note time"
              onChange={(value) => onChange("morning_time", value)}
              type="time"
              value={draft.morning_time}
            />
            <BuilderField
              error={errors.goodnight_time}
              field="goodnight_time"
              label="Goodnight note time"
              onChange={(value) => onChange("goodnight_time", value)}
              type="time"
              value={draft.goodnight_time}
            />
            <BuilderField
              error={errors.quiet_hours_start}
              field="quiet_hours_start"
              label="Quiet hours begin"
              onChange={(value) => onChange("quiet_hours_start", value)}
              type="time"
              value={draft.quiet_hours_start}
            />
            <BuilderField
              error={errors.quiet_hours_end}
              field="quiet_hours_end"
              label="Quiet hours end"
              onChange={(value) => onChange("quiet_hours_end", value)}
              type="time"
              value={draft.quiet_hours_end}
            />
          </div>
        </div>
      </section>
    </BuilderSection>
  );
}

function normalizeText(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}
