import type { FormEvent } from "react";

export type AuthMode = "login" | "register";
export type ContentMode = "sfw" | "adult";
export type AdultReadinessState = "idle" | "loading" | "ready" | "error";
export type ConversationPrivacyMode = "normal" | "private";
export type ConversationScenarioMode = "default" | "custom";
export type StreamPhase = "connecting" | "composing" | "streaming";
export type StreamFailure = {
  userMessageId: string;
  content: string;
  detail: string;
  failureType: string;
  retryable: boolean;
};
export type User = {
  id: string;
  email: string;
  display_name: string | null;
  age_gate_confirmed: boolean;
  created_at: string;
};

export type CharacterSoul = {
  identity: string;
  worldview: string;
  temperament: string;
  humour: string;
  speech_rhythm: string;
  affection_style: string;
  conflict_style: string;
  values: string;
  insecurities: string;
  habits: string;
  initiative_style: string;
  boundaries: string;
  emoji_style: "none" | "rare" | "light" | "expressive";
  terms_of_address: string;
  relationship_path: "friendship" | "romantic" | "custom";
  custom_relationship: string;
};

export type Character = {
  id: string;
  owner_user_id: string;
  name: string;
  description: string | null;
  personality_core: string | null;
  speech_style: string | null;
  soul_json: CharacterSoul;
  boundaries_json: Record<string, unknown>;
  explicit_age: number | null;
  adult_mode_allowed: boolean;
  content_intensity: number;
  created_at: string;
  updated_at: string;
};

export type Conversation = {
  id: string;
  user_id: string;
  character_id: string;
  title: string | null;
  metadata_json: {
    privacy_mode?: ConversationPrivacyMode;
    scenario_mode?: ConversationScenarioMode;
    scenario_text?: string;
  } & Record<string, unknown>;
  last_read_at: string;
  last_message_at: string | null;
  unread_count: number;
  created_at: string;
  updated_at: string;
};

export type DeliveryState = {
  typing_ms?: number;
  read_state?: string;
  away_state?: string;
};

export type ContinuityReceipt = {
  state: "pending" | "ready" | "degraded" | "skipped";
  memory_ids: string[];
  moment_id: string | null;
  change_labels: ("remembered" | "reinforced" | "corrected" | "moment" | "relationship")[];
};

export type Message = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  metadata_json: {
    content_mode?: ContentMode;
    privacy_mode?: ConversationPrivacyMode;
    proactive?: boolean;
    proactive_type?: string;
    proactive_label?: string;
    provider?: string;
    model?: string;
    prompt_version?: string;
    generation_state?: "generating" | "complete" | "retryable" | "cancelled";
    generation_failure_type?: string | null;
    generation_retry_count?: number;
    reply_to_user_message_id?: string;
    delivery_state?: DeliveryState;
    continuity_receipt?: ContinuityReceipt;
    reroll_of?: string;
    edited?: boolean;
    system_event?: boolean;
    event_type?: string;
    event_label?: string;
  } & Record<string, unknown>;
  created_at: string;
};

export type SearchStatus = "idle" | "loading" | "ready" | "error";
export type MemoryView = "active" | "forgotten";
export type MemoryCategory =
  | "inside_jokes"
  | "moments"
  | "patterns"
  | "people"
  | "promises";

export type ChatResponse = {
  user_message: Message;
  assistant_message: Message;
};

export type MemoryItem = {
  id: string;
  user_id: string;
  character_id: string;
  source_message_id: string | null;
  scope: "general" | "adult";
  claim_key: string | null;
  retention_tier: "transient" | "normal" | "core";
  lifecycle_state: "active" | "superseded" | "forgotten";
  sensitivity: "standard" | "sensitive";
  memory_type: string;
  content: string;
  importance: number;
  confidence: number;
  emotional_weight: number;
  emotional_context_json: Record<string, unknown>;
  novelty: number;
  future_relevance: number;
  reinforcement_count: number;
  pinned: boolean;
  decay_score: number;
  contradiction_group: string | null;
  last_recalled_at: string | null;
  last_reinforced_at: string | null;
  last_evidence_at: string | null;
  superseded_by_id: string | null;
  forgotten_at: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type MemoryResolveResult = {
  memory: MemoryItem;
  removed: number;
  removed_memory_ids: string[];
};

export type RelationshipEvent = {
  at?: string;
  kind?: string;
  summary?: string;
  tags?: string[];
};

export type RelationshipRecentChange = {
  at?: string;
  key?: string;
  label?: string;
  direction?: "up" | "down" | "flat";
  magnitude?: string;
  delta?: number;
  summary?: string;
};

export type Relationship = {
  trust: number;
  intimacy: number;
  warmth: number;
  tension: number;
  familiarity: number;
  attachment: number;
  mood: string;
  conflict_state: string;
  repair_needed: boolean;
  tags_json: string[];
  last_interaction_at: string | null;
  metadata_json: {
    timeline?: RelationshipEvent[];
    recent_changes?: RelationshipRecentChange[];
    recent_change_summary?: string;
  } & Record<string, unknown>;
};

export type Journal = {
  id: string;
  user_id: string;
  character_id: string;
  conversation_id: string | null;
  scope: "general" | "adult";
  journal_type: string;
  title: string;
  summary: string;
  emotional_tags_json: string[];
  unresolved_threads_json: string[];
  callbacks_json: string[];
  importance: number;
  metadata_json: {
    episode_focus?: unknown;
    continuity_signals?: unknown;
    continuity_notes?: unknown;
    redacted_adult?: unknown;
  } & Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ContinuityThreadKind = "follow_up" | "plan" | "promise" | "repair" | "ritual";
export type ContinuityThreadStatus = "open" | "resolved";

export type ContinuityThread = {
  id: string;
  user_id: string;
  character_id: string;
  conversation_id: string | null;
  source_message_id: string | null;
  thread_kind: ContinuityThreadKind;
  content: string;
  status: ContinuityThreadStatus;
  salience: number;
  confidence: number;
  last_referenced_at: string | null;
  last_proactive_at: string | null;
  resolved_at: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type AdultStatus = {
  requested_mode: ContentMode;
  effective_mode: ContentMode;
  allowed: boolean;
  reasons: string[];
  intensity: number;
  stored_memory_count: number;
  stored_moment_count: number;
};

export type CharacterDraft = {
  name: string;
  appearance: string;
  visual_theme: string;
  description: string;
  relationship_type: string;
  personality_core: string;
  worldview: string;
  temperament: string;
  flaws: string;
  values: string;
  speech_style: string;
  humor_style: string;
  affection_style: string;
  conflict_style: string;
  insecurities: string;
  habits: string;
  initiative_style: string;
  emoji_style: CharacterSoul["emoji_style"];
  relationship_path: CharacterSoul["relationship_path"];
  custom_relationship: string;
  boundary_notes: string;
  interests: string;
  backstory: string;
  greeting: string;
  nicknames: string;
  scenario_preset: string;
  consent_style: string;
  soft_limits: string;
  hard_limits: string;
  aftercare_style: string;
  remember_preferences: boolean;
  remember_emotional_notes: boolean;
  retention_mode: "minimal" | "balanced" | "long_lived";
  private_mode_default: boolean;
  adult_memory_storage: boolean;
  proactive_enabled: boolean;
  proactive_snoozed_until: string;
  proactive_cooldown_hours: string;
  proactive_timezone: string;
  quiet_hours_start: string;
  quiet_hours_end: string;
  morning_time: string;
  goodnight_time: string;
  allow_inactivity_checkins: boolean;
  allow_morning_notes: boolean;
  allow_goodnight_notes: boolean;
  allow_thinking_of_you: boolean;
  allow_milestone_notes: boolean;
  allow_unresolved_thread_nudges: boolean;
  allow_delayed_double_texts: boolean;
  allow_manual_notes: boolean;
  explicit_age: string;
  adult_mode_allowed: boolean;
  content_intensity: string;
};

export type CharacterCreationResult =
  | { ok: true }
  | { ok: false; error: string; persisted: boolean };

export type AuthResponse = {
  access_token: string;
  token_type: "bearer";
  user: User;
};

export type SubmitHandler = (event: FormEvent<HTMLFormElement>) => void;

export const relationshipMetrics = [
  "trust",
  "intimacy",
  "warmth",
  "tension",
  "familiarity",
  "attachment"
] as const;

export type RelationshipMetric = (typeof relationshipMetrics)[number];
