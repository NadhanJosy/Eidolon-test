import type { FormEvent } from "react";

export type AuthMode = "login" | "register";
export type ContentMode = "sfw" | "adult";
export type Panel =
  | "overview"
  | "character"
  | "memory"
  | "journal"
  | "relationship"
  | "adult"
  | "settings"
  | "debug"
  | "data";

export type User = {
  id: string;
  email: string;
  display_name: string | null;
  age_gate_confirmed: boolean;
};

export type Character = {
  id: string;
  name: string;
  description: string | null;
  personality_core: string | null;
  speech_style: string | null;
  boundaries_json: Record<string, unknown>;
  explicit_age: number | null;
  adult_mode_allowed: boolean;
  content_intensity: number;
};

export type Conversation = {
  id: string;
  character_id: string;
  title: string | null;
  created_at?: string;
  updated_at?: string;
};

export type DeliveryState = {
  typing_ms?: number;
  read_state?: string;
  away_state?: string;
};

export type Message = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  metadata_json: {
    content_mode?: ContentMode;
    proactive?: boolean;
    proactive_type?: string;
    proactive_label?: string;
    provider?: string;
    prompt_version?: string;
    delivery_state?: DeliveryState;
    reroll_of?: string;
    edited?: boolean;
  } & Record<string, unknown>;
  created_at: string;
};

export type MemoryItem = {
  id: string;
  memory_type: string;
  content: string;
  importance: number;
  confidence: number;
  emotional_weight: number;
  pinned: boolean;
  decay_score: number;
  contradiction_group: string | null;
  last_recalled_at: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type RelationshipEvent = {
  at?: string;
  kind?: string;
  summary?: string;
  tags?: string[];
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
  metadata_json: {
    timeline?: RelationshipEvent[];
  } & Record<string, unknown>;
};

export type ScheduledJob = {
  id: string;
  job_type: string;
  status: string;
  run_at: string;
  payload_json?: Record<string, unknown>;
};

export type Journal = {
  id: string;
  journal_type: string;
  title: string;
  summary: string;
  emotional_tags_json: string[];
  unresolved_threads_json: string[];
  callbacks_json: string[];
  importance: number;
  created_at: string;
};

export type AdultStatus = {
  requested_mode: ContentMode;
  effective_mode: ContentMode;
  allowed: boolean;
  reasons: string[];
  intensity: number;
};

export type DebugPayload = {
  relationship?: Relationship & { timeline?: RelationshipEvent[] };
  journals?: Pick<Journal, "id" | "title" | "summary" | "journal_type" | "importance">[];
  prompt_context?: {
    prompt_version: string;
    content_mode: string;
    llm_provider: string;
    prompt_preview: string;
    prompt_chars: number;
  };
};

export type RuntimeHealthState = "checking" | "ok" | "degraded" | "offline";

export type RuntimeStatus = {
  api: RuntimeHealthState;
  db: RuntimeHealthState;
  llm: RuntimeHealthState;
  llmProvider: string | null;
  checkedAt: string | null;
};

export type CharacterDraft = {
  name: string;
  description: string;
  personality_core: string;
  speech_style: string;
  explicit_age: string;
  adult_mode_allowed: boolean;
  content_intensity: string;
};

export type AuthResponse = {
  access_token: string;
  refresh_token: string;
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
