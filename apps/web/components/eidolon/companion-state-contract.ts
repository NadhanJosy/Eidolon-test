import type {
  AdultStatus,
  AssembledContext,
  ConversationDebugPayload,
  DebugPayload,
  Journal,
  MemoryItem,
  Relationship,
  ScheduledJob
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
    (state === "active" && forgottenAt === null) ||
    (state === "forgotten" && validTimestamp(forgottenAt));
  return (
    validUuid(value.id) &&
    validUuid(value.user_id) &&
    value.character_id === characterId &&
    (value.source_message_id === null || validUuid(value.source_message_id)) &&
    boundedText(value.memory_type, 80) &&
    boundedText(value.content, 1_000) &&
    finiteRange(value.importance, 0, 1) &&
    finiteRange(value.confidence, 0, 1) &&
    finiteRange(value.emotional_weight, -1, 1) &&
    typeof value.pinned === "boolean" &&
    finiteRange(value.decay_score, 0, 1) &&
    (value.contradiction_group === null || boundedText(value.contradiction_group, 120)) &&
    (value.last_recalled_at === null || validTimestamp(value.last_recalled_at)) &&
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
    !integerRange(value.intensity, 0, 3)
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

export function completeScheduledJobs(value: unknown): ScheduledJob[] | null {
  if (!completeUniqueList<ScheduledJob>(value, 50, isCompleteScheduledJob)) {
    return null;
  }
  return value;
}

export function completeDebugPayload(
  value: unknown,
  characterId: string
): DebugPayload | null {
  if (!record(value) || !boundedJson(value, 256_000)) {
    return null;
  }
  const runtime = value.runtime;
  const relationship = value.relationship;
  const memories = value.memories;
  const journals = value.journals;
  const errors = value.errors;
  const promptContext = value.prompt_context;
  if (
    !validDebugRuntime(runtime) ||
    !validDebugRelationship(relationship) ||
    !completeUniqueList<NonNullable<DebugPayload["memories"]>[number]>(
      memories,
      10,
      validDebugMemory
    ) ||
    !completeUniqueList<NonNullable<DebugPayload["journals"]>[number]>(
      journals,
      4,
      validDebugJournal
    ) ||
    !completeUniqueList<NonNullable<DebugPayload["errors"]>[number]>(
      errors,
      20,
      validDiagnosticEvent
    ) ||
    !validPromptContext(promptContext, characterId)
  ) {
    return null;
  }
  return {
    runtime,
    relationship,
    memories,
    journals,
    errors,
    prompt_context: promptContext
  };
}

export function completeConversationDebugPayload(
  value: unknown,
  conversationId: string,
  characterId: string
): ConversationDebugPayload | null {
  if (!record(value) || !boundedJson(value, 256_000)) {
    return null;
  }
  const conversation = value.conversation;
  const pipeline = value.memory_pipeline;
  const lastContext = value.last_assembled_context;
  if (
    !record(conversation) ||
    conversation.id !== conversationId ||
    conversation.character_id !== characterId ||
    (conversation.title !== null && !boundedText(conversation.title, 200)) ||
    !completeUniqueList<
      NonNullable<ConversationDebugPayload["memory_pipeline"]>[number]
    >(pipeline, 20, validMemoryPipelineRow, "message_id") ||
    (lastContext !== null && !validAssembledContext(lastContext, characterId))
  ) {
    return null;
  }
  return {
    conversation: conversation as NonNullable<ConversationDebugPayload["conversation"]>,
    memory_pipeline: pipeline,
    last_assembled_context: lastContext as AssembledContext | null
  };
}

export function completeHealthPayload(
  value: unknown
): { status: "ok" | "degraded"; provider?: string } | null {
  if (
    !record(value) ||
    (value.status !== "ok" && value.status !== "degraded") ||
    (value.provider !== undefined && !safeLabel(value.provider, 80))
  ) {
    return null;
  }
  return typeof value.provider === "string"
    ? { status: value.status, provider: value.provider }
    : { status: value.status };
}

function isCompleteScheduledJob(value: unknown): value is ScheduledJob {
  if (!record(value) || !boundedJson(value)) {
    return false;
  }
  const statusValid =
    value.status === "pending" ||
    value.status === "running" ||
    value.status === "done" ||
    value.status === "failed";
  const lockValid =
    value.status === "running"
      ? validTimestamp(value.locked_at) && boundedText(value.locked_by, 200)
      : value.locked_at === null && value.locked_by === null;
  return (
    validUuid(value.id) &&
    boundedText(value.job_type, 120) &&
    statusValid &&
    validTimestamp(value.run_at) &&
    lockValid &&
    record(value.payload_json) &&
    integerRange(value.retry_count, 0, 1_000) &&
    (value.last_error === null || boundedText(value.last_error, 1_000))
  );
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

function validDebugRuntime(value: unknown): value is NonNullable<DebugPayload["runtime"]> {
  return (
    record(value) &&
    typeof value.scheduler_enabled === "boolean" &&
    typeof value.scheduler_running === "boolean" &&
    integerRange(value.scheduler_interval_seconds, 1, 86_400) &&
    integerRange(value.scheduler_job_limit, 1, 1_000) &&
    integerRange(value.scheduler_max_retries, 0, 100)
  );
}

function validDebugRelationship(
  value: unknown
): value is NonNullable<DebugPayload["relationship"]> {
  return (
    record(value) &&
    finiteRange(value.trust, 0, 1) &&
    finiteRange(value.intimacy, 0, 1) &&
    finiteRange(value.warmth, 0, 1) &&
    finiteRange(value.tension, 0, 1) &&
    finiteRange(value.familiarity, 0, 1) &&
    finiteRange(value.attachment, 0, 1) &&
    boundedText(value.mood, 80) &&
    boundedText(value.conflict_state, 80) &&
    typeof value.repair_needed === "boolean" &&
    boundedStringList(value.tags_json, 32, 80) &&
    (value.timeline === undefined ||
      (Array.isArray(value.timeline) &&
        value.timeline.length <= 100 &&
        value.timeline.every(
          (item) =>
            record(item) &&
            (item.at === undefined || validTimestamp(item.at)) &&
            (item.kind === undefined || boundedText(item.kind, 80)) &&
            (item.summary === undefined || boundedText(item.summary, 500)) &&
            (item.tags === undefined || boundedStringList(item.tags, 16, 80))
        )))
  );
}

function validDebugMemory(
  value: unknown
): value is NonNullable<DebugPayload["memories"]>[number] {
  return (
    record(value) &&
    validUuid(value.id) &&
    boundedText(value.memory_type, 80) &&
    boundedText(value.content, 1_000) &&
    finiteRange(value.importance, 0, 1) &&
    finiteRange(value.confidence, 0, 1) &&
    typeof value.pinned === "boolean"
  );
}

function validDebugJournal(
  value: unknown
): value is NonNullable<DebugPayload["journals"]>[number] {
  return (
    record(value) &&
    validUuid(value.id) &&
    boundedText(value.journal_type, 80) &&
    boundedText(value.title, 200) &&
    boundedText(value.summary, 2_000) &&
    finiteRange(value.importance, 0, 1)
  );
}

function validDiagnosticEvent(
  value: unknown
): value is NonNullable<DebugPayload["errors"]>[number] {
  const diagnosticCodes = new Set([
    "authentication",
    "context_overflow",
    "generation_failed",
    "malformed_response",
    "model_unavailable",
    "provider_unavailable",
    "quota_exhausted",
    "rate_limited",
    "refusal",
    "timeout",
  ]);
  return (
    record(value) &&
    validUuid(value.id) &&
    (value.conversation_id === null || validUuid(value.conversation_id)) &&
    value.source === "chat" &&
    (value.operation === "message" ||
      value.operation === "stream" ||
      value.operation === "reroll" ||
      value.operation === "edit") &&
    typeof value.code === "string" &&
    diagnosticCodes.has(value.code) &&
    safeLabel(value.provider, 80) &&
    boundedText(value.safe_message, 500) &&
    validTimestamp(value.created_at)
  );
}

function validPromptContext(
  value: unknown,
  characterId: string
): value is NonNullable<DebugPayload["prompt_context"]> {
  if (
    !record(value) ||
    !safeLabel(value.prompt_version, 120) ||
    (value.content_mode !== "sfw" && value.content_mode !== "adult") ||
    !safeLabel(value.llm_provider, 80) ||
    !record(value.current_summary)
  ) {
    return false;
  }
  const summary = value.current_summary;
  return (
    boundedText(summary.snapshot_at, 80) &&
    validCharacterReference(summary.character, characterId) &&
    validContextRelationship(summary.relationship) &&
    completeUniqueList(summary.retrieved_memories, 12, validContextMemory) &&
    completeUniqueList(summary.journals, 8, validContextJournal) &&
    boundedStringList(summary.pending_proactive_events, 8, 80) &&
    validContextSafety(summary.safety)
  );
}

function validMemoryPipelineRow(value: unknown): boolean {
  if (
    !record(value) ||
    !validUuid(value.message_id) ||
    !validTimestamp(value.created_at) ||
    (value.content_mode !== "sfw" && value.content_mode !== "adult") ||
    (value.privacy_mode !== "normal" && value.privacy_mode !== "private") ||
    !record(value.decision)
  ) {
    return false;
  }
  const decision = value.decision;
  return (
    typeof decision.accepted === "boolean" &&
    boundedText(decision.reason, 160) &&
    (decision.memory_type === undefined || boundedText(decision.memory_type, 80)) &&
    (decision.trigger === undefined || boundedText(decision.trigger, 160)) &&
    (decision.importance === undefined || finiteRange(decision.importance, 0, 1)) &&
    (decision.confidence === undefined || finiteRange(decision.confidence, 0, 1)) &&
    (decision.emotional_weight === undefined ||
      finiteRange(decision.emotional_weight, -1, 1)) &&
    (value.stored_memory === null || validStoredMemory(value.stored_memory))
  );
}

function validStoredMemory(value: unknown): boolean {
  return (
    record(value) &&
    validUuid(value.id) &&
    boundedText(value.memory_type, 80) &&
    finiteRange(value.importance, 0, 1) &&
    finiteRange(value.confidence, 0, 1)
  );
}

function validAssembledContext(value: unknown, characterId: string): value is AssembledContext {
  if (
    !record(value) ||
    value.schema_version !== 1 ||
    !validTimestamp(value.assembled_at) ||
    (value.generation_kind !== "chat" &&
      value.generation_kind !== "stream" &&
      value.generation_kind !== "reroll" &&
      value.generation_kind !== "edit") ||
    !safeLabel(value.provider, 80) ||
    !safeLabel(value.prompt_version, 120) ||
    (value.content_mode !== "sfw" && value.content_mode !== "adult") ||
    !integerRange(value.prompt_chars, 0, 100_000) ||
    !boundedText(value.response_plan_summary, 1_200) ||
    !record(value.context_manifest)
  ) {
    return false;
  }
  const manifest = value.context_manifest;
  return (
    validCharacterReference(manifest.character, characterId) &&
    validContextRelationship(manifest.relationship) &&
    (manifest.scenario === undefined || validContextScenario(manifest.scenario)) &&
    completeUniqueList(manifest.memory_items, 12, validContextMemory) &&
    completeUniqueList(manifest.journal_items, 8, validContextJournal) &&
    completeUniqueList(manifest.recent_messages, 12, validRecentMessage) &&
    validContextSafety(manifest.safety) &&
    boundedText(manifest.time_context, 80) &&
    integerRange(manifest.current_message_chars, 0, 6_000)
  );
}

function validCharacterReference(value: unknown, characterId: string): boolean {
  return record(value) && value.id === characterId && boundedText(value.name, 120);
}

function validContextRelationship(value: unknown): boolean {
  return (
    record(value) &&
    boundedText(value.mood, 80) &&
    boundedText(value.conflict_state, 80) &&
    typeof value.repair_needed === "boolean"
  );
}

function validContextMemory(value: unknown): boolean {
  return (
    record(value) &&
    validUuid(value.id) &&
    boundedText(value.memory_type, 80) &&
    typeof value.pinned === "boolean"
  );
}

function validContextJournal(value: unknown): boolean {
  return (
    record(value) &&
    validUuid(value.id) &&
    boundedText(value.journal_type, 80) &&
    boundedStringList(value.continuity_signals, 8, 80)
  );
}

function validContextSafety(value: unknown): boolean {
  return (
    record(value) &&
    (value.effective_mode === "sfw" || value.effective_mode === "adult") &&
    typeof value.allowed === "boolean" &&
    value.allowed === (value.effective_mode === "adult") &&
    boundedStringList(value.reasons, 8, 160) &&
    integerRange(value.intensity, 0, 3)
  );
}

function validContextScenario(value: unknown): boolean {
  return (
    record(value) &&
    (value.mode === "default" || value.mode === "custom") &&
    integerRange(value.text_chars, 0, 1_200)
  );
}

function validRecentMessage(value: unknown): boolean {
  return (
    record(value) &&
    validUuid(value.id) &&
    (value.role === "user" || value.role === "assistant" || value.role === "system") &&
    (value.privacy_mode === "normal" || value.privacy_mode === "private")
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

function safeLabel(value: unknown, limit: number): value is string {
  return (
    boundedText(value, limit) &&
    [...value].every((character) => /[A-Za-z0-9_.:-]/.test(character))
  );
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
