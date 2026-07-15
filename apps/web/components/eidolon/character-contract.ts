import type { Character } from "./types";

export type CharacterPayload = {
  name: string;
  description: string | null;
  personality_core: string | null;
  speech_style: string | null;
  boundaries_json: Record<string, unknown>;
  explicit_age: number | null;
  adult_mode_allowed: boolean;
  content_intensity: number;
};

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const MAX_PROFILE_BYTES = 32_000;
const MAX_PROFILE_DEPTH = 6;
const MAX_COLLECTION_LENGTH = 100;
const MAX_KEY_LENGTH = 80;
const MAX_PROFILE_STRING_LENGTH = 4_000;

export function ownedCharacter(value: unknown, ownerUserId: string): Character | null {
  if (!isRecord(value) || !isUuid(ownerUserId)) {
    return null;
  }
  if (
    !isUuid(value.id) ||
    value.owner_user_id !== ownerUserId ||
    !isNormalizedName(value.name) ||
    !isNullableBoundedString(value.description, 2_000) ||
    !isNullableBoundedString(value.personality_core, 4_000) ||
    !isNullableBoundedString(value.speech_style, 2_000) ||
    !isBoundedProfile(value.boundaries_json) ||
    !isExplicitAge(value.explicit_age) ||
    typeof value.adult_mode_allowed !== "boolean" ||
    !Number.isInteger(value.content_intensity) ||
    Number(value.content_intensity) < 0 ||
    Number(value.content_intensity) > 3 ||
    !isTimestamp(value.created_at) ||
    !isTimestamp(value.updated_at)
  ) {
    return null;
  }
  if (Date.parse(value.updated_at) < Date.parse(value.created_at)) {
    return null;
  }
  if (
    value.adult_mode_allowed
      ? value.explicit_age === null || Number(value.explicit_age) < 18
      : value.content_intensity !== 0
  ) {
    return null;
  }
  return value as Character;
}

export function ownedCharacterList(
  value: unknown,
  ownerUserId: string
): Character[] | null {
  if (!Array.isArray(value)) {
    return null;
  }
  const characters: Character[] = [];
  const ids = new Set<string>();
  for (const item of value) {
    const character = ownedCharacter(item, ownerUserId);
    if (!character || ids.has(character.id)) {
      return null;
    }
    ids.add(character.id);
    characters.push(character);
  }
  return characters;
}

export function recoveredCreatedCharacter({
  value,
  ownerUserId,
  knownCharacterIds,
  payload,
  responseId
}: {
  value: unknown;
  ownerUserId: string;
  knownCharacterIds: ReadonlySet<string>;
  payload: CharacterPayload;
  responseId: string | null;
}): { character: Character; characters: Character[] } | null {
  const characters = ownedCharacterList(value, ownerUserId);
  if (!characters) {
    return null;
  }
  const candidates = characters.filter(
    (character) =>
      !knownCharacterIds.has(character.id) && characterMatchesPayload(character, payload)
  );
  if (responseId) {
    const exact = candidates.find((character) => character.id === responseId);
    if (exact) {
      return { character: exact, characters };
    }
  }
  return candidates.length === 1
    ? { character: candidates[0], characters }
    : null;
}

export function characterMatchesPayload(
  character: Character,
  payload: CharacterPayload
): boolean {
  return (
    character.name === payload.name &&
    character.description === payload.description &&
    character.personality_core === payload.personality_core &&
    character.speech_style === payload.speech_style &&
    character.explicit_age === payload.explicit_age &&
    character.adult_mode_allowed === payload.adult_mode_allowed &&
    character.content_intensity === payload.content_intensity &&
    jsonValuesEqual(character.boundaries_json, payload.boundaries_json)
  );
}

export function possibleCharacterId(value: unknown): string | null {
  return isRecord(value) && isUuid(value.id) ? value.id : null;
}

function isBoundedProfile(value: unknown): value is Record<string, unknown> {
  if (!isRecord(value)) {
    return false;
  }
  try {
    if (new TextEncoder().encode(JSON.stringify(value)).length > MAX_PROFILE_BYTES) {
      return false;
    }
  } catch {
    return false;
  }

  const pending: Array<{ value: unknown; depth: number }> = [{ value, depth: 0 }];
  while (pending.length > 0) {
    const next = pending.pop();
    if (!next || next.depth > MAX_PROFILE_DEPTH) {
      return false;
    }
    if (Array.isArray(next.value)) {
      if (next.value.length > MAX_COLLECTION_LENGTH) {
        return false;
      }
      for (const child of next.value) {
        pending.push({ value: child, depth: next.depth + 1 });
      }
      continue;
    }
    if (isRecord(next.value)) {
      const entries = Object.entries(next.value);
      if (entries.length > MAX_COLLECTION_LENGTH) {
        return false;
      }
      for (const [key, child] of entries) {
        if (key.length > MAX_KEY_LENGTH) {
          return false;
        }
        pending.push({ value: child, depth: next.depth + 1 });
      }
      continue;
    }
    if (
      next.value !== null &&
      typeof next.value !== "boolean" &&
      !(typeof next.value === "number" && Number.isFinite(next.value)) &&
      !(typeof next.value === "string" && next.value.length <= MAX_PROFILE_STRING_LENGTH)
    ) {
      return false;
    }
  }
  return true;
}

function jsonValuesEqual(left: unknown, right: unknown): boolean {
  const pending: Array<[unknown, unknown]> = [[left, right]];
  while (pending.length > 0) {
    const pair = pending.pop();
    if (!pair) {
      return false;
    }
    const [leftValue, rightValue] = pair;
    if (Object.is(leftValue, rightValue)) {
      continue;
    }
    if (Array.isArray(leftValue) || Array.isArray(rightValue)) {
      if (
        !Array.isArray(leftValue) ||
        !Array.isArray(rightValue) ||
        leftValue.length !== rightValue.length
      ) {
        return false;
      }
      for (let index = 0; index < leftValue.length; index += 1) {
        pending.push([leftValue[index], rightValue[index]]);
      }
      continue;
    }
    if (isRecord(leftValue) || isRecord(rightValue)) {
      if (!isRecord(leftValue) || !isRecord(rightValue)) {
        return false;
      }
      const leftKeys = Object.keys(leftValue);
      const rightKeys = Object.keys(rightValue);
      if (leftKeys.length !== rightKeys.length) {
        return false;
      }
      for (const key of leftKeys) {
        if (!Object.hasOwn(rightValue, key)) {
          return false;
        }
        pending.push([leftValue[key], rightValue[key]]);
      }
      continue;
    }
    return false;
  }
  return true;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function isNormalizedName(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length >= 1 &&
    value.length <= 120 &&
    value === value.trim().replace(/\s+/gu, " ") &&
    !containsControlCharacter(value)
  );
}

function isNullableBoundedString(value: unknown, maximum: number): boolean {
  return value === null || (typeof value === "string" && value.length <= maximum);
}

function isExplicitAge(value: unknown): value is number | null {
  return value === null || (Number.isInteger(value) && Number(value) >= 0 && Number(value) <= 150);
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && value.length <= 64 && Number.isFinite(Date.parse(value));
}

function containsControlCharacter(value: string): boolean {
  return /[\p{Cc}\p{Cf}]/u.test(value);
}
