import type {
  AdultStatus,
  ContinuityThread,
  Journal,
  MemoryItem,
  Relationship
} from "./types";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const OFFSET_TIMESTAMP_PATTERN = /(?:Z|[+-]\d{2}:\d{2})$/;
const MAX_JSON_BYTES = 64_000;
const MAX_JSON_DEPTH = 6;
const MAX_JSON_COLLECTION_SIZE = 128;
const MAX_JSON_KEY_LENGTH = 100;
const MAX_JSON_STRING_LENGTH = 8_000;

type MemoryState = "active" | "forgotten" | "any";

export function isCompleteMemoryItem(
  value: unknown,
  characterId: string,
  state: MemoryState
): value is MemoryItem {
  if (!record(value) || !boundedJson(value)) {
    return false;
  }
  const forgottenAt = value.forgotten_at;
  const stateMatches =
    state === "any" ||
    (state === "active" && forgottenAt === null && value.lifecycle_state === "active") ||
    (state === "forgotten" &&
      validTimestamp(forgottenAt) &&
      (value.lifecycle_state === "forgotten" || value.lifecycle_state === "superseded"));
  return (
    validUuid(value.id) &&
    validUuid(value.user_id) &&
    value.character_id === characterId &&
    (value.source_message_id === null || validUuid(value.source_message_id)) &&
    (value.scope === "general" || value.scope === "adult") &&
    (value.claim_key === null || boundedText(value.claim_key, 160)) &&
    (value.retention_tier === "transient" ||
      value.retention_tier === "normal" ||
      value.retention_tier === "core") &&
    (value.lifecycle_state === "active" ||
      value.lifecycle_state === "superseded" ||
      value.lifecycle_state === "forgotten") &&
    (value.sensitivity === "standard" || value.sensitivity === "sensitive") &&
    boundedText(value.memory_type, 80) &&
    boundedText(value.content, 1_000) &&
    finiteRange(value.importance, 0, 1) &&
    finiteRange(value.confidence, 0, 1) &&
    finiteRange(value.emotional_weight, -1, 1) &&
    record(value.emotional_context_json) &&
    finiteRange(value.novelty, 0, 1) &&
    finiteRange(value.future_relevance, 0, 1) &&
    Number.isInteger(value.reinforcement_count) &&
    Number(value.reinforcement_count) >= 1 &&
    typeof value.pinned === "boolean" &&
    finiteRange(value.decay_score, 0, 1) &&
    (value.contradiction_group === null || boundedText(value.contradiction_group, 120)) &&
    (value.last_recalled_at === null || validTimestamp(value.last_recalled_at)) &&
    (value.last_reinforced_at === null || validTimestamp(value.last_reinforced_at)) &&
    (value.last_evidence_at === null || validTimestamp(value.last_evidence_at)) &&
    (value.superseded_by_id === null || validUuid(value.superseded_by_id)) &&
    (forgottenAt === null || validTimestamp(forgottenAt)) &&
    stateMatches &&
    record(value.metadata_json) &&
    validTimestamp(value.created_at) &&
    validTimestamp(value.updated_at) &&
    Date.parse(value.updated_at) >= Date.parse(value.created_at)
  );
}

export function isCompleteMemoryList(
  value: unknown,
  characterId: string,
  state: Exclude<MemoryState, "any">
): value is MemoryItem[] {
  return completeUniqueList<MemoryItem>(value, 500, (item) =>
    isCompleteMemoryItem(item, characterId, state)
  );
}

export function isCompleteJournal(value: unknown, characterId: string): value is Journal {
  return (
    record(value) &&
    boundedJson(value) &&
    validUuid(value.id) &&
    validUuid(value.user_id) &&
    value.character_id === characterId &&
    (value.conversation_id === null || validUuid(value.conversation_id)) &&
    (value.scope === "general" || value.scope === "adult") &&
    boundedText(value.journal_type, 80) &&
    boundedText(value.title, 200) &&
    boundedText(value.summary, 2_000) &&
    boundedStringList(value.emotional_tags_json, 32, 120) &&
    boundedStringList(value.unresolved_threads_json, 32, 500) &&
    boundedStringList(value.callbacks_json, 32, 500) &&
    finiteRange(value.importance, 0, 1) &&
    record(value.metadata_json) &&
    validTimestamp(value.created_at) &&
    validTimestamp(value.updated_at) &&
    Date.parse(value.updated_at) >= Date.parse(value.created_at)
  );
}

export function isCompleteJournalList(
  value: unknown,
  characterId: string
): value is Journal[] {
  return completeUniqueList<Journal>(value, 500, (item) =>
    isCompleteJournal(item, characterId)
  );
}

export function isCompleteContinuityThread(
  value: unknown,
  characterId: string
): value is ContinuityThread {
  if (!record(value) || !boundedJson(value)) {
    return false;
  }
  const status = value.status;
  const resolvedAt = value.resolved_at;
  return (
    validUuid(value.id) &&
    validUuid(value.user_id) &&
    value.character_id === characterId &&
    (value.conversation_id === null || validUuid(value.conversation_id)) &&
    (value.source_message_id === null || validUuid(value.source_message_id)) &&
    ["follow_up", "plan", "promise", "repair", "ritual"].includes(
      String(value.thread_kind)
    ) &&
    boundedText(value.content, 600) &&
    (status === "open" || status === "resolved") &&
    finiteRange(value.salience, 0, 1) &&
    finiteRange(value.confidence, 0, 1) &&
    (value.last_referenced_at === null || validTimestamp(value.last_referenced_at)) &&
    (value.last_proactive_at === null || validTimestamp(value.last_proactive_at)) &&
    (resolvedAt === null || validTimestamp(resolvedAt)) &&
    ((status === "open" && resolvedAt === null) ||
      (status === "resolved" && validTimestamp(resolvedAt))) &&
    record(value.metadata_json) &&
    validTimestamp(value.created_at) &&
    validTimestamp(value.updated_at) &&
    Date.parse(value.updated_at) >= Date.parse(value.created_at)
  );
}

export function isCompleteContinuityThreadList(
  value: unknown,
  characterId: string
): value is ContinuityThread[] {
  return completeUniqueList<ContinuityThread>(value, 100, (item) =>
    isCompleteContinuityThread(item, characterId)
  );
}

export function completeRelationship(
  value: unknown,
  characterId: string
): Relationship | null {
  if (
    !record(value) ||
    !boundedJson(value) ||
    value.character_id !== characterId ||
    !finiteRange(value.trust, 0, 1) ||
    !finiteRange(value.intimacy, 0, 1) ||
    !finiteRange(value.warmth, 0, 1) ||
    !finiteRange(value.tension, 0, 1) ||
    !finiteRange(value.familiarity, 0, 1) ||
    !finiteRange(value.attachment, 0, 1) ||
    !boundedText(value.mood, 80) ||
    !boundedText(value.conflict_state, 80) ||
    typeof value.repair_needed !== "boolean" ||
    !boundedStringList(value.tags_json, 32, 80) ||
    (value.last_interaction_at !== null && !validTimestamp(value.last_interaction_at)) ||
    !record(value.metadata_json) ||
    !validRelationshipMetadata(value.metadata_json)
  ) {
    return null;
  }
  return {
    trust: value.trust,
    intimacy: value.intimacy,
    warmth: value.warmth,
    tension: value.tension,
    familiarity: value.familiarity,
    attachment: value.attachment,
    mood: value.mood,
    conflict_state: value.conflict_state,
    repair_needed: value.repair_needed,
    tags_json: value.tags_json,
    last_interaction_at: value.last_interaction_at,
    metadata_json: value.metadata_json
  };
}

export function completeAdultStatus(value: unknown): AdultStatus | null {
  if (
    !record(value) ||
    (value.requested_mode !== "sfw" && value.requested_mode !== "adult") ||
    (value.effective_mode !== "sfw" && value.effective_mode !== "adult") ||
    typeof value.allowed !== "boolean" ||
    !boundedStringList(value.reasons, 16, 240) ||
    !integerRange(value.intensity, 0, 3) ||
    !integerRange(value.stored_memory_count, 0, 10_000_000) ||
    !integerRange(value.stored_moment_count, 0, 10_000_000)
  ) {
    return null;
  }
  const adultEffective = value.effective_mode === "adult";
  if (
    value.allowed !== adultEffective ||
    (adultEffective &&
      (value.requested_mode !== "adult" || value.reasons.length !== 0)) ||
    (!adultEffective && (value.reasons.length === 0 || value.intensity !== 0))
  ) {
    return null;
  }
  return value as AdultStatus;
}

function validRelationshipMetadata(value: Record<string, unknown>): boolean {
  const timeline = value.timeline;
  const changes = value.recent_changes;
  return (
    (timeline === undefined ||
      (Array.isArray(timeline) &&
        timeline.length <= 100 &&
        timeline.every(
          (item) =>
            record(item) &&
            (item.at === undefined || validTimestamp(item.at)) &&
            (item.kind === undefined || boundedText(item.kind, 80)) &&
            (item.summary === undefined || boundedText(item.summary, 500)) &&
            (item.tags === undefined || boundedStringList(item.tags, 16, 80))
        ))) &&
    (changes === undefined ||
      (Array.isArray(changes) &&
        changes.length <= 100 &&
        changes.every(
          (item) =>
            record(item) &&
            (item.at === undefined || validTimestamp(item.at)) &&
            (item.key === undefined || boundedText(item.key, 80)) &&
            (item.label === undefined || boundedText(item.label, 120)) &&
            (item.direction === undefined ||
              item.direction === "up" ||
              item.direction === "down" ||
              item.direction === "flat") &&
            (item.magnitude === undefined || boundedText(item.magnitude, 80)) &&
            (item.delta === undefined || finiteRange(item.delta, -1, 1)) &&
            (item.summary === undefined || boundedText(item.summary, 500))
        ))) &&
    (value.recent_change_summary === undefined ||
      boundedText(value.recent_change_summary, 500))
  );
}

function completeUniqueList<T>(
  value: unknown,
  limit: number,
  validator: (item: unknown) => boolean,
  idKey = "id"
): value is T[] {
  if (!Array.isArray(value) || value.length > limit || !value.every(validator)) {
    return false;
  }
  const ids = value.map((item) => (item as Record<string, unknown>)[idKey]);
  return ids.every((id) => typeof id === "string") && new Set(ids).size === ids.length;
}

function boundedJson(value: unknown, maxBytes = MAX_JSON_BYTES): boolean {
  if (!validJsonNode(value, 0)) {
    return false;
  }
  try {
    return new TextEncoder().encode(JSON.stringify(value)).length <= maxBytes;
  } catch {
    return false;
  }
}

function validJsonNode(value: unknown, depth: number): boolean {
  if (value === null || typeof value === "boolean") {
    return true;
  }
  if (typeof value === "number") {
    return Number.isFinite(value);
  }
  if (typeof value === "string") {
    return value.length <= MAX_JSON_STRING_LENGTH;
  }
  if (depth >= MAX_JSON_DEPTH) {
    return false;
  }
  if (Array.isArray(value)) {
    return (
      value.length <= MAX_JSON_COLLECTION_SIZE &&
      value.every((item) => validJsonNode(item, depth + 1))
    );
  }
  if (!record(value)) {
    return false;
  }
  const entries = Object.entries(value);
  return (
    entries.length <= MAX_JSON_COLLECTION_SIZE &&
    entries.every(
      ([key, item]) =>
        key.length <= MAX_JSON_KEY_LENGTH &&
        !key.startsWith("_") &&
        validJsonNode(item, depth + 1)
    )
  );
}

function boundedStringList(
  value: unknown,
  limit: number,
  itemLimit: number
): value is string[] {
  return (
    Array.isArray(value) &&
    value.length <= limit &&
    value.every((item) => typeof item === "string" && item.length <= itemLimit)
  );
}

function validUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function validTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length <= 64 &&
    OFFSET_TIMESTAMP_PATTERN.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}

function boundedText(value: unknown, limit: number): value is string {
  return typeof value === "string" && value.trim().length > 0 && value.length <= limit;
}

function finiteRange(value: unknown, minimum: number, maximum: number): value is number {
  return (
    typeof value === "number" &&
    Number.isFinite(value) &&
    value >= minimum &&
    value <= maximum
  );
}

function integerRange(value: unknown, minimum: number, maximum: number): value is number {
  return Number.isInteger(value) && finiteRange(value, minimum, maximum);
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
