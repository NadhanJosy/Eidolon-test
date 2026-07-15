"use client";

import { useCallback, useState } from "react";

import { AuthScreen } from "./eidolon/auth-screen";
import { authoredCharacterDraft } from "./eidolon/character-builder-model";
import { ChatSurface } from "./eidolon/chat-surface";
import { relationshipPhase } from "./eidolon/cognition";
import {
  characterMemoryCapturePolicy,
  characterScenarioPreset,
  conversationCustomScenario,
  conversationScenarioMode,
  memorySourceMessageIds
} from "./eidolon/controller-utils";
import { ConversationLibrary } from "./eidolon/conversation-library";
import { CompanionPortrait, Feedback } from "./eidolon/experience-primitives";
import { Icon, type IconName } from "./eidolon/icons";
import { MemoryArchive } from "./eidolon/memory-archive";
import { MomentsJournal } from "./eidolon/moments-journal";
import { OnboardingExperience } from "./eidolon/onboarding-experience";
import { RelationshipExperience } from "./eidolon/relationship-experience";
import { SettingsExperience } from "./eidolon/settings-experience";
import type { Character, CharacterDraft, Conversation, Message } from "./eidolon/types";
import { useEidolonController } from "./eidolon/use-eidolon-controller";

type AppView = "chat" | "memories" | "relationship" | "moments" | "settings";

const destinations: Array<{ id: AppView; icon: IconName; label: string }> = [
  { id: "chat", icon: "message", label: "Chat" },
  { id: "memories", icon: "bookmark", label: "Memories" },
  { id: "relationship", icon: "heart", label: "Relationship" },
  { id: "moments", icon: "book", label: "Moments" },
  { id: "settings", icon: "settings", label: "Settings" }
];

export function EidolonApp() {
  const { state, actions } = useEidolonController();
  const [view, setView] = useState<AppView>("chat");
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [completedOnboardingKey, setCompletedOnboardingKey] = useState<string | null>(null);
  const [creatingCompanion, setCreatingCompanion] = useState(false);
  const onboardingStorageKey =
    state.user && state.activeCharacter && state.activeConversation
      ? `eidolon:onboarding:${state.user.id}:${state.activeCharacter.id}`
      : null;
  const onboardingKey =
    onboardingStorageKey &&
    state.characters.length === 1 &&
    state.sortedMessages.length === 0 &&
    state.activeCharacter?.name === "Eidolon" &&
    completedOnboardingKey !== onboardingStorageKey &&
    (typeof window === "undefined" ||
      window.localStorage.getItem(onboardingStorageKey) !== "complete")
      ? onboardingStorageKey
      : null;

  const closeLibrary = useCallback(() => setLibraryOpen(false), []);

  if (!state.sessionReady) {
    return <SessionOpening />;
  }

  if (!state.user || !state.token || state.authStage === "opening") {
    return (
      <AuthScreen
        authMode={state.authMode}
        authStage={state.authStage}
        busy={state.busy}
        displayName={state.displayName}
        email={state.email}
        error={state.error}
        notice={state.notice}
        password={state.password}
        setDisplayName={actions.setDisplayName}
        setEmail={actions.setEmail}
        setPassword={actions.setPassword}
        onModeChange={actions.changeAuthMode}
        onSubmit={actions.handleAuth}
      />
    );
  }

  const currentUser = state.user;
  const characterName = state.activeCharacter?.name ?? "Eidolon";
  const rememberedMessageIds = state.memories.flatMap(memorySourceMessageIds);
  const interactionBusy =
    state.busy ||
    state.sending ||
    state.scenarioSaving ||
    state.messageMutating ||
    state.characterMutating ||
    state.conversationCreating ||
    state.conversationProvisioning ||
    state.conversationDeleting ||
    state.memoryMutating ||
    state.journalMutating ||
    state.accountMutating ||
    state.conversationMutating;

  function navigate(nextView: AppView) {
    setView(nextView);
    setLibraryOpen(false);
  }

  async function openCharacter(character: Character) {
    if (await actions.selectCharacter(character)) {
      setView("chat");
      setLibraryOpen(false);
    }
  }

  async function openConversation(conversation: Conversation) {
    if (await actions.selectConversation(conversation)) {
      setView("chat");
      setLibraryOpen(false);
    }
  }

  async function createConversation() {
    if (await actions.createConversationForCurrentCharacter("normal")) {
      setView("chat");
      setLibraryOpen(false);
    }
  }

  function openSearchResult(message: Message) {
    if (message.conversation_id !== state.activeConversation?.id) {
      return;
    }
    setView("chat");
    setLibraryOpen(false);
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        const target = document.getElementById(`message-${message.id}`);
        if (!target) return;
        const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        target.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "center" });
        target.focus({ preventScroll: true });
      });
    });
  }

  async function completeOnboarding(draft: CharacterDraft) {
    const ok = await actions.saveCharacter(draft);
    if (!ok) {
      return { ok: false, error: "Those details could not be saved yet. Everything you wrote is still here." };
    }
    if (onboardingKey) {
      window.localStorage.setItem(onboardingKey, "complete");
    }
    setCompletedOnboardingKey(onboardingKey);
    setView("chat");
    return { ok: true };
  }

  async function completeNewCompanion(draft: CharacterDraft) {
    const result = await actions.createCharacter(draft);
    if (!result.ok) {
      return { ok: false, error: result.error };
    }
    setCreatingCompanion(false);
    setView("chat");
    setLibraryOpen(false);
    return { ok: true };
  }

  return (
    <main className="eidolon-room relative h-[100dvh] overflow-hidden text-[#f3eee5]">
      <div className="relative z-10 flex h-full min-h-0">
        <DesktopNavigation active={view} onNavigate={navigate} />

        <div className="flex min-w-0 flex-1 flex-col">
          <CompanionHeader
            characterName={characterName}
            theme={state.characterDraft.visual_theme}
            relationshipLabel={relationshipLabel(state.relationship ? relationshipPhase(state.relationship) : "new connection")}
            unreadCount={state.conversations.reduce((total, conversation) => total + conversation.unread_count, 0)}
            onOpenLibrary={() => setLibraryOpen(true)}
          />

          <div className="min-h-0 flex-1 overflow-hidden pb-[4.45rem] lg:pb-0">
            {view === "chat" ? (
              <ChatSurface
                busy={interactionBusy}
                character={state.activeCharacter}
                characterScenario={characterScenarioPreset(state.activeCharacter)}
                contentMode={state.contentMode}
                draft={state.messageDraft}
                editableTitle={state.conversationTitle}
                editingMessageId={state.editingMessageId}
                error={state.error}
                failedTurn={state.failedTurn}
                memoryCapturePolicy={characterMemoryCapturePolicy(state.activeCharacter)}
                messages={state.sortedMessages}
                notice={state.notice}
                pendingOutgoingContent={state.pendingOutgoingContent}
                privateTurn={state.privateTurn}
                providerName={state.runtimeStatus.llmProvider}
                privacyMode={state.activeConversationPrivacyMode}
                rememberedMessageIds={rememberedMessageIds}
                rememberingMessageId={state.rememberingMessageId}
                scenarioDraft={state.conversationScenarioDraft}
                scenarioMode={conversationScenarioMode(state.activeConversation)}
                scenarioText={conversationCustomScenario(state.activeConversation)}
                sending={state.sending}
                setDraft={actions.setMessageDraft}
                setEditableTitle={actions.setConversationTitle}
                setPrivateTurn={actions.setPrivateTurn}
                setScenarioDraft={actions.setConversationScenarioDraft}
                streamPhase={state.streamPhase}
                streamingContent={state.streamingContent}
                onCancelEdit={actions.cancelEditMessage}
                onDelete={actions.deleteMessage}
                onEdit={actions.startEditMessage}
                onOpenMemories={() => navigate("memories")}
                onQueueProactive={actions.queueProactive}
                onRemember={actions.rememberMessage}
                onReroll={actions.rerollMessage}
                onResetScenario={actions.resetActiveConversationScenario}
                onSaveScenario={actions.saveActiveConversationScenario}
                onSaveTitle={actions.saveConversationTitle}
                onSetPrivacyMode={actions.setActiveConversationPrivacyMode}
                onSubmit={actions.sendMessage}
                onRetryFailed={actions.retryFailedTurn}
                onStop={actions.stopResponse}
              />
            ) : null}

            {view !== "chat" ? (
              <div className="h-full overflow-y-auto overscroll-contain">
                {view === "memories" ? (
                  <MemoryArchive
                    characterName={characterName}
                    editingMemoryId={state.editingMemoryId}
                    forgottenMemories={state.forgottenMemories}
                    forgottenMemoriesLoading={state.forgottenMemoriesLoading}
                    memories={state.memories}
                    memoryActionId={state.memoryActionId}
                    memoryContent={state.memoryContent}
                    memoryEditContent={state.memoryEditContent}
                    memoryImportance={state.memoryImportance}
                    memoryPinned={state.memoryPinned}
                    memoryType={state.memoryType}
                    memoryView={state.memoryView}
                    setEditingMemoryId={actions.setEditingMemoryId}
                    setMemoryContent={actions.setMemoryContent}
                    setMemoryEditContent={actions.setMemoryEditContent}
                    setMemoryImportance={actions.setMemoryImportance}
                    setMemoryPinned={actions.setMemoryPinned}
                    setMemoryType={actions.setMemoryType}
                    onAdd={actions.addMemory}
                    onChangeView={actions.changeMemoryView}
                    onDelete={actions.deleteMemory}
                    onForget={actions.forgetMemories}
                    onForgetMemory={actions.forgetMemory}
                    onResolveConflict={actions.resolveMemoryConflict}
                    onRestoreMemory={actions.restoreMemory}
                    onSaveEdit={actions.saveMemoryEdit}
                    onTogglePinned={actions.toggleMemoryPinned}
                  />
                ) : null}
                {view === "relationship" ? (
                  <RelationshipExperience characterName={characterName} draft={state.characterDraft} journals={state.journals} relationship={state.relationship} timeline={state.timeline} />
                ) : null}
                {view === "moments" ? (
                  <MomentsJournal
                    characterName={characterName}
                    editSummary={state.journalEditSummary}
                    editTitle={state.journalEditTitle}
                    editingJournalId={state.editingJournalId}
                    journalActionId={state.journalActionId}
                    journals={state.journals}
                    setEditSummary={actions.setJournalEditSummary}
                    setEditTitle={actions.setJournalEditTitle}
                    setSummary={actions.setJournalSummary}
                    setTitle={actions.setJournalTitle}
                    summary={state.journalSummary}
                    title={state.journalTitle}
                    onAdd={actions.addJournal}
                    onCancelEdit={actions.cancelJournalEdit}
                    onDelete={actions.deleteJournal}
                    onSaveEdit={actions.saveJournalEdit}
                    onStartEdit={actions.startJournalEdit}
                  />
                ) : null}
                {view === "settings" ? (
                  <SettingsExperience
                    accountActionId={state.accountActionId}
                    adultModeAvailable={state.adultModeAvailable}
                    adultReadinessState={state.adultReadinessState}
                    adultStatus={state.adultStatus}
                    characterName={characterName}
                    characterSaving={state.characterMutating}
                    contentMode={state.contentMode}
                    conversationCount={state.conversations.length}
                    deletingConversationId={state.deletingConversationId}
                    displayName={state.displayName}
                    draft={state.characterDraft}
                    memoryCount={state.memories.length}
                    messageCount={state.sortedMessages.length}
                    privacyMode={state.activeConversationPrivacyMode}
                    setDisplayName={actions.setDisplayName}
                    setDraft={actions.setCharacterDraft}
                    streaming={state.sending}
                    user={currentUser}
                    onChangeContentMode={(mode) => { actions.changeContentMode(mode); }}
                    onClearMemories={actions.clearMemories}
                    onClearMessages={actions.clearConversationMessages}
                    onDeleteAccount={actions.deleteAccount}
                    onDeleteConversation={actions.deleteActiveConversation}
                    onExport={actions.exportAccount}
                    onLogout={() => { setView("chat"); actions.clearAuth(); }}
                    onSaveCharacter={() => actions.saveCharacter()}
                    onSaveName={() => { void actions.updateUser({ display_name: state.displayName }); }}
                    onSetPrivacyMode={(mode) => { void actions.setActiveConversationPrivacyMode(mode); }}
                    onToggleAgeGate={() => { void actions.updateUser({ age_gate_confirmed: !currentUser.age_gate_confirmed }); }}
                  />
                ) : null}
                <div className="fixed bottom-24 left-1/2 z-50 w-[min(92vw,34rem)] -translate-x-1/2 lg:bottom-6">
                  <Feedback error={state.error} notice={state.notice} />
                </div>
              </div>
            ) : null}
          </div>
        </div>

        <MobileNavigation active={view} onNavigate={navigate} />
      </div>

      <ConversationLibrary
        activeCharacter={state.activeCharacter}
        activeConversation={state.activeConversation}
        busy={interactionBusy}
        characters={state.characters}
        conversations={state.conversations}
        creating={state.conversationCreating}
        open={libraryOpen}
        searchError={state.searchError}
        searchQuery={state.searchQuery}
        searchResults={state.searchResults}
        searchStatus={state.searchStatus}
        setSearchQuery={actions.setSearchQuery}
        onClose={closeLibrary}
        onCreateCompanion={() => setCreatingCompanion(true)}
        onCreateConversation={() => void createConversation()}
        onSearch={actions.searchMessages}
        onSelectCharacter={(character) => void openCharacter(character)}
        onSelectConversation={(conversation) => void openConversation(conversation)}
        onSelectSearchResult={openSearchResult}
      />

      {onboardingKey && state.activeCharacter ? (
        <OnboardingExperience initialDraft={state.characterDraft} userName={currentUser.display_name ?? "you"} onComplete={completeOnboarding} />
      ) : null}

      {creatingCompanion ? (
        <OnboardingExperience creatingAnother initialDraft={authoredCharacterDraft()} userName={currentUser.display_name ?? "you"} onClose={() => setCreatingCompanion(false)} onComplete={completeNewCompanion} />
      ) : null}
    </main>
  );
}

function CompanionHeader({ characterName, theme, relationshipLabel, unreadCount, onOpenLibrary }: { characterName: string; theme: string; relationshipLabel: string; unreadCount: number; onOpenLibrary: () => void }) {
  return (
    <header className="safe-area-header relative z-40 flex min-h-[4.6rem] items-center justify-between gap-4 border-b border-white/[0.07] bg-[#0b0a09]/82 px-4 backdrop-blur-2xl sm:px-6 lg:px-8">
      <button className="group flex min-w-0 items-center gap-3 rounded-full pr-3 text-left transition hover:bg-white/[0.035]" onClick={onOpenLibrary} type="button">
        <CompanionPortrait name={characterName} size="small" theme={theme} />
        <span className="min-w-0"><span className="flex items-center gap-2"><span className="truncate font-eidolon-display text-xl text-[#eee5dc]">{characterName}</span><Icon className="h-3.5 w-3.5 text-[#756c64] transition group-hover:text-[#a88a79]" name="chevron-down" /></span><span className="block truncate text-[0.65rem] text-[#776f67]">{relationshipLabel}</span></span>
      </button>
      <button className="relative flex min-h-10 items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.025] px-3 text-xs text-[#91887f] transition hover:border-white/[0.16] hover:text-[#c7bcb1]" onClick={onOpenLibrary} type="button"><Icon className="h-4 w-4" name="archive" /><span className="hidden sm:inline">Past conversations</span>{unreadCount > 0 ? <span className="grid h-4 min-w-4 place-items-center rounded-full bg-[#a96f54] px-1 text-[0.58rem] font-semibold text-[#190f0b]">{unreadCount > 9 ? "9+" : unreadCount}</span> : null}</button>
    </header>
  );
}

function DesktopNavigation({ active, onNavigate }: { active: AppView; onNavigate: (view: AppView) => void }) {
  return <aside className="hidden w-[5.25rem] shrink-0 flex-col items-center border-r border-white/[0.07] bg-[#0b0a09]/75 py-5 backdrop-blur-xl lg:flex"><div className="grid h-10 w-10 place-items-center rounded-full border border-[#b98265]/25 bg-[#b98265]/[0.08] font-eidolon-display text-lg text-[#d1a087]">E</div><nav aria-label="Primary" className="mt-auto mb-auto space-y-3">{destinations.map((item) => <NavigationButton active={active === item.id} icon={item.icon} key={item.id} label={item.label} onClick={() => onNavigate(item.id)} />)}</nav><span className="text-[0.58rem] uppercase tracking-[0.2em] text-[#57524d] [writing-mode:vertical-rl]">Private companion</span></aside>;
}

function NavigationButton({ active, icon, label, onClick }: { active: boolean; icon: IconName; label: string; onClick: () => void }) {
  return <button aria-current={active ? "page" : undefined} aria-label={label} className={`group relative grid h-11 w-11 place-items-center rounded-full transition ${active ? "bg-[#b98265]/[0.12] text-[#d2a088]" : "text-[#6f6861] hover:bg-white/[0.04] hover:text-[#b7ada3]"}`} onClick={onClick} title={label} type="button"><Icon className="h-[1.15rem] w-[1.15rem]" name={icon} />{active ? <span className="absolute -left-[1.3rem] h-5 w-0.5 rounded-full bg-[#b98265]" /> : null}<span className="pointer-events-none absolute left-14 z-50 hidden whitespace-nowrap rounded-lg border border-white/[0.08] bg-[#171512] px-2.5 py-1.5 text-[0.68rem] text-[#b7ada3] shadow-xl group-hover:block">{label}</span></button>;
}

function MobileNavigation({ active, onNavigate }: { active: AppView; onNavigate: (view: AppView) => void }) {
  return <nav aria-label="Primary" className="safe-area-nav fixed inset-x-0 bottom-0 z-50 grid grid-cols-5 border-t border-white/[0.08] bg-[#0d0c0b]/94 px-1 pt-1.5 backdrop-blur-2xl lg:hidden">{destinations.map((item) => <button aria-current={active === item.id ? "page" : undefined} className={`flex min-h-14 min-w-0 flex-col items-center justify-center gap-1 rounded-xl text-[0.58rem] transition ${active === item.id ? "text-[#d2a088]" : "text-[#6e6760]"}`} key={item.id} onClick={() => onNavigate(item.id)} type="button"><Icon className="h-[1.05rem] w-[1.05rem]" name={item.icon} /><span className="truncate">{item.label}</span></button>)}</nav>;
}

function SessionOpening() {
  return <main className="eidolon-room relative flex min-h-[100svh] items-center justify-center overflow-hidden px-6 text-[#f3eee5]"><div aria-live="polite" className="relative z-10 text-center" role="status"><div className="companion-aura mx-auto grid h-20 w-20 place-items-center rounded-full border border-[#b98265]/25 bg-[#b98265]/[0.08] font-eidolon-display text-3xl text-[#d5a48b]">E</div><p className="mt-8 font-eidolon-display text-4xl">Eidolon</p><p className="mt-3 text-xs tracking-wide text-[#776f67]">Opening your private space</p><span className="mx-auto mt-5 block h-px w-20 overflow-hidden bg-white/[0.08]"><span className="block h-full w-1/2 animate-pulse bg-[#b98265]" /></span></div></main>;
}

function relationshipLabel(phase: string): string {
  const labels: Record<string, string> = { "new connection": "You’ve only just met", "warming up": "You’re finding a rhythm", "trusted warmth": "Trust is taking root", "close bond": "A deeply familiar presence", "repair arc": "A little tenderness is needed" };
  return labels[phase] ?? "Here with you";
}
