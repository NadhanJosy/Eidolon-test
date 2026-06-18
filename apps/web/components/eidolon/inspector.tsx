import type { FormEvent } from "react";

import { AdultPanel } from "./panels/adult-panel";
import { CharacterPanel } from "./panels/character-panel";
import { DataPanel } from "./panels/data-panel";
import { DebugPanel } from "./panels/debug-panel";
import { JournalPanel } from "./panels/journal-panel";
import { MemoryPanel } from "./panels/memory-panel";
import { OverviewPanel } from "./panels/overview-panel";
import { RelationshipPanel } from "./panels/relationship-panel";
import { SettingsPanel } from "./panels/settings-panel";
import type {
  AdultStatus,
  CharacterDraft,
  Conversation,
  DebugPayload,
  Journal,
  MemoryItem,
  Panel,
  Relationship,
  RelationshipEvent,
  ScheduledJob,
  User
} from "./types";
import { formatMetric } from "./ui";

type PanelItem = {
  panel: Panel;
  label: string;
  group: "State" | "Memory" | "Control";
};

const panelList: PanelItem[] = [
  { panel: "overview", label: "Overview", group: "State" },
  { panel: "relationship", label: "Bond", group: "State" },
  { panel: "character", label: "Persona", group: "State" },
  { panel: "memory", label: "Memory", group: "Memory" },
  { panel: "journal", label: "Journal", group: "Memory" },
  { panel: "adult", label: "Adult", group: "Control" },
  { panel: "settings", label: "Account", group: "Control" },
  { panel: "debug", label: "Debug", group: "Control" },
  { panel: "data", label: "Data", group: "Control" }
];

export function Inspector({
  panel,
  setPanel,
  user,
  draft,
  setDraft,
  relationship,
  timeline,
  memories,
  journals,
  jobs,
  debug,
  conversations,
  messageCount,
  activeConversationTitle,
  adultStatus,
  displayName,
  setDisplayName,
  memoryContent,
  memoryType,
  memoryImportance,
  memoryPinned,
  editingMemoryId,
  memoryEditContent,
  journalTitle,
  journalSummary,
  setMemoryContent,
  setMemoryType,
  setMemoryImportance,
  setMemoryPinned,
  setEditingMemoryId,
  setMemoryEditContent,
  setJournalTitle,
  setJournalSummary,
  onSaveCharacter,
  onToggleAgeGate,
  onSaveName,
  onAddMemory,
  onSaveMemoryEdit,
  onToggleMemoryPinned,
  onDeleteMemory,
  onForgetMemories,
  onAddJournal,
  onExport,
  onDeleteAccount,
  onClearMessages,
  onClearMemories,
  onDeleteConversation,
  onLogout
}: {
  panel: Panel;
  setPanel: (panel: Panel) => void;
  user: User;
  draft: CharacterDraft;
  setDraft: (value: CharacterDraft) => void;
  relationship: Relationship;
  timeline: RelationshipEvent[];
  memories: MemoryItem[];
  journals: Journal[];
  jobs: ScheduledJob[];
  debug: DebugPayload | null;
  conversations: Conversation[];
  messageCount: number;
  activeConversationTitle: string;
  adultStatus: AdultStatus | null;
  displayName: string;
  setDisplayName: (value: string) => void;
  memoryContent: string;
  memoryType: string;
  memoryImportance: string;
  memoryPinned: boolean;
  editingMemoryId: string | null;
  memoryEditContent: string;
  journalTitle: string;
  journalSummary: string;
  setMemoryContent: (value: string) => void;
  setMemoryType: (value: string) => void;
  setMemoryImportance: (value: string) => void;
  setMemoryPinned: (value: boolean) => void;
  setEditingMemoryId: (value: string | null) => void;
  setMemoryEditContent: (value: string) => void;
  setJournalTitle: (value: string) => void;
  setJournalSummary: (value: string) => void;
  onSaveCharacter: () => void;
  onToggleAgeGate: () => void;
  onSaveName: () => void;
  onAddMemory: (event: FormEvent<HTMLFormElement>) => void;
  onSaveMemoryEdit: (memory: MemoryItem) => void;
  onToggleMemoryPinned: (memory: MemoryItem) => void;
  onDeleteMemory: (memory: MemoryItem) => void;
  onForgetMemories: () => void;
  onAddJournal: (event: FormEvent<HTMLFormElement>) => void;
  onExport: () => void;
  onDeleteAccount: (password: string, confirmation: string) => void;
  onClearMessages: () => void;
  onClearMemories: () => void;
  onDeleteConversation: () => void;
  onLogout: () => void;
}) {
  const activePanel = panelList.find((item) => item.panel === panel) ?? panelList[0];
  const groups = ["State", "Memory", "Control"] as const;

  return (
    <aside className="rounded-lg border border-line bg-panel shadow-2xl shadow-black/30">
      <div className="border-b border-line p-3">
        <p className="text-xs uppercase text-zinc-600">Companion state</p>
        <div className="mt-1 flex items-end justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-semibold">{activePanel.label}</h2>
            <p className="truncate text-xs text-zinc-500">
              {panelSummary({
                panel,
                relationship,
                memories,
                journals,
                jobs,
                adultStatus,
                conversations,
                user
              })}
            </p>
          </div>
          <span className="rounded border border-line bg-ink px-2 py-1 text-xs text-zinc-400">
            {activePanel.group}
          </span>
        </div>
      </div>
      <div className="space-y-3 border-b border-line p-2">
        {groups.map((group) => (
          <div key={group}>
            <p className="px-1 text-[11px] uppercase text-zinc-600">{group}</p>
            <div className="mt-1 grid grid-cols-3 gap-1 text-sm">
              {panelList
                .filter((item) => item.group === group)
                .map((item) => (
                  <button
                    key={item.panel}
                    className={panelButtonClass(panel === item.panel)}
                    onClick={() => setPanel(item.panel)}
                    type="button"
                  >
                    <span className="truncate">{item.label}</span>
                    <span className="rounded bg-panel px-1.5 py-0.5 text-[10px] text-zinc-500">
                      {panelBadge({
                        panel: item.panel,
                        relationship,
                        memories,
                        journals,
                        jobs,
                        debug,
                        conversations,
                        adultStatus
                      })}
                    </span>
                  </button>
                ))}
            </div>
          </div>
        ))}
      </div>
      <div className="space-y-4 p-4">
        {panel === "overview" ? (
          <OverviewPanel
            relationship={relationship}
            memories={memories}
            journals={journals}
            jobs={jobs}
            adultStatus={adultStatus}
          />
        ) : null}
        {panel === "character" ? (
          <CharacterPanel draft={draft} setDraft={setDraft} onSave={onSaveCharacter} />
        ) : null}
        {panel === "memory" ? (
          <MemoryPanel
            memories={memories}
            memoryContent={memoryContent}
            memoryType={memoryType}
            memoryImportance={memoryImportance}
            memoryPinned={memoryPinned}
            editingMemoryId={editingMemoryId}
            memoryEditContent={memoryEditContent}
            setMemoryContent={setMemoryContent}
            setMemoryType={setMemoryType}
            setMemoryImportance={setMemoryImportance}
            setMemoryPinned={setMemoryPinned}
            setEditingMemoryId={setEditingMemoryId}
            setMemoryEditContent={setMemoryEditContent}
            onAdd={onAddMemory}
            onSaveEdit={onSaveMemoryEdit}
            onTogglePinned={onToggleMemoryPinned}
            onDelete={onDeleteMemory}
            onForget={onForgetMemories}
          />
        ) : null}
        {panel === "journal" ? (
          <JournalPanel
            journals={journals}
            title={journalTitle}
            summary={journalSummary}
            setTitle={setJournalTitle}
            setSummary={setJournalSummary}
            onAdd={onAddJournal}
          />
        ) : null}
        {panel === "relationship" ? (
          <RelationshipPanel relationship={relationship} timeline={timeline} />
        ) : null}
        {panel === "adult" ? (
          <AdultPanel
            status={adultStatus}
            user={user}
            draft={draft}
            setDraft={setDraft}
            onToggleAgeGate={onToggleAgeGate}
            onSave={onSaveCharacter}
          />
        ) : null}
        {panel === "settings" ? (
          <SettingsPanel
            user={user}
            displayName={displayName}
            setDisplayName={setDisplayName}
            onSaveName={onSaveName}
            onLogout={onLogout}
          />
        ) : null}
        {panel === "debug" ? (
          <DebugPanel debug={debug} jobs={jobs} conversations={conversations} />
        ) : null}
        {panel === "data" ? (
          <DataPanel
            messageCount={messageCount}
            memoryCount={memories.length}
            conversationCount={conversations.length}
            activeConversationTitle={activeConversationTitle}
            onExport={onExport}
            onDeleteAccount={onDeleteAccount}
            onClearMessages={onClearMessages}
            onClearMemories={onClearMemories}
            onDeleteConversation={onDeleteConversation}
          />
        ) : null}
      </div>
    </aside>
  );
}

function panelButtonClass(active: boolean) {
  return `flex min-h-11 items-center justify-between gap-1 rounded-md border px-2 py-2 text-left ${
    active
      ? "border-paper bg-paper text-ink"
      : "border-line bg-ink text-zinc-300 hover:border-zinc-500"
  }`;
}

function panelBadge({
  panel,
  relationship,
  memories,
  journals,
  jobs,
  debug,
  conversations,
  adultStatus
}: {
  panel: Panel;
  relationship: Relationship;
  memories: MemoryItem[];
  journals: Journal[];
  jobs: ScheduledJob[];
  debug: DebugPayload | null;
  conversations: Conversation[];
  adultStatus: AdultStatus | null;
}) {
  if (panel === "overview") {
    return relationship.mood;
  }
  if (panel === "relationship") {
    return formatMetric(relationship.warmth);
  }
  if (panel === "character") {
    return relationship.repair_needed ? "repair" : "ok";
  }
  if (panel === "memory") {
    return memories.length.toString();
  }
  if (panel === "journal") {
    return journals.length.toString();
  }
  if (panel === "adult") {
    return adultStatus?.effective_mode ?? "sfw";
  }
  if (panel === "settings") {
    return "user";
  }
  if (panel === "debug") {
    return debug?.prompt_context?.llm_provider ?? jobs.length.toString();
  }
  return conversations.length.toString();
}

function panelSummary({
  panel,
  relationship,
  memories,
  journals,
  jobs,
  adultStatus,
  conversations,
  user
}: {
  panel: Panel;
  relationship: Relationship;
  memories: MemoryItem[];
  journals: Journal[];
  jobs: ScheduledJob[];
  adultStatus: AdultStatus | null;
  conversations: Conversation[];
  user: User;
}) {
  if (panel === "overview") {
    return `${relationship.mood} mood · ${jobs.length} queued jobs`;
  }
  if (panel === "relationship") {
    return `${relationship.conflict_state} · warmth ${formatMetric(relationship.warmth)}`;
  }
  if (panel === "character") {
    return "Persona, speech, and age-gated profile state";
  }
  if (panel === "memory") {
    return `${memories.length} memories · ${memories.filter((memory) => memory.pinned).length} pinned`;
  }
  if (panel === "journal") {
    return `${journals.length} entries · ${journals.reduce(
      (total, journal) => total + journal.unresolved_threads_json.length,
      0
    )} open threads`;
  }
  if (panel === "adult") {
    return adultStatus?.allowed ? "Adult gates available" : "SFW boundaries enforced";
  }
  if (panel === "settings") {
    return user.display_name ?? user.email;
  }
  if (panel === "debug") {
    return "Private runtime and prompt preview";
  }
  return `${conversations.length} conversations available for export or cleanup`;
}
