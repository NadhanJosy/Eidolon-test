import type { Message } from "./types";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const OFFSET_TIMESTAMP_PATTERN = /(?:Z|[+-]\d{2}:\d{2})$/;
const MAX_CONTENT_LENGTH = 24_000;
const MAX_METADATA_BYTES = 16_000;
const MAX_METADATA_DEPTH = 5;
const MAX_METADATA_COLLECTION_SIZE = 64;
const MAX_METADATA_KEY_LENGTH = 80;
const MAX_METADATA_STRING_LENGTH = 6_000;

export function completeMessage(
  value: unknown,
  expectedConversationId?: string
): Message | null {
  if (!plainObject(value)) {
    return null;
  }
  const metadata = completeMetadata(value.metadata_json);
  if (
    !validUuid(value.id) ||
    !validUuid(value.conversation_id) ||
    (expectedConversationId !== undefined &&
      value.conversation_id !== expectedConversationId) ||
    (value.role !== "user" && value.role !== "assistant" && value.role !== "system") ||
    typeof value.content !== "string" ||
    value.content.length === 0 ||
    value.content.length > MAX_CONTENT_LENGTH ||
    metadata === null ||
    !validTimestamp(value.created_at)
  ) {
    return null;
  }
  return {
    id: value.id,
    conversation_id: value.conversation_id,
    role: value.role,
    content: value.content,
    metadata_json: metadata,
    created_at: value.created_at
  };
}

export function completeMessageList(
  value: unknown,
  conversationId: string
): Message[] | null {
  if (!Array.isArray(value)) {
    return null;
  }
  const messages: Message[] = [];
  const ids = new Set<string>();
  let previousTimestamp = Number.NEGATIVE_INFINITY;
  for (const item of value) {
    const message = completeMessage(item, conversationId);
    if (!message || ids.has(message.id)) {
      return null;
    }
    const timestamp = Date.parse(message.created_at);
    if (timestamp < previousTimestamp) {
      return null;
    }
    ids.add(message.id);
    messages.push(message);
    previousTimestamp = timestamp;
  }
  return messages;
}

function completeMetadata(value: unknown): Message["metadata_json"] | null {
  if (!plainObject(value) || !validJsonNode(value, 0)) {
    return null;
  }
  if (Object.keys(value).some((key) => key.startsWith("_"))) {
    return null;
  }
  if (
    (value.content_mode !== undefined &&
      value.content_mode !== "sfw" &&
      value.content_mode !== "adult") ||
    (value.privacy_mode !== undefined &&
      value.privacy_mode !== "normal" &&
      value.privacy_mode !== "private")
  ) {
    return null;
  }
  try {
    if (new TextEncoder().encode(JSON.stringify(value)).length > MAX_METADATA_BYTES) {
      return null;
    }
  } catch {
    return null;
  }
  return value as Message["metadata_json"];
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

function validTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    OFFSET_TIMESTAMP_PATTERN.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}

function validUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function plainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
