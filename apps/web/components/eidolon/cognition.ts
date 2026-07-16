import type {
  Journal,
  MemoryItem,
  Relationship,
  RelationshipEvent,
  RelationshipRecentChange
} from "./types";

const JOURNAL_SIGNAL_LABELS: Record<string, string> = {
  repair_arc: "repair arc",
  anniversary: "anniversary",
  inside_joke: "inside joke",
  milestone: "milestone",
  shared_moment: "shared moment",
  shared_reference: "shared reference",
  callback_request: "callback",
  open_thread: "open thread",
  adult_redacted: "private episode",
  steady_exchange: "steady exchange"
};

export function memoryTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    preference: "preference",
    interest: "interest",
    person: "person",
    place: "place",
    date: "date",
    event: "shared moment",
    shared_moment: "shared moment",
    inside_joke: "inside joke",
    boundary: "boundary",
    relationship_milestone: "milestone"
  };
  return labels[type] ?? type.replaceAll("_", " ");
}

export function hasActiveMemoryConflict(memory: MemoryItem): boolean {
  return (
    memory.metadata_json.contradiction_status === "conflicts" ||
    typeof memory.metadata_json.contradicts_memory_id === "string" ||
    typeof memory.metadata_json.contradicted_by_memory_id === "string"
  );
}

export function journalResonance(journal: Journal): string {
  const signals = journalContinuitySignalKeys(journal);
  if (signals.includes("adult_redacted")) {
    return "private episode";
  }
  if (signals.includes("repair_arc") || journal.emotional_tags_json.includes("repair")) {
    return "repair arc";
  }
  if (signals.includes("anniversary")) {
    return "anniversary";
  }
  if (signals.includes("inside_joke")) {
    return "inside joke";
  }
  if (signals.includes("milestone")) {
    return "milestone";
  }
  if (signals.includes("shared_moment")) {
    return "shared moment";
  }
  if (signals.includes("shared_reference")) {
    return "shared reference";
  }
  if (journal.unresolved_threads_json.length > 0) {
    return "open thread";
  }
  if (journal.callbacks_json.length > 0) {
    return "callback ready";
  }
  if (journal.emotional_tags_json.length > 0) {
    return "emotional marker";
  }
  return "episode";
}

export function journalIsAdultRedacted(journal: Journal): boolean {
  return (
    journal.metadata_json?.redacted_adult === true ||
    journalContinuitySignalKeys(journal).includes("adult_redacted")
  );
}

export function relationshipPhase(relationship: Relationship): string {
  if (relationship.repair_needed || relationship.conflict_state === "strained") {
    return "repair arc";
  }
  if (relationship.intimacy >= 20 || relationship.attachment >= 20) {
    return "close bond";
  }
  if (relationship.trust >= 10 && relationship.warmth >= 8) {
    return "trusted warmth";
  }
  if (relationship.familiarity >= 8 || relationship.warmth >= 4) {
    return "warming up";
  }
  return "new connection";
}

export function relationshipTemperature(relationship: Relationship): string {
  if (relationship.tension >= 15) {
    return "tense";
  }
  if (relationship.tension >= 5) {
    return "careful";
  }
  if (relationship.warmth >= 12) {
    return "warm";
  }
  if (relationship.warmth <= -6) {
    return "guarded";
  }
  return "steady";
}

export function relationshipMomentum(relationship: Relationship): string {
  if (relationship.familiarity >= 20) {
    return "well-established";
  }
  if (relationship.familiarity >= 8) {
    return "building rhythm";
  }
  if (relationship.attachment >= 5) {
    return "starting to stick";
  }
  return "early days";
}

export function relationshipRecentChanges(
  relationship: Relationship
): RelationshipRecentChange[] {
  const changes = relationship.metadata_json.recent_changes;
  if (!Array.isArray(changes)) {
    return [];
  }
  return changes
    .filter((change) => typeof change.summary === "string" && change.summary.trim().length > 0)
    .slice(0, 4);
}

export function timelineSummary(event: RelationshipEvent): string {
  const summary = event.summary?.trim();
  if (!summary) {
    return event.kind ? event.kind.replaceAll("_", " ") : "state shifted";
  }
  if (/^[a-z_]+ [+-]\d/i.test(summary)) {
    return "The relationship adjusted after the last exchange.";
  }
  return summary;
}

function journalContinuitySignalKeys(journal: Journal): string[] {
  const rawSignals = journal.metadata_json?.continuity_signals;
  if (!Array.isArray(rawSignals)) {
    return [];
  }
  const signals: string[] = [];
  for (const signal of rawSignals) {
    if (
      typeof signal === "string" &&
      signal in JOURNAL_SIGNAL_LABELS &&
      !signals.includes(signal)
    ) {
      signals.push(signal);
    }
  }
  return signals;
}
