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
  AdultReadinessState,
  CharacterDraft,
  Conversation,
  ConversationDebugPayload,
  DebugPayload,
  Journal,
  MemoryItem,
  Panel,
  Relationship,
  RelationshipEvent,
  RuntimeStatus,
  ScheduledJob,
  User
} from "./types";
import type { MemoryView } from "./use-knowledge-controller";
import {
  journalResonance,
  relationshipPhase,
  relationshipTemperature
} from "./cognition";

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
  busy,
  sending,
  user,
  draft,
  setDraft,
  relationship,
  timeline,
  memories,
  forgottenMemories,
  memoryView,
  memoryActionId,
  forgottenMemoriesLoading,
  journals,
  jobs,
  debug,
  conversationDebug,
  conversations,
  messageCount,
  activeConversationTitle,
  adultStatus,
  adultReadinessState,
  runtimeStatus,
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
  editingJournalId,
  journalEditTitle,
  journalEditSummary,
  journalActionId,
  accountActionId,
  characterActionId,
  setMemoryContent,
  setMemoryType,
  setMemoryImportance,
  setMemoryPinned,
  setEditingMemoryId,
  setMemoryEditContent,
  setJournalTitle,
  setJournalSummary,
  setJournalEditTitle,
  setJournalEditSummary,
  onSaveCharacter,
  onToggleAgeGate,
  onSaveName,
  onAddMemory,
  onSaveMemoryEdit,
  onToggleMemoryPinned,
  onDeleteMemory,
  onForgetMemory,
  onRestoreMemory,
  onResolveMemoryConflict,
  onForgetMemories,
  onChangeMemoryView,
  onAddJournal,
  onStartJournalEdit,
  onCancelJournalEdit,
  onSaveJournalEdit,
  onDeleteJournal,
  onExport,
  onDeleteAccount,
  onClearMessages,
  onClearMemories,
  onDeleteConversation,
  deletingConversationId,
  onRefreshRuntime,
  onLogout
}: {
  panel: Panel;
  setPanel: (panel: Panel) => void;
  busy: boolean;
  sending: boolean;
  user: User;
  draft: CharacterDraft;
  setDraft: (value: CharacterDraft) => void;
  relationship: Relationship;
  timeline: RelationshipEvent[];
  memories: MemoryItem[];
  forgottenMemories: MemoryItem[];
  memoryView: MemoryView;
  memoryActionId: string | null;
  forgottenMemoriesLoading: boolean;
  journals: Journal[];
  jobs: ScheduledJob[];
  debug: DebugPayload | null;
  conversationDebug: ConversationDebugPayload | null;
  conversations: Conversation[];
  messageCount: number;
  activeConversationTitle: string;
  adultStatus: AdultStatus | null;
  adultReadinessState: AdultReadinessState;
  runtimeStatus: RuntimeStatus;
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
  editingJournalId: string | null;
  journalEditTitle: string;
  journalEditSummary: string;
  journalActionId: string | null;
  accountActionId: string | null;
  characterActionId: string | null;
  setMemoryContent: (value: string) => void;
  setMemoryType: (value: string) => void;
  setMemoryImportance: (value: string) => void;
  setMemoryPinned: (value: boolean) => void;
  setEditingMemoryId: (value: string | null) => void;
  setMemoryEditContent: (value: string) => void;
  setJournalTitle: (value: string) => void;
  setJournalSummary: (value: string) => void;
  setJournalEditTitle: (value: string) => void;
  setJournalEditSummary: (value: string) => void;
  onSaveCharacter: () => void;
  onToggleAgeGate: () => void;
  onSaveName: () => void;
  onAddMemory: (event: FormEvent<HTMLFormElement>) => void;
  onSaveMemoryEdit: (memory: MemoryItem) => void;
  onToggleMemoryPinned: (memory: MemoryItem) => void;
  onDeleteMemory: (memory: MemoryItem) => void;
  onForgetMemory: (memory: MemoryItem) => void;
  onRestoreMemory: (memory: MemoryItem) => void;
  onResolveMemoryConflict: (memory: MemoryItem) => void;
  onForgetMemories: () => void;
  onChangeMemoryView: (view: MemoryView) => void;
  onAddJournal: (event: FormEvent<HTMLFormElement>) => void;
  onStartJournalEdit: (journal: Journal) => void;
  onCancelJournalEdit: () => void;
  onSaveJournalEdit: (journal: Journal) => void;
  onDeleteJournal: (journal: Journal) => void;
  onExport: () => Promise<boolean>;
  onDeleteAccount: (password: string, confirmation: string) => Promise<boolean>;
  onClearMessages: () => Promise<boolean>;
  onClearMemories: () => Promise<boolean>;
  onDeleteConversation: () => Promise<boolean>;
  deletingConversationId: string | null;
  onRefreshRuntime: () => void;
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
                    <span className="w-full truncate">{item.label}</span>
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
      <fieldset
        aria-busy={busy}
        className="min-w-0 space-y-4 p-4 disabled:opacity-70"
        disabled={busy && !(panel === "data" && sending)}
      >
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
          <CharacterPanel
            draft={draft}
            setDraft={setDraft}
            onSave={onSaveCharacter}
            saving={characterActionId === "save"}
          />
        ) : null}
        {panel === "memory" ? (
          <MemoryPanel
            memories={memories}
            forgottenMemories={forgottenMemories}
            memoryView={memoryView}
            memoryActionId={memoryActionId}
            forgottenMemoriesLoading={forgottenMemoriesLoading}
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
            onForgetMemory={onForgetMemory}
            onRestoreMemory={onRestoreMemory}
            onResolveConflict={onResolveMemoryConflict}
            onForget={onForgetMemories}
            onChangeView={onChangeMemoryView}
          />
        ) : null}
        {panel === "journal" ? (
          <JournalPanel
            journals={journals}
            title={journalTitle}
            summary={journalSummary}
            editingJournalId={editingJournalId}
            editTitle={journalEditTitle}
            editSummary={journalEditSummary}
            journalActionId={journalActionId}
            setTitle={setJournalTitle}
            setSummary={setJournalSummary}
            setEditTitle={setJournalEditTitle}
            setEditSummary={setJournalEditSummary}
            onAdd={onAddJournal}
            onStartEdit={onStartJournalEdit}
            onCancelEdit={onCancelJournalEdit}
            onSaveEdit={onSaveJournalEdit}
            onDelete={onDeleteJournal}
          />
        ) : null}
        {panel === "relationship" ? (
          <RelationshipPanel relationship={relationship} timeline={timeline} />
        ) : null}
        {panel === "adult" ? (
          <AdultPanel
            status={adultStatus}
            readinessState={adultReadinessState}
            user={user}
            draft={draft}
            setDraft={setDraft}
            onToggleAgeGate={onToggleAgeGate}
            onSave={onSaveCharacter}
            saving={characterActionId === "save"}
          />
        ) : null}
        {panel === "settings" ? (
          <SettingsPanel
            user={user}
            displayName={displayName}
            setDisplayName={setDisplayName}
            onSaveName={onSaveName}
            onLogout={onLogout}
            accountActionId={accountActionId}
          />
        ) : null}
        {panel === "debug" ? (
          <DebugPanel
            debug={debug}
            conversationDebug={conversationDebug}
            jobs={jobs}
            conversations={conversations}
            runtimeStatus={runtimeStatus}
            onRefreshRuntime={onRefreshRuntime}
          />
        ) : null}
        {panel === "data" ? (
          <DataPanel
            streaming={sending}
            messageCount={messageCount}
            memoryCount={memories.length}
            conversationCount={conversations.length}
            activeConversationTitle={activeConversationTitle}
            onExport={onExport}
            onDeleteAccount={onDeleteAccount}
            onClearMessages={onClearMessages}
            onClearMemories={onClearMemories}
            onDeleteConversation={onDeleteConversation}
            accountActionId={accountActionId}
            deletingConversationId={deletingConversationId}
          />
        ) : null}
      </fieldset>
    </aside>
  );
}

function panelButtonClass(active: boolean) {
  return `flex min-h-12 min-w-0 flex-col items-start justify-center gap-0.5 rounded-md border px-2 py-1.5 text-left ${
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
    return relationshipTemperature(relationship);
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
    return debug?.prompt_context?.llm_provider ? "ready" : jobs.length > 0 ? "queued" : "quiet";
  }
  return conversations.length > 1 ? "threads" : "thread";
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
    return `${relationshipPhase(relationship)} · ${
      jobs.length > 0 ? "companion notes queued" : "quiet background"
    }`;
  }
  if (panel === "relationship") {
    return `${relationshipTemperature(relationship)} · ${relationshipPhase(relationship)}`;
  }
  if (panel === "character") {
    return "Persona, speech, and age-gated profile state";
  }
  if (panel === "memory") {
    return `${memories.length} memories · ${memories.filter((memory) => memory.pinned).length} pinned`;
  }
  if (panel === "journal") {
    const leadingJournal = journals[0];
    return leadingJournal
      ? `${journals.length} entries · ${journalResonance(leadingJournal)}`
      : "No episodes logged yet";
  }
  if (panel === "adult") {
    return adultStatus?.allowed ? "Adult gates available" : "SFW boundaries enforced";
  }
  if (panel === "settings") {
    return user.display_name ?? user.email;
  }
  if (panel === "debug") {
    return "Private runtime and context manifest";
  }
  return `${conversations.length} conversations available for export or cleanup`;
}
