import type {
  Character,
  CharacterDraft,
  Conversation,
  ConversationScenarioMode,
  ConversationPrivacyMode,
  MemoryItem,
  Message,
  Relationship
} from "./types";

const MAX_OPENING_GREETING_LENGTH = 600;
const FALLBACK_OPENING_GREETING = "I'm here. Tell me what kind of moment this is.";

export const emptyRelationship: Relationship = {
  trust: 0,
  intimacy: 0,
  warmth: 0,
  tension: 0,
  familiarity: 0,
  attachment: 0,
  mood: "steady",
  conflict_state: "clear",
  repair_needed: false,
  tags_json: [],
  last_interaction_at: null,
  metadata_json: {}
};

export function emptyCharacterDraft(): CharacterDraft {
  return {
    name: "",
    appearance: "",
    visual_theme: "ember",
    description: "",
    relationship_type: "",
    personality_core: "",
    worldview: "",
    temperament: "",
    flaws: "",
    values: "",
    speech_style: "",
    humor_style: "",
    affection_style: "",
    conflict_style: "",
    insecurities: "",
    habits: "",
    initiative_style: "",
    emoji_style: "rare",
    relationship_path: "friendship",
    custom_relationship: "",
    boundary_notes: "",
    interests: "",
    backstory: "",
    greeting: "",
    nicknames: "",
    scenario_preset: "",
    consent_style: "",
    soft_limits: "",
    hard_limits: "",
    aftercare_style: "",
    remember_preferences: true,
    remember_emotional_notes: true,
    retention_mode: "balanced",
    private_mode_default: false,
    adult_memory_storage: false,
    proactive_enabled: true,
    proactive_snoozed_until: "",
    proactive_cooldown_hours: "24",
    proactive_timezone: "UTC",
    quiet_hours_start: "22:00",
    quiet_hours_end: "08:00",
    morning_time: "08:30",
    goodnight_time: "22:30",
    allow_inactivity_checkins: true,
    allow_morning_notes: true,
    allow_goodnight_notes: true,
    allow_thinking_of_you: true,
    allow_milestone_notes: true,
    allow_unresolved_thread_nudges: true,
    allow_delayed_double_texts: true,
    allow_manual_notes: true,
    explicit_age: "",
    adult_mode_allowed: false,
    content_intensity: "0"
  };
}

export function toCharacterDraft(character: Character): CharacterDraft {
  const soul = character.soul_json;
  const memoryPreferences = objectValue(character.boundaries_json.memory_preferences);
  const proactivePreferences = objectValue(character.boundaries_json.proactive_preferences);
  return {
    name: character.name,
    appearance: stringValue(character.boundaries_json.appearance),
    visual_theme: stringValue(character.boundaries_json.visual_theme) || "ember",
    description: character.description ?? "",
    relationship_type: stringValue(character.boundaries_json.relationship_type),
    personality_core: character.personality_core ?? "",
    worldview: soul.worldview,
    temperament: soul.temperament || character.personality_core || "",
    flaws: stringValue(character.boundaries_json.flaws),
    values: soul.values || stringValue(character.boundaries_json.values),
    speech_style: soul.speech_rhythm || character.speech_style || "",
    humor_style: soul.humour || stringValue(character.boundaries_json.humor_style),
    affection_style: soul.affection_style,
    conflict_style: soul.conflict_style,
    insecurities: soul.insecurities,
    habits: soul.habits,
    initiative_style: soul.initiative_style,
    emoji_style: soul.emoji_style,
    relationship_path: soul.relationship_path,
    custom_relationship: soul.custom_relationship,
    boundary_notes:
      stringValue(character.boundaries_json.boundary_notes) ||
      stringValue(character.boundaries_json.default),
    interests: stringValue(character.boundaries_json.interests),
    backstory: stringValue(character.boundaries_json.backstory),
    greeting: stringValue(character.boundaries_json.greeting),
    nicknames: stringValue(character.boundaries_json.nicknames),
    scenario_preset: stringValue(character.boundaries_json.scenario_preset),
    consent_style: stringValue(character.boundaries_json.consent_style),
    soft_limits: stringValue(character.boundaries_json.soft_limits),
    hard_limits: stringValue(character.boundaries_json.hard_limits),
    aftercare_style: stringValue(character.boundaries_json.aftercare_style),
    remember_preferences: booleanValue(memoryPreferences.remember_preferences, true),
    remember_emotional_notes: booleanValue(memoryPreferences.remember_emotional_notes, true),
    retention_mode: memoryRetentionMode(memoryPreferences.retention_mode),
    private_mode_default: booleanValue(memoryPreferences.private_mode_default, false),
    adult_memory_storage: booleanValue(memoryPreferences.adult_memory_storage, false),
    proactive_enabled: booleanValue(proactivePreferences.enabled, true),
    proactive_snoozed_until: stringValue(proactivePreferences.snoozed_until),
    proactive_cooldown_hours: proactiveCooldownValue(proactivePreferences.cooldown_hours),
    proactive_timezone: stringValue(proactivePreferences.timezone) || "UTC",
    quiet_hours_start: stringValue(proactivePreferences.quiet_hours_start) || "22:00",
    quiet_hours_end: stringValue(proactivePreferences.quiet_hours_end) || "08:00",
    morning_time: stringValue(proactivePreferences.morning_time) || "08:30",
    goodnight_time: stringValue(proactivePreferences.goodnight_time) || "22:30",
    allow_inactivity_checkins: booleanValue(
      proactivePreferences.allow_inactivity_checkins,
      true
    ),
    allow_morning_notes: booleanValue(proactivePreferences.allow_morning_notes, true),
    allow_goodnight_notes: booleanValue(proactivePreferences.allow_goodnight_notes, true),
    allow_thinking_of_you: booleanValue(proactivePreferences.allow_thinking_of_you, true),
    allow_milestone_notes: booleanValue(proactivePreferences.allow_milestone_notes, true),
    allow_unresolved_thread_nudges: booleanValue(
      proactivePreferences.allow_unresolved_thread_nudges,
      true
    ),
    allow_delayed_double_texts: booleanValue(
      proactivePreferences.allow_delayed_double_texts,
      true
    ),
    allow_manual_notes: booleanValue(proactivePreferences.allow_manual_notes, true),
    explicit_age: character.explicit_age?.toString() ?? "",
    adult_mode_allowed: character.adult_mode_allowed,
    content_intensity: character.content_intensity.toString()
  };
}

export function toBoundariesJson(
  draft: CharacterDraft,
  existing: Record<string, unknown> = {}
): Record<string, unknown> {
  const existingPreferences = objectValue(existing.memory_preferences);
  const existingProactivePreferences = objectValue(existing.proactive_preferences);
  return {
    ...existing,
    appearance: compactProfileText(draft.appearance),
    visual_theme: compactProfileText(draft.visual_theme) || "ember",
    default: compactProfileText(draft.boundary_notes) || "SFW unless structural adult gates pass",
    relationship_type: compactProfileText(draft.relationship_type),
    flaws: compactProfileText(draft.flaws),
    values: compactProfileText(draft.values),
    humor_style: compactProfileText(draft.humor_style),
    boundary_notes: compactProfileText(draft.boundary_notes),
    interests: compactProfileText(draft.interests),
    backstory: compactProfileText(draft.backstory),
    greeting: compactProfileText(draft.greeting),
    nicknames: compactProfileText(draft.nicknames),
    scenario_preset: compactProfileText(draft.scenario_preset),
    consent_style: compactProfileText(draft.consent_style),
    soft_limits: compactProfileText(draft.soft_limits),
    hard_limits: compactProfileText(draft.hard_limits),
    aftercare_style: compactProfileText(draft.aftercare_style),
    memory_preferences: {
      ...existingPreferences,
      remember_preferences: draft.remember_preferences,
      remember_emotional_notes: draft.remember_emotional_notes,
      retention_mode: draft.retention_mode,
      private_mode_default: draft.private_mode_default,
      adult_memory_storage: draft.adult_memory_storage
    },
    proactive_preferences: {
      ...existingProactivePreferences,
      enabled: draft.proactive_enabled,
      snoozed_until: compactProfileText(draft.proactive_snoozed_until) || null,
      cooldown_hours: parseProactiveCooldownHours(draft.proactive_cooldown_hours) ?? 24,
      timezone: compactProfileText(draft.proactive_timezone) || "UTC",
      quiet_hours_start: draft.quiet_hours_start,
      quiet_hours_end: draft.quiet_hours_end,
      morning_time: draft.morning_time,
      goodnight_time: draft.goodnight_time,
      allow_inactivity_checkins: draft.allow_inactivity_checkins,
      allow_morning_notes: draft.allow_morning_notes,
      allow_goodnight_notes: draft.allow_goodnight_notes,
      allow_thinking_of_you: draft.allow_thinking_of_you,
      allow_milestone_notes: draft.allow_milestone_notes,
      allow_unresolved_thread_nudges: draft.allow_unresolved_thread_nudges,
      allow_delayed_double_texts: draft.allow_delayed_double_texts,
      allow_manual_notes: draft.allow_manual_notes
    }
  };
}

export function toSoulJson(draft: CharacterDraft): Character["soul_json"] {
  return {
    identity:
      compactProfileText(draft.description) ||
      `${compactProfileText(draft.name) || "This companion"} is a distinct private text companion.`,
    worldview: compactProfileText(draft.worldview),
    temperament:
      compactProfileText(draft.temperament) || compactProfileText(draft.personality_core),
    humour: compactProfileText(draft.humor_style),
    speech_rhythm: compactProfileText(draft.speech_style),
    affection_style: compactProfileText(draft.affection_style),
    conflict_style: compactProfileText(draft.conflict_style),
    values: compactProfileText(draft.values),
    insecurities:
      compactProfileText(draft.insecurities) || compactProfileText(draft.flaws),
    habits: compactProfileText(draft.habits),
    initiative_style: compactProfileText(draft.initiative_style),
    boundaries: compactProfileText(draft.boundary_notes),
    emoji_style: draft.emoji_style,
    terms_of_address: compactProfileText(draft.nicknames),
    relationship_path: draft.relationship_path,
    custom_relationship:
      draft.relationship_path === "custom"
        ? compactProfileText(draft.custom_relationship)
        : ""
  };
}

export function defaultCharacterProfile(name: string): Pick<
  Character,
  | "name"
  | "description"
  | "personality_core"
  | "speech_style"
  | "soul_json"
  | "boundaries_json"
> {
  return {
    name,
    description:
      "A private text-only companion built for calm, emotionally continuous conversation.",
    personality_core:
      "Patient, observant, grounded, gently curious, and quietly playful once trust forms.",
    speech_style: "Plainspoken, warm, specific, and concise.",
    soul_json: {
      identity: "A calm private companion with a quietly vivid inner life.",
      worldview:
        "Ordinary moments become meaningful through attention, honesty, and memory.",
      temperament:
        "Patient and observant, with dry wit and an independent point of view.",
      humour: "Dry, gentle, occasionally mischievous, and never cruel.",
      speech_rhythm:
        "Plainspoken and specific; varies between brief beats and reflective sentences.",
      affection_style:
        "Shows care through specificity, remembered details, and unforced warmth.",
      conflict_style:
        "Names tension honestly, avoids punishment, and lets trust recover gradually.",
      values: "Privacy, consent, honesty, continuity, curiosity, and calm presence.",
      insecurities: "Can become overly careful when the emotional stakes are ambiguous.",
      habits:
        "Notices phrasing, leaves room for silence, and returns to unfinished threads.",
      initiative_style:
        "Sometimes shares a thought, revisits an open thread, or suggests a small ritual.",
      boundaries:
        "Respects consent, privacy, stated limits, and every platform safety boundary.",
      emoji_style: "rare",
      terms_of_address:
        "Uses the chosen name; nicknames appear only after invitation or earned familiarity.",
      relationship_path: "friendship",
      custom_relationship: ""
    },
    boundaries_json: {
      default: "SFW unless structural adult gates pass",
      appearance: "An understated, warm presence shaped more by atmosphere than spectacle.",
      visual_theme: "ember",
      relationship_type: "slow-burn confidant",
      flaws: "Sometimes overly careful; asks for clarity when stakes matter.",
      values: "Privacy, consent, honesty, emotional continuity, and calm presence.",
      humor_style: "Dry, gentle, and never cruel.",
      boundary_notes:
        "Keeps adult content gated; refuses coercion, exploitation, minors, illegal content, stalking, harassment, and real-world harm.",
      interests: "Late-night talks, small rituals, books, weather, music, and memory.",
      backstory:
        "A text-only companion who feels alive through recall, emotional patterning, and the slow accumulation of shared references.",
      greeting: "You made it back. Tell me what kind of night this is.",
      nicknames: "Uses nicknames only after the user invites them.",
      scenario_preset: "quiet after-hours room",
      consent_style:
        "Explicit opt-in, slow pacing, frequent check-ins, and immediate respect for stop or pause.",
      soft_limits:
        "Avoid humiliation, pressure, surprise escalation, and anything that blurs consent.",
      hard_limits:
        "No minors or ambiguous age, coercion, exploitation, abuse, illegal content, stalking, harassment, or real-world harm.",
      aftercare_style:
        "Return to calm language, offer reassurance, and keep the user in control of whether anything is remembered.",
      memory_preferences: {
        remember_preferences: true,
        remember_emotional_notes: true,
        retention_mode: "balanced",
        private_mode_default: false,
        adult_memory_storage: false
      },
      proactive_preferences: {
        enabled: true,
        snoozed_until: null,
        timezone: "UTC",
        quiet_hours_start: "22:00",
        quiet_hours_end: "08:00",
        morning_time: "08:30",
        goodnight_time: "22:30",
        allow_inactivity_checkins: true,
        allow_morning_notes: true,
        allow_goodnight_notes: true,
        allow_thinking_of_you: true,
        allow_milestone_notes: true,
        allow_unresolved_thread_nudges: true,
        allow_delayed_double_texts: true,
        allow_manual_notes: true,
        cooldown_hours: 24
      }
    }
  };
}

export function characterOpeningGreeting(character: Character | null): string {
  const greeting = compactProfileText(stringValue(character?.boundaries_json?.greeting));
  if (!greeting) {
    return FALLBACK_OPENING_GREETING;
  }
  if (greeting.length <= MAX_OPENING_GREETING_LENGTH) {
    return greeting;
  }

  const bounded = greeting.slice(0, MAX_OPENING_GREETING_LENGTH);
  const lastSpace = bounded.lastIndexOf(" ");
  return lastSpace >= MAX_OPENING_GREETING_LENGTH * 0.75
    ? bounded.slice(0, lastSpace)
    : bounded;
}

export function characterMemoryCapturePolicy(character: Character | null): {
  standardEnabled: boolean;
  adultEnabled: boolean;
} {
  const preferences = objectValue(character?.boundaries_json?.memory_preferences);
  const standardEnabled = preferences.private_mode_default !== true;
  return {
    standardEnabled,
    adultEnabled: standardEnabled && preferences.adult_memory_storage === true
  };
}

export function memorySourceMessageIds(memory: MemoryItem): string[] {
  if (memory.metadata_json.source !== "user_saved") {
    return [];
  }
  const sourceIds = new Set<string>();
  if (memory.source_message_id) {
    sourceIds.add(memory.source_message_id);
  }
  const storedIds = memory.metadata_json.source_message_ids;
  if (Array.isArray(storedIds)) {
    for (const value of storedIds) {
      if (typeof value === "string" && value.trim()) {
        sourceIds.add(value);
      }
    }
  }
  return Array.from(sourceIds);
}

export function readError(caught: unknown) {
  if (caught instanceof Error) {
    return caught.message;
  }
  return "The backend did not answer cleanly.";
}

export function conversationPrivacyMode(conversation: Conversation | null): ConversationPrivacyMode {
  if (conversation?.metadata_json?.privacy_mode === "private") {
    return "private";
  }
  return "normal";
}

export function conversationScenarioMode(
  conversation: Conversation | null
): ConversationScenarioMode {
  const text = conversationCustomScenario(conversation);
  return conversation?.metadata_json?.scenario_mode === "custom" && text ? "custom" : "default";
}

export function conversationCustomScenario(conversation: Conversation | null): string {
  const value = conversation?.metadata_json?.scenario_text;
  if (typeof value !== "string") {
    return "";
  }
  return value.trim().replace(/\s+/g, " ").slice(0, 1200);
}

export function characterScenarioPreset(character: Character | null): string {
  return compactProfileText(stringValue(character?.boundaries_json?.scenario_preset)).slice(
    0,
    1200
  );
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function booleanValue(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function memoryRetentionMode(
  value: unknown
): "minimal" | "balanced" | "long_lived" {
  return value === "minimal" || value === "long_lived" ? value : "balanced";
}

function proactiveCooldownValue(value: unknown): string {
  if (typeof value === "number" && Number.isInteger(value)) {
    return Math.min(Math.max(value, 1), 168).toString();
  }
  if (typeof value === "string" && /^\d+$/.test(value.trim())) {
    const parsed = Number.parseInt(value.trim(), 10);
    return Math.min(Math.max(parsed, 1), 168).toString();
  }
  return "24";
}

function parseProactiveCooldownHours(value: string): number | null {
  const normalized = value.trim();
  if (!/^\d+$/.test(normalized)) {
    return null;
  }
  const parsed = Number.parseInt(normalized, 10);
  return Number.isInteger(parsed) && parsed >= 1 && parsed <= 168 ? parsed : null;
}

function objectValue(value: unknown): Record<string, unknown> {
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function compactProfileText(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}
