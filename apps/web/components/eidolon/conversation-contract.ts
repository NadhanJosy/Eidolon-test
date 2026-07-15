import type { Conversation, ConversationPrivacyMode } from "./types";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const OFFSET_TIMESTAMP_PATTERN = /(?:Z|[+-]\d{2}:\d{2})$/;
const CONTROL_CHARACTER_PATTERN = /[\p{Cc}\p{Cf}]/u;
const MAX_TITLE_LENGTH = 200;
const MAX_SCENARIO_LENGTH = 1200;
const MAX_METADATA_BYTES = 16_000;
const MAX_METADATA_DEPTH = 5;
const MAX_METADATA_COLLECTION_SIZE = 64;
const MAX_METADATA_KEY_LENGTH = 80;
const MAX_METADATA_STRING_LENGTH = 2000;

export type ConversationCreationExpectation = {
  ownerUserId: string;
  characterId: string;
  privacyMode: ConversationPrivacyMode;
  knownConversationIds: Set<string>;
  responseId?: string | null;
};

export type ConversationScenarioExpectation =
  | { mode: "default" }
  | { mode: "custom"; text: string };

export function canonicalConversationTitle(value: string): string | null | undefined {
  if (value.length > MAX_TITLE_LENGTH || CONTROL_CHARACTER_PATTERN.test(value)) {
    return undefined;
  }
  return normalizeText(value) || null;
}

export function ownedConversation(
  value: unknown,
  ownerUserId: string
): Conversation | null {
  if (!plainObject(value)) {
    return null;
  }
  const candidate = value as Record<string, unknown>;
  const title = normalizedOptionalTitle(candidate.title);
  const metadata = validConversationMetadata(candidate.metadata_json);
  const createdAt = validTimestamp(candidate.created_at);
  const updatedAt = validTimestamp(candidate.updated_at);
  const lastReadAt = validTimestamp(candidate.last_read_at);
  const lastMessageAt = nullableTimestamp(candidate.last_message_at);
  if (
    !validUuid(candidate.id) ||
    candidate.user_id !== ownerUserId ||
    !validUuid(candidate.character_id) ||
    title === undefined ||
    metadata === null ||
    createdAt === null ||
    updatedAt === null ||
    lastReadAt === null ||
    lastMessageAt === undefined ||
    !Number.isSafeInteger(candidate.unread_count) ||
    (candidate.unread_count as number) < 0 ||
    updatedAt < createdAt ||
    (lastMessageAt !== null && lastMessageAt < createdAt)
  ) {
    return null;
  }
  return {
    id: candidate.id as string,
    user_id: ownerUserId,
    character_id: candidate.character_id as string,
    title,
    metadata_json: metadata,
    last_read_at: candidate.last_read_at as string,
    last_message_at: candidate.last_message_at as string | null,
    unread_count: candidate.unread_count as number,
    created_at: candidate.created_at as string,
    updated_at: candidate.updated_at as string
  };
}

export function ownedConversationList(
  value: unknown,
  ownerUserId: string
): Conversation[] | null {
  if (!Array.isArray(value)) {
    return null;
  }
  const conversations: Conversation[] = [];
  const ids = new Set<string>();
  for (const item of value) {
    const conversation = ownedConversation(item, ownerUserId);
    if (!conversation || ids.has(conversation.id)) {
      return null;
    }
    ids.add(conversation.id);
    conversations.push(conversation);
  }
  return conversations;
}

export function conversationMatchesCreation(
  conversation: Conversation,
  characterId: string,
  privacyMode: ConversationPrivacyMode
): boolean {
  return (
    conversation.character_id === characterId &&
    conversation.metadata_json.privacy_mode === privacyMode &&
    conversation.metadata_json.scenario_mode === "default" &&
    conversation.last_message_at === null &&
    conversation.unread_count === 0
  );
}

export function conversationMatchesTitle(
  conversation: Conversation,
  title: string | null
): boolean {
  return conversation.title === title;
}

export function conversationMatchesPrivacy(
  conversation: Conversation,
  privacyMode: ConversationPrivacyMode
): boolean {
  return conversationPrivacyModeValue(conversation) === privacyMode;
}

export function conversationMatchesScenario(
  conversation: Conversation,
  scenario: ConversationScenarioExpectation
): boolean {
  if (conversation.metadata_json.scenario_mode !== scenario.mode) {
    return false;
  }
  return scenario.mode === "custom"
    ? conversation.metadata_json.scenario_text === scenario.text
    : conversation.metadata_json.scenario_text === undefined;
}

export function advancedConversationSummary(
  current: Conversation,
  next: Conversation
): Conversation | null {
  if (
    current.id !== next.id ||
    current.user_id !== next.user_id ||
    current.character_id !== next.character_id ||
    current.created_at !== next.created_at
  ) {
    return null;
  }

  const currentUpdatedAt = Date.parse(current.updated_at);
  const nextUpdatedAt = Date.parse(next.updated_at);
  const currentReadAt = Date.parse(current.last_read_at);
  const nextReadAt = Date.parse(next.last_read_at);
  const currentMessageAt = nullableTimestampValue(current.last_message_at);
  const nextMessageAt = nullableTimestampValue(next.last_message_at);
  const base = nextUpdatedAt >= currentUpdatedAt ? next : current;
  const nextCoversLatestMessage = nextMessageAt >= currentMessageAt;
  const nextHasCurrentReadCursor = nextReadAt >= currentReadAt;

  return {
    ...base,
    last_read_at: nextHasCurrentReadCursor ? next.last_read_at : current.last_read_at,
    last_message_at:
      nextMessageAt >= currentMessageAt ? next.last_message_at : current.last_message_at,
    unread_count:
      nextCoversLatestMessage && nextHasCurrentReadCursor
        ? next.unread_count
        : current.unread_count
  };
}

export function recoveredCreatedConversation({
  value,
  ownerUserId,
  characterId,
  privacyMode,
  knownConversationIds,
  responseId
}: ConversationCreationExpectation & { value: unknown }): {
  conversation: Conversation;
  conversations: Conversation[];
} | null {
  const conversations = ownedConversationList(value, ownerUserId);
  if (!conversations) {
    return null;
  }
  const candidates = conversations.filter(
    (conversation) =>
      !knownConversationIds.has(conversation.id) &&
      conversationMatchesCreation(conversation, characterId, privacyMode)
  );
  const responseMatch = responseId
    ? candidates.find((conversation) => conversation.id === responseId)
    : null;
  const conversation = responseMatch ?? (candidates.length === 1 ? candidates[0] : null);
  return conversation ? { conversation, conversations } : null;
}

export function possibleConversationId(value: unknown): string | null {
  return plainObject(value) && validUuid(value.id) ? value.id : null;
}

export function hasPositiveDeleteCount(value: unknown): boolean {
  return (
    plainObject(value) &&
    Number.isSafeInteger(value.deleted) &&
    (value.deleted as number) > 0
  );
}

function validConversationMetadata(
  value: unknown
): Conversation["metadata_json"] | null {
  if (!plainObject(value) || !validJsonNode(value, 0)) {
    return null;
  }
  let encoded: string;
  try {
    encoded = JSON.stringify(value);
  } catch {
    return null;
  }
  if (new TextEncoder().encode(encoded).length > MAX_METADATA_BYTES) {
    return null;
  }
  const privacyMode = value.privacy_mode;
  const scenarioMode = value.scenario_mode ?? "default";
  if (
    (privacyMode !== "normal" && privacyMode !== "private") ||
    (scenarioMode !== "default" && scenarioMode !== "custom")
  ) {
    return null;
  }
  if (scenarioMode === "custom") {
    if (
      typeof value.scenario_text !== "string" ||
      value.scenario_text.length > MAX_SCENARIO_LENGTH ||
      CONTROL_CHARACTER_PATTERN.test(value.scenario_text) ||
      normalizeText(value.scenario_text) !== value.scenario_text
    ) {
      return null;
    }
  } else if (value.scenario_text !== undefined && value.scenario_text !== null) {
    return null;
  }
  const metadata: Conversation["metadata_json"] = {
    ...value,
    privacy_mode: privacyMode,
    scenario_mode: scenarioMode
  };
  if (scenarioMode === "default") {
    delete metadata.scenario_text;
  }
  return metadata;
}

function conversationPrivacyModeValue(
  conversation: Conversation
): ConversationPrivacyMode | null {
  const value = conversation.metadata_json.privacy_mode;
  return value === "normal" || value === "private" ? value : null;
}

function validJsonNode(value: unknown, depth: number): boolean {
  if (value === null || typeof value === "boolean") {
    return true;
  }
  if (typeof value === "number") {
    return Number.isFinite(value);
  }
  if (typeof value === "string") {
    return value.length <= MAX_METADATA_STRING_LENGTH;
  }
  if (depth >= MAX_METADATA_DEPTH) {
    return false;
  }
  if (Array.isArray(value)) {
    return (
      value.length <= MAX_METADATA_COLLECTION_SIZE &&
      value.every((item) => validJsonNode(item, depth + 1))
    );
  }
  if (!plainObject(value)) {
    return false;
  }
  const entries = Object.entries(value);
  return (
    entries.length <= MAX_METADATA_COLLECTION_SIZE &&
    entries.every(
      ([key, item]) =>
        key.length <= MAX_METADATA_KEY_LENGTH && validJsonNode(item, depth + 1)
    )
  );
}

function normalizedOptionalTitle(value: unknown): string | null | undefined {
  if (value === null) {
    return null;
  }
  if (
    typeof value !== "string" ||
    value.length > MAX_TITLE_LENGTH ||
    CONTROL_CHARACTER_PATTERN.test(value)
  ) {
    return undefined;
  }
  const normalized = normalizeText(value);
  return normalized && normalized === value ? value : undefined;
}

function normalizeText(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

function validTimestamp(value: unknown): number | null {
  if (typeof value !== "string" || !OFFSET_TIMESTAMP_PATTERN.test(value)) {
    return null;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function nullableTimestamp(value: unknown): number | null | undefined {
  if (value === null) {
    return null;
  }
  const parsed = validTimestamp(value);
  return parsed === null ? undefined : parsed;
}

function nullableTimestampValue(value: string | null): number {
  return value === null ? Number.NEGATIVE_INFINITY : Date.parse(value);
}

function validUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function plainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
