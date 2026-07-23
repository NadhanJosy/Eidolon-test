import {
  defaultCharacterProfile,
  emptyCharacterDraft,
  toBoundariesJson,
  toCharacterDraft,
  toSoulJson
} from "./controller-utils";
import type { Character, CharacterDraft } from "./types";

export type CharacterBuilderStep = "identity" | "inner-life" | "world" | "trust";

export type CharacterDraftErrors = Partial<Record<keyof CharacterDraft, string>>;

export type ScenarioPreset = {
  label: string;
  detail: string;
  value: string;
};

export const CHARACTER_BUILDER_STEPS: Array<{
  id: CharacterBuilderStep;
  label: string;
  summary: string;
}> = [
  { id: "identity", label: "Presence", summary: "Identity and relationship" },
  { id: "inner-life", label: "Inner life", summary: "Temperament and voice" },
  { id: "world", label: "Shared world", summary: "History and first moment" },
  { id: "trust", label: "Trust", summary: "Boundaries and continuity" }
];

export const SCENARIO_PRESETS: ScenarioPreset[] = [
  {
    label: "First Evening",
    detail: "Soft opening, attentive questions, no assumed closeness.",
    value:
      "A quiet first evening together: low pressure, attentive listening, gentle curiosity, and no assumptions about closeness."
  },
  {
    label: "Late Check-In",
    detail: "A grounded note after a long day, warm but unintrusive.",
    value:
      "A late-night check-in where the companion notices tone, offers steadiness, and leaves room for short replies."
  },
  {
    label: "Shared Project",
    detail: "Companionable focus with small callbacks to progress.",
    value:
      "A focused co-working session with warm encouragement, practical companionship, and small callbacks to progress."
  },
  {
    label: "Repair Talk",
    detail: "Accountability first, calm pacing, clear boundaries.",
    value:
      "A calm repair conversation after tension: accountability first, no defensiveness, and explicit room for boundaries."
  },
  {
    label: "Daily Ritual",
    detail: "A familiar rhythm built from remembered preferences.",
    value:
      "A familiar daily rhythm with remembered preferences, small rituals, grounded affection, and respect for pace."
  },
  {
    label: "Reflective Debrief",
    detail: "Emotional continuity, unresolved threads, gentle follow-up.",
    value:
      "A thoughtful debrief after an emotional day, prioritizing memory-worthy moments, unresolved questions, and gentle follow-up."
  }
];

export const CHARACTER_FIELD_LIMITS: Partial<Record<keyof CharacterDraft, number>> = {
  name: 120,
  appearance: 2000,
  visual_theme: 80,
  description: 2000,
  relationship_type: 2000,
  personality_core: 4000,
  worldview: 2000,
  temperament: 2000,
  flaws: 2000,
  values: 2000,
  speech_style: 2000,
  humor_style: 2000,
  affection_style: 1600,
  conflict_style: 1600,
  insecurities: 1600,
  habits: 1600,
  initiative_style: 1600,
  custom_relationship: 1000,
  boundary_notes: 4000,
  interests: 2000,
  backstory: 4000,
  greeting: 600,
  nicknames: 2000,
  scenario_preset: 4000,
  consent_style: 4000,
  soft_limits: 4000,
  hard_limits: 4000,
  aftercare_style: 4000,
  proactive_cooldown_hours: 3,
  proactive_daily_cap: 1,
  proactive_timezone: 80,
  quiet_hours_start: 5,
  quiet_hours_end: 5,
  morning_time: 5,
  goodnight_time: 5
};

const MAX_CHARACTER_PROFILE_JSON_BYTES = 30_000;

const STEP_FIELDS: Record<CharacterBuilderStep, Array<keyof CharacterDraft>> = {
  identity: ["name", "appearance", "visual_theme", "relationship_type", "description", "explicit_age", "adult_mode_allowed"],
  "inner-life": [
    "personality_core",
    "worldview",
    "temperament",
    "flaws",
    "values",
    "speech_style",
    "humor_style",
    "affection_style",
    "conflict_style",
    "insecurities",
    "habits",
    "initiative_style",
    "relationship_path",
    "custom_relationship"
  ],
  world: ["interests", "backstory", "greeting", "nicknames", "scenario_preset"],
  trust: [
    "boundary_notes",
    "consent_style",
    "soft_limits",
    "hard_limits",
    "aftercare_style",
    "content_intensity",
    "adult_memory_storage",
    "proactive_cooldown_hours",
    "proactive_daily_cap",
    "proactive_timezone",
    "quiet_hours_start",
    "quiet_hours_end",
    "morning_time",
    "goodnight_time"
  ]
};

export function authoredCharacterDraft(): CharacterDraft {
  const profile = defaultCharacterProfile("");
  const character: Character = {
    id: "",
    owner_user_id: "",
    name: "",
    description: profile.description ?? null,
    personality_core: profile.personality_core ?? null,
    speech_style: profile.speech_style ?? null,
    soul_json: profile.soul_json,
    boundaries_json: profile.boundaries_json,
    explicit_age: null,
    adult_mode_allowed: false,
    content_intensity: 0,
    created_at: "",
    updated_at: ""
  };
  return {
    ...emptyCharacterDraft(),
    ...toCharacterDraft(character),
    name: ""
  };
}

export function validateCharacterDraft(
  draft: CharacterDraft,
  options: { requireAuthoredProfile?: boolean } = {}
): CharacterDraftErrors {
  const errors: CharacterDraftErrors = {};
  const requireAuthoredProfile = options.requireAuthoredProfile ?? false;

  for (const [field, maximum] of Object.entries(CHARACTER_FIELD_LIMITS) as Array<
    [keyof CharacterDraft, number]
  >) {
    const value = draft[field];
    if (typeof value === "string" && value.length > maximum) {
      errors[field] = `Keep this to ${maximum.toLocaleString()} characters or fewer.`;
    }
  }

  if (!draft.name.trim()) {
    errors.name = "Give this companion a name.";
  }

  if (requireAuthoredProfile) {
    requireText(errors, draft, "relationship_type", "Choose the relationship they are entering.");
    requireText(errors, draft, "personality_core", "Give them a clear personality core.");
    requireText(errors, draft, "worldview", "Give them a point of view on the world.");
    requireText(errors, draft, "temperament", "Describe their emotional temperament.");
    requireText(errors, draft, "speech_style", "Describe how their voice should feel.");
    requireText(errors, draft, "affection_style", "Describe how they show care.");
    requireText(errors, draft, "conflict_style", "Describe how they handle disagreement.");
    requireText(errors, draft, "initiative_style", "Describe how they take initiative.");
    requireText(errors, draft, "greeting", "Write the first line they will meet you with.");
    requireText(errors, draft, "boundary_notes", "Set the boundaries that keep this relationship safe.");
  }

  const age = parseCharacterAge(draft.explicit_age);
  if (draft.explicit_age.trim() && age === null) {
    errors.explicit_age = "Age must be a whole number from 0 to 150.";
  }
  if (draft.adult_mode_allowed && (age === null || age < 18)) {
    errors.explicit_age = "Adult eligibility requires an explicit age of 18 or older.";
    errors.adult_mode_allowed = "Set an adult age before enabling adult eligibility.";
  }

  const intensity = parseContentIntensity(draft.content_intensity);
  if (intensity === null) {
    errors.content_intensity = "Choose an intensity from 0 to 3.";
  } else if (!draft.adult_mode_allowed && intensity !== 0) {
    errors.content_intensity = "Intensity stays at Off until adult eligibility is enabled.";
  }

  if (draft.adult_mode_allowed) {
    requireText(errors, draft, "consent_style", "Describe how this companion handles consent.");
    requireText(errors, draft, "hard_limits", "Set clear hard limits before enabling adult eligibility.");
  }
  if (draft.relationship_path === "custom" && !draft.custom_relationship.trim()) {
    errors.custom_relationship = "Describe the custom relationship path.";
  }
  if (draft.adult_memory_storage && draft.private_mode_default) {
    errors.adult_memory_storage =
      "Adult memory storage stays off while private by default is enabled.";
  } else if (draft.adult_memory_storage && !draft.adult_mode_allowed) {
    errors.adult_memory_storage =
      "Enable adult eligibility before allowing adult memory storage.";
  }

  if (!isValidTimeZone(draft.proactive_timezone)) {
    errors.proactive_timezone = "Use a recognized IANA timezone such as Europe/London.";
  }
  if (parseProactiveCooldownHours(draft.proactive_cooldown_hours) === null) {
    errors.proactive_cooldown_hours = "Choose a cooldown from 1 to 168 hours.";
  }
  if (!/^[1-3]$/.test(draft.proactive_daily_cap)) {
    errors.proactive_daily_cap = "Choose a daily cap from 1 to 3 notes.";
  }
  for (const field of [
    "quiet_hours_start",
    "quiet_hours_end",
    "morning_time",
    "goodnight_time"
  ] as const) {
    if (!isValidClockTime(draft[field])) {
      errors[field] = "Use a 24-hour time from 00:00 to 23:59.";
    }
  }

  const profileBytes = new TextEncoder().encode(
    JSON.stringify(toBoundariesJson(draft))
  ).length;
  if (profileBytes > MAX_CHARACTER_PROFILE_JSON_BYTES) {
    errors.boundary_notes =
      "The combined profile is too long. Shorten the world, boundary, or continuity details.";
  }

  return errors;
}

export function firstInvalidBuilderStep(
  errors: CharacterDraftErrors
): CharacterBuilderStep | null {
  for (const step of CHARACTER_BUILDER_STEPS) {
    if (STEP_FIELDS[step.id].some((field) => errors[field])) {
      return step.id;
    }
  }
  return null;
}

export function stepHasError(
  step: CharacterBuilderStep,
  errors: CharacterDraftErrors
): boolean {
  return STEP_FIELDS[step].some((field) => Boolean(errors[field]));
}

export function parseCharacterAge(value: string): number | null {
  const normalized = value.trim();
  if (!normalized || !/^\d+$/.test(normalized)) {
    return null;
  }
  const age = Number.parseInt(normalized, 10);
  return Number.isSafeInteger(age) && age >= 0 && age <= 150 ? age : null;
}

export function parseContentIntensity(value: string): number | null {
  const normalized = value.trim();
  if (!/^[0-3]$/.test(normalized)) {
    return null;
  }
  return Number.parseInt(normalized, 10);
}

export function canonicalizeCharacterAdultDraft(draft: CharacterDraft): CharacterDraft {
  const explicitAge = parseCharacterAge(draft.explicit_age);
  const adultModeAllowed =
    explicitAge !== null && explicitAge >= 18 && draft.adult_mode_allowed;
  return {
    ...draft,
    adult_mode_allowed: adultModeAllowed,
    content_intensity: adultModeAllowed ? draft.content_intensity : "0",
    adult_memory_storage:
      adultModeAllowed && !draft.private_mode_default && draft.adult_memory_storage
  };
}

export function parseProactiveCooldownHours(value: string): number | null {
  const normalized = value.trim();
  if (!/^\d+$/.test(normalized)) {
    return null;
  }
  const hours = Number.parseInt(normalized, 10);
  return Number.isSafeInteger(hours) && hours >= 1 && hours <= 168 ? hours : null;
}

export function resolvedDeviceTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

export function characterPayloadFromDraft(
  draft: CharacterDraft,
  existingBoundaries: Record<string, unknown> = {}
) {
  const canonicalDraft = canonicalizeCharacterAdultDraft(draft);
  const explicitAge = parseCharacterAge(canonicalDraft.explicit_age);
  const adultModeAllowed = canonicalDraft.adult_mode_allowed;
  const contentIntensity = adultModeAllowed
    ? (parseContentIntensity(canonicalDraft.content_intensity) ?? 0)
    : 0;
  const normalizedDraft: CharacterDraft = {
    ...canonicalDraft,
    content_intensity: contentIntensity.toString()
  };
  return {
    name: compactText(draft.name),
    description: nullableText(draft.description),
    personality_core: nullableText(draft.personality_core),
    speech_style: nullableText(draft.speech_style),
    soul_json: toSoulJson(normalizedDraft),
    boundaries_json: toBoundariesJson(normalizedDraft, existingBoundaries),
    explicit_age: explicitAge,
    adult_mode_allowed: adultModeAllowed,
    content_intensity: contentIntensity
  };
}

function requireText(
  errors: CharacterDraftErrors,
  draft: CharacterDraft,
  field: keyof CharacterDraft,
  message: string
) {
  const value = draft[field];
  if (typeof value === "string" && !value.trim() && !errors[field]) {
    errors[field] = message;
  }
}

function compactText(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

function nullableText(value: string): string | null {
  const normalized = value.trim();
  return normalized || null;
}

function isValidClockTime(value: string): boolean {
  if (!/^\d{2}:\d{2}$/.test(value)) {
    return false;
  }
  const [hour, minute] = value.split(":").map(Number);
  return hour >= 0 && hour <= 23 && minute >= 0 && minute <= 59;
}

function isValidTimeZone(value: string): boolean {
  const normalized = value.trim();
  if (!normalized) {
    return false;
  }
  try {
    Intl.DateTimeFormat("en-GB", { timeZone: normalized }).format(new Date(0));
    return true;
  } catch {
    return false;
  }
}
