import type {
  AdultStatus,
  Journal,
  MemoryItem,
  Relationship,
  RelationshipEvent,
  RelationshipRecentChange,
  ScheduledJob
} from "./types";

export type Tone = "quiet" | "warm" | "alert" | "cool";

export type SummaryCard = {
  label: string;
  value: string;
  detail: string;
  tone: Tone;
};

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

export function memoryResonance(memory: MemoryItem): string {
  if (hasActiveMemoryConflict(memory)) {
    return "needs review";
  }
  if (memory.pinned) {
    return "anchored";
  }
  if (memory.importance >= 0.75 && memory.confidence >= 0.75) {
    return "strong recall";
  }
  if (memory.importance >= 0.55 || memory.emotional_weight >= 0.35) {
    return "meaningful";
  }
  if (memory.confidence < 0.45) {
    return "tentative";
  }
  return "ordinary";
}

export function memoryFreshness(memory: MemoryItem): string {
  if (memory.last_recalled_at) {
    return "recently recalled";
  }
  if (memory.decay_score >= 0.75) {
    return "fading";
  }
  if (memory.decay_score >= 0.45) {
    return "softening";
  }
  return "available";
}

export function memorySourceLabel(memory: MemoryItem): string {
  const source = memory.metadata_json.source;
  if (source === "manual") {
    return "saved by hand";
  }
  if (source === "extracted") {
    return "learned from chat";
  }
  if (source === "user_saved") {
    return "kept from chat";
  }
  return "stored";
}

export function memoryOverviewCards(memories: MemoryItem[]): SummaryCard[] {
  const anchored = memories.filter((memory) => memory.pinned).length;
  const reviews = memories.filter((memory) => hasActiveMemoryConflict(memory)).length;
  const emotional = memories.filter((memory) => Math.abs(memory.emotional_weight) >= 0.3).length;
  return [
    {
      label: "Recall",
      value: memories.length === 0 ? "quiet" : `${memories.length} kept`,
      detail: memories.length === 0 ? "nothing durable yet" : "available for future replies",
      tone: "quiet"
    },
    {
      label: "Anchors",
      value: anchored === 0 ? "none pinned" : `${anchored} anchored`,
      detail: anchored === 0 ? "important notes can be pinned" : "protected from forgetting",
      tone: anchored > 0 ? "warm" : "quiet"
    },
    {
      label: "Texture",
      value: emotional === 0 ? "practical" : "emotion-aware",
      detail: reviews > 0 ? "some memories need review" : "no contradictions surfaced",
      tone: reviews > 0 ? "alert" : emotional > 0 ? "warm" : "quiet"
    }
  ];
}

export function hasActiveMemoryConflict(memory: MemoryItem): boolean {
  return (
    memory.metadata_json.contradiction_status === "conflicts" ||
    typeof memory.metadata_json.contradicts_memory_id === "string" ||
    typeof memory.metadata_json.contradicted_by_memory_id === "string"
  );
}

export function journalOverviewCards(journals: Journal[]): SummaryCard[] {
  const unresolved = journals.reduce(
    (total, journal) => total + journal.unresolved_threads_json.length,
    0
  );
  const callbacks = journals.reduce((total, journal) => total + journal.callbacks_json.length, 0);
  const emotional = journals.reduce(
    (total, journal) => total + journal.emotional_tags_json.length,
    0
  );
  const continuity = journals.filter((journal) => journalContinuityLabels(journal).length > 0)
    .length;
  return [
    {
      label: "Episodes",
      value: journals.length === 0 ? "none yet" : `${journals.length} logged`,
      detail:
        journals.length === 0
          ? "shared moments will gather here"
          : continuity > 0
            ? "continuity signals active"
            : "summaries are active",
      tone: "quiet"
    },
    {
      label: "Open Loops",
      value: unresolved === 0 ? "clear" : `${unresolved} open`,
      detail: unresolved === 0 ? "no unresolved threads" : "worth returning to",
      tone: unresolved > 0 ? "alert" : "warm"
    },
    {
      label: "Callbacks",
      value: callbacks === 0 ? "waiting" : `${callbacks} ready`,
      detail: emotional > 0 ? "emotional markers available" : "inside references can grow",
      tone: callbacks > 0 || emotional > 0 ? "warm" : "quiet"
    }
  ];
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

export function journalContinuityLabels(journal: Journal): string[] {
  return journalContinuitySignalKeys(journal).map((signal) => JOURNAL_SIGNAL_LABELS[signal]);
}

export function journalContinuityNotes(journal: Journal): string[] {
  const rawNotes = journal.metadata_json?.continuity_notes;
  if (!Array.isArray(rawNotes)) {
    return [];
  }
  const notes: string[] = [];
  for (const note of rawNotes) {
    if (typeof note !== "string") {
      continue;
    }
    const compact = compactText(note, 180);
    if (compact.length > 0) {
      notes.push(compact);
    }
    if (notes.length >= 3) {
      break;
    }
  }
  return notes;
}

export function journalIsAdultRedacted(journal: Journal): boolean {
  return (
    journal.metadata_json?.redacted_adult === true ||
    journalContinuitySignalKeys(journal).includes("adult_redacted")
  );
}

export function relationshipCards(relationship: Relationship): SummaryCard[] {
  return [
    {
      label: "Phase",
      value: relationshipPhase(relationship),
      detail: relationship.repair_needed ? "repair should come first" : "stable enough to deepen",
      tone: relationship.repair_needed ? "alert" : "warm"
    },
    {
      label: "Temperature",
      value: relationshipTemperature(relationship),
      detail: relationship.conflict_state === "clear" ? "clear channel" : "move gently",
      tone: relationship.tension > 8 ? "alert" : relationship.warmth > 4 ? "warm" : "quiet"
    },
    {
      label: "Momentum",
      value: relationshipMomentum(relationship),
      detail: relationship.last_interaction_at ? "recent state is active" : "waiting for history",
      tone: relationship.familiarity > 8 ? "warm" : "quiet"
    }
  ];
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

export function overviewCards({
  relationship,
  memories,
  journals,
  jobs,
  adultStatus
}: {
  relationship: Relationship;
  memories: MemoryItem[];
  journals: Journal[];
  jobs: ScheduledJob[];
  adultStatus: AdultStatus | null;
}): SummaryCard[] {
  const dueJobs = jobs.filter((job) => job.status === "pending").length;
  return [
    {
      label: "Bond",
      value: relationshipPhase(relationship),
      detail: relationshipTemperature(relationship),
      tone: relationship.repair_needed ? "alert" : "warm"
    },
    {
      label: "Memory",
      value: memories.length === 0 ? "blank slate" : `${memories.length} remembered`,
      detail: memories.some((memory) => memory.pinned) ? "anchored recall present" : "recall active",
      tone: memories.length > 0 ? "warm" : "quiet"
    },
    {
      label: "Journal",
      value: journals.length === 0 ? "unwritten" : `${journals.length} episodes`,
      detail: journals.some((journal) => journal.callbacks_json.length > 0)
        ? "callbacks available"
        : "continuity notes",
      tone: journals.length > 0 ? "warm" : "quiet"
    },
    {
      label: "Presence",
      value: dueJobs === 0 ? "quiet" : "queued",
      detail: adultStatus?.effective_mode === "adult" ? "adult gates active" : "safe mode",
      tone: dueJobs > 0 ? "cool" : "quiet"
    }
  ];
}

export function toneClass(tone: Tone): string {
  const classes: Record<Tone, string> = {
    quiet: "border-line bg-ink",
    warm: "border-moss/60 bg-lime-950/30",
    alert: "border-ember/70 bg-amber-950/40",
    cool: "border-tide/60 bg-cyan-950/30"
  };
  return classes[tone];
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

function compactText(value: string, limit: number): string {
  const compact = value.trim().replace(/\s+/g, " ");
  if (compact.length <= limit) {
    return compact;
  }
  return `${compact.slice(0, Math.max(0, limit - 3)).trimEnd()}...`;
}
