import type { Character, CharacterDraft, Message, Relationship } from "./types";

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
  metadata_json: {}
};

export function emptyCharacterDraft(): CharacterDraft {
  return {
    name: "",
    description: "",
    personality_core: "",
    speech_style: "",
    explicit_age: "",
    adult_mode_allowed: false,
    content_intensity: "0"
  };
}

export function toCharacterDraft(character: Character): CharacterDraft {
  return {
    name: character.name,
    description: character.description ?? "",
    personality_core: character.personality_core ?? "",
    speech_style: character.speech_style ?? "",
    explicit_age: character.explicit_age?.toString() ?? "",
    adult_mode_allowed: character.adult_mode_allowed,
    content_intensity: character.content_intensity.toString()
  };
}

export function isMessage(value: unknown): value is Message {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    "role" in value &&
    "content" in value
  );
}

export function readError(caught: unknown) {
  if (caught instanceof Error) {
    return caught.message;
  }
  return "The backend did not answer cleanly.";
}
