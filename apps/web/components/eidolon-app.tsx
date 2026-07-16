"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AuthScreen } from "./eidolon/auth-screen";
import { authoredCharacterDraft } from "./eidolon/character-builder-model";
import { ChatSurface } from "./eidolon/chat-surface";
import { relationshipPhase } from "./eidolon/cognition";
import {
  ConfirmationDialog,
  type ConfirmationRequest
} from "./eidolon/confirmation-dialog";
import {
  characterMemoryCapturePolicy,
  characterScenarioPreset,
  conversationCustomScenario,
  conversationScenarioMode,
  memorySourceMessageIds
} from "./eidolon/controller-utils";
import { ConversationLibrary } from "./eidolon/conversation-library";
import {
  CompanionPortrait,
  EidolonWordmark,
  Feedback
} from "./eidolon/experience-primitives";
import { Icon, type IconName } from "./eidolon/icons";
import { MemoryArchive } from "./eidolon/memory-archive";
import { MomentsJournal } from "./eidolon/moments-journal";
import { OnboardingExperience } from "./eidolon/onboarding-experience";
import { RelationshipExperience } from "./eidolon/relationship-experience";
import { SettingsExperience } from "./eidolon/settings-experience";
import type {
  Character,
  CharacterDraft,
  ContinuityThread,
  Conversation,
  ConversationPrivacyMode,
  Journal,
  MemoryItem,
  Message
} from "./eidolon/types";
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
  const [librarySelectionBusy, setLibrarySelectionBusy] = useState(false);
  const [completedOnboardingKey, setCompletedOnboardingKey] = useState<string | null>(null);
  const [creatingCompanion, setCreatingCompanion] = useState(false);
  const [confirmation, setConfirmation] = useState<ConfirmationRequest | null>(null);
  const [unreadEntry, setUnreadEntry] = useState<{
    conversationId: string;
    after: string;
  } | null>(null);
  const contentScrollRef = useRef<HTMLDivElement | null>(null);
  const viewScrollPositions = useRef<Partial<Record<AppView, number>>>({});
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

  useEffect(() => {
    if (view === "chat") return;
    const frame = window.requestAnimationFrame(() => {
      const scroller = contentScrollRef.current;
      if (scroller) scroller.scrollTop = viewScrollPositions.current[view] ?? 0;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [view]);

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
  const experienceError = state.error ?? state.sideStateError;
  const activeUnreadAfter =
    unreadEntry && unreadEntry.conversationId === state.activeConversation?.id
      ? unreadEntry.after
      : null;
  const interactionBusy =
    state.busy ||
    state.sending ||
    state.scenarioSaving ||
    state.messageMutating ||
    state.characterMutating ||
    state.conversationCreating ||
    state.conversationProvisioning ||
    state.conversationDeleting ||
    state.conversationSwitchingId !== null ||
    state.memoryMutating ||
    state.journalMutating ||
    state.threadMutating ||
    state.accountMutating ||
    state.conversationMutating;

  function navigate(nextView: AppView) {
    if (view !== "chat" && contentScrollRef.current) {
      viewScrollPositions.current[view] = contentScrollRef.current.scrollTop;
    }
    setView(nextView);
    setLibraryOpen(false);
  }

  async function openCharacter(character: Character) {
    if (librarySelectionBusy) return;
    const knownConversation = state.conversations.find(
      (conversation) => conversation.character_id === character.id
    );
    const unread =
      knownConversation && knownConversation.unread_count > 0
        ? {
            conversationId: knownConversation.id,
            after: knownConversation.last_read_at
          }
        : null;
    const previousUnreadEntry = unreadEntry;
    setUnreadEntry(unread);
    setLibrarySelectionBusy(true);
    try {
      if (await actions.selectCharacter(character)) {
        setView("chat");
        setLibraryOpen(false);
      } else {
        setUnreadEntry(previousUnreadEntry);
      }
    } finally {
      setLibrarySelectionBusy(false);
    }
  }

  async function openConversation(conversation: Conversation) {
    if (librarySelectionBusy) return;
    const unread =
      conversation.unread_count > 0
        ? { conversationId: conversation.id, after: conversation.last_read_at }
        : null;
    const previousUnreadEntry = unreadEntry;
    setUnreadEntry(unread);
    setLibrarySelectionBusy(true);
    try {
      if (await actions.selectConversation(conversation)) {
        setView("chat");
        setLibraryOpen(false);
      } else {
        setUnreadEntry(previousUnreadEntry);
      }
    } finally {
      setLibrarySelectionBusy(false);
    }
  }

  async function createConversation() {
    if (await actions.createConversationForCurrentCharacter("normal")) {
      setUnreadEntry(null);
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
    setUnreadEntry(null);
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

  const companionTheme =
    typeof state.activeCharacter?.boundaries_json.visual_theme === "string"
      ? state.activeCharacter.boundaries_json.visual_theme
      : "ember";

  function confirmMessageDeletion(message: Message) {
    setConfirmation({
      title: message.role === "user" ? "Remove this turn?" : "Remove this reply?",
      detail:
        message.role === "user"
          ? "Your message, the companion reply that followed it, and continuity grounded in that turn will be removed."
          : "This reply will leave the conversation. Any continuity grounded in it will be reconciled by Eidolon.",
      actionLabel: message.role === "user" ? "Remove turn" : "Remove reply",
      onConfirm: () => actions.deleteMessage(message)
    });
  }

  function confirmMemoryDeletion(memory: MemoryItem) {
    setConfirmation({
      title: "Release this memory?",
      detail: "It will be removed permanently from this companion’s continuity and cannot be restored.",
      actionLabel: "Release memory",
      onConfirm: () => actions.deleteMemory(memory)
    });
  }

  function confirmJournalDeletion(journal: Journal) {
    setConfirmation({
      title: "Remove this reflection?",
      detail: "This reflection will leave your shared journal permanently.",
      actionLabel: "Remove reflection",
      onConfirm: () => actions.deleteJournal(journal)
    });
  }

  function confirmThreadDeletion(thread: ContinuityThread) {
    setConfirmation({
      title: "Release this thread?",
      detail: "It will no longer appear in your shared continuity and cannot be reopened.",
      actionLabel: "Release thread",
      onConfirm: () => actions.deleteContinuityThread(thread)
    });
  }

  function confirmAdultContinuityDeletion() {
    setConfirmation({
      title: "Remove intimate continuity?",
      detail: "Every adult-only memory and private moment for this companion will be erased. Your conversation messages will remain.",
      actionLabel: "Remove continuity",
      onConfirm: actions.clearAdultContinuity
    });
  }

  return (
    <main
      className="eidolon-room relative h-[100dvh] overflow-hidden text-[#f3eee5]"
      data-companion-theme={companionTheme}
    >
      <div className="relative z-10 flex h-full min-h-0">
        <DesktopNavigation
          active={view}
          characterName={characterName}
          theme={state.characterDraft.visual_theme}
          onNavigate={navigate}
          onOpenLibrary={() => setLibraryOpen(true)}
        />

        <div className="flex min-w-0 flex-1 flex-col">
          <CompanionHeader
            characterName={characterName}
            conversationTitle={state.activeConversation?.title}
            privacyMode={state.activeConversationPrivacyMode}
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
                conversationId={state.activeConversation?.id ?? null}
                continuityThreads={state.continuityThreads}
                draft={state.messageDraft}
                editableTitle={state.conversationTitle}
                editingMessageId={state.editingMessageId}
                error={experienceError}
                failedTurn={state.failedTurn}
                memoryCapturePolicy={characterMemoryCapturePolicy(state.activeCharacter)}
                messages={state.sortedMessages}
                loading={state.conversationSwitchingId === state.activeConversation?.id}
                unreadAfter={activeUnreadAfter}
                notice={state.notice}
                pendingOutgoingContent={state.pendingOutgoingContent}
                privateTurn={state.privateTurn}
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
                threadActionId={state.threadActionId}
                threadDraft={state.threadDraft}
                setThreadDraft={actions.setThreadDraft}
                onAddContinuityThread={actions.addContinuityThread}
                onCancelEdit={actions.cancelEditMessage}
                onDelete={confirmMessageDeletion}
                onEdit={actions.startEditMessage}
                onOpenMemories={() => navigate("memories")}
                onQueueProactive={actions.queueProactive}
                onDeleteContinuityThread={confirmThreadDeletion}
                onReopenContinuityThread={actions.reopenContinuityThread}
                onRemember={actions.rememberMessage}
                onResolveContinuityThread={actions.resolveContinuityThread}
                onReroll={actions.rerollMessage}
                onResetScenario={actions.resetActiveConversationScenario}
                onSaveScenario={actions.saveActiveConversationScenario}
                onSaveTitle={actions.saveConversationTitle}
                onSetPrivacyMode={actions.setActiveConversationPrivacyMode}
                onSubmit={actions.sendMessage}
                onRetryFailed={actions.retryFailedTurn}
                onStop={actions.stopResponse}
                onUnreadSeen={() => setUnreadEntry(null)}
              />
            ) : null}

            {view !== "chat" ? (
              <div className="h-full overflow-y-auto overscroll-contain" ref={contentScrollRef}>
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
                    onDelete={confirmMemoryDeletion}
                    onForget={actions.forgetMemories}
                    onForgetMemory={actions.forgetMemory}
                    onResolveConflict={actions.resolveMemoryConflict}
                    onRestoreMemory={actions.restoreMemory}
                    onSaveEdit={actions.saveMemoryEdit}
                    onTogglePinned={actions.toggleMemoryPinned}
                  />
                ) : null}
                {view === "relationship" ? (
                  <RelationshipExperience
                    actionId={state.threadActionId}
                    characterName={characterName}
                    draft={state.characterDraft}
                    journals={state.journals}
                    relationship={state.relationship}
                    threads={state.continuityThreads}
                    timeline={state.timeline}
                    onDelete={confirmThreadDeletion}
                    onReopen={actions.reopenContinuityThread}
                    onResolve={actions.resolveContinuityThread}
                    onReturn={(thread) => {
                      actions.setMessageDraft(`Can we come back to this: ${thread.content}`);
                      navigate("chat");
                    }}
                  />
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
                    onDelete={confirmJournalDeletion}
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
                    onClearAdultContinuity={confirmAdultContinuityDeletion}
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
                  <Feedback error={experienceError} notice={state.notice} />
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
        busy={interactionBusy || librarySelectionBusy}
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
        <OnboardingExperience
          initialDraft={state.characterDraft}
          storageKey={`eidolon:onboarding-draft:${currentUser.id}:${state.activeCharacter.id}`}
          userName={currentUser.display_name ?? "you"}
          onComplete={completeOnboarding}
        />
      ) : null}

      {creatingCompanion ? (
        <OnboardingExperience
          creatingAnother
          initialDraft={authoredCharacterDraft()}
          storageKey={`eidolon:onboarding-draft:${currentUser.id}:new`}
          userName={currentUser.display_name ?? "you"}
          onClose={() => setCreatingCompanion(false)}
          onComplete={completeNewCompanion}
        />
      ) : null}

      <ConfirmationDialog request={confirmation} onClose={() => setConfirmation(null)} />
    </main>
  );
}

function CompanionHeader({ characterName, conversationTitle, privacyMode, theme, relationshipLabel, unreadCount, onOpenLibrary }: { characterName: string; conversationTitle: string | null | undefined; privacyMode: ConversationPrivacyMode; theme: string; relationshipLabel: string; unreadCount: number; onOpenLibrary: () => void }) {
  return (
    <header className="safe-area-header relative z-40 flex min-h-[4.75rem] items-center justify-between gap-4 border-b border-white/[0.07] bg-[#0b0a09]/88 px-4 backdrop-blur-2xl sm:px-6 lg:px-8">
      <button aria-label={`Open conversations with ${characterName}`} className="group flex min-h-11 min-w-0 items-center gap-3 rounded-2xl pr-3 text-left transition hover:bg-white/[0.035]" onClick={onOpenLibrary} type="button">
        <CompanionPortrait name={characterName} size="small" theme={theme} />
        <span className="min-w-0"><span className="flex items-center gap-2"><span className="truncate font-eidolon-display text-xl text-[#eee5dc]">{characterName}</span><Icon className="h-3.5 w-3.5 text-[#847b72] transition group-hover:text-[#ba907a]" name="chevron-down" /></span><span className="block max-w-[55vw] truncate text-[0.68rem] text-[#8b8279] sm:max-w-sm">{conversationTitle?.trim() || relationshipLabel}{privacyMode === "private" ? " · Private" : ""}</span></span>
      </button>
      <button className="relative flex min-h-11 items-center gap-2 rounded-full border border-white/[0.09] bg-white/[0.025] px-3 text-xs text-[#9b9187] transition hover:border-white/[0.18] hover:text-[#d4c8bd]" onClick={onOpenLibrary} type="button"><Icon className="h-4 w-4" name="archive" /><span className="hidden sm:inline">Shared history</span>{unreadCount > 0 ? <span className="grid h-4 min-w-4 place-items-center rounded-full bg-[#bd8163] px-1 text-[0.58rem] font-semibold text-[#190f0b]">{unreadCount > 9 ? "9+" : unreadCount}</span> : null}</button>
    </header>
  );
}

function DesktopNavigation({ active, characterName, theme, onNavigate, onOpenLibrary }: { active: AppView; characterName: string; theme: string; onNavigate: (view: AppView) => void; onOpenLibrary: () => void }) {
  return (
    <aside className="hidden w-[5.5rem] shrink-0 flex-col border-r border-white/[0.07] bg-[#0b0a09]/78 px-3 py-5 backdrop-blur-xl lg:flex xl:w-[16rem] xl:px-4">
      <div className="w-10 overflow-hidden xl:w-full"><EidolonWordmark compact /></div>
      <nav aria-label="Primary" className="my-auto space-y-2">
        {destinations.map((item) => <NavigationButton active={active === item.id} icon={item.icon} key={item.id} label={item.label} onClick={() => onNavigate(item.id)} />)}
      </nav>
      <button className="flex min-h-12 items-center justify-center gap-3 rounded-2xl border border-white/[0.07] bg-white/[0.02] p-1.5 text-left transition hover:border-white/[0.14] hover:bg-white/[0.04] xl:justify-start xl:p-2" onClick={onOpenLibrary} type="button">
        <CompanionPortrait name={characterName} quiet size="small" theme={theme} />
        <span className="hidden min-w-0 xl:block"><span className="block truncate text-sm text-[#d4c9bf]">{characterName}</span><span className="mt-0.5 block text-[0.65rem] text-[#817970]">Switch companion or chapter</span></span>
      </button>
    </aside>
  );
}

function NavigationButton({ active, icon, label, onClick }: { active: boolean; icon: IconName; label: string; onClick: () => void }) {
  return <button aria-current={active ? "page" : undefined} aria-label={label} className={`group relative flex min-h-12 w-full items-center justify-center gap-3 rounded-2xl px-3 transition xl:justify-start ${active ? "bg-[color:var(--color-accent)]/[0.11] text-[color:var(--color-accent-soft)]" : "text-[#817970] hover:bg-white/[0.04] hover:text-[#c1b6ab]"}`} onClick={onClick} title={label} type="button"><Icon className="h-[1.1rem] w-[1.1rem] shrink-0" name={icon} /><span className="hidden text-sm xl:block">{label}</span>{active ? <span className="absolute -left-3 h-6 w-0.5 rounded-full bg-[color:var(--color-accent)] xl:-left-4" /> : null}<span className="pointer-events-none absolute left-14 z-50 hidden whitespace-nowrap rounded-xl border border-white/[0.08] bg-[#171512] px-2.5 py-1.5 text-[0.68rem] text-[#c4b9ae] shadow-xl group-hover:block xl:hidden">{label}</span></button>;
}

function MobileNavigation({ active, onNavigate }: { active: AppView; onNavigate: (view: AppView) => void }) {
  return <nav aria-label="Primary" className="safe-area-nav fixed inset-x-2 bottom-1 z-50 grid grid-cols-5 rounded-[1.35rem] border border-white/[0.1] bg-[#11100e]/95 px-1 pt-1 shadow-[0_16px_55px_rgba(0,0,0,0.5)] backdrop-blur-2xl lg:hidden">{destinations.map((item) => <button aria-current={active === item.id ? "page" : undefined} className={`relative flex min-h-14 min-w-0 flex-col items-center justify-center gap-1 rounded-xl text-[0.6rem] transition ${active === item.id ? "bg-white/[0.045] text-[color:var(--color-accent-soft)]" : "text-[#807870]"}`} key={item.id} onClick={() => onNavigate(item.id)} type="button"><Icon className="h-[1.05rem] w-[1.05rem]" name={item.icon} /><span className="truncate">{item.label}</span>{active === item.id ? <span className="absolute bottom-1 h-0.5 w-4 rounded-full bg-[color:var(--color-accent)]" /> : null}</button>)}</nav>;
}

function SessionOpening() {
  return <main className="eidolon-room relative flex min-h-[100svh] items-center justify-center overflow-hidden px-6 text-[#f3eee5]"><div aria-live="polite" className="relative z-10 text-center" role="status"><EidolonWordmark /><p className="mt-6 text-xs tracking-wide text-[#8a8178]">Opening your private space</p><span className="mx-auto mt-5 block h-px w-24 overflow-hidden bg-white/[0.08]"><span className="block h-full w-1/2 animate-pulse bg-[color:var(--color-accent)]" /></span></div></main>;
}

function relationshipLabel(phase: string): string {
  const labels: Record<string, string> = { "new connection": "You’ve only just met", "warming up": "You’re finding a rhythm", "trusted warmth": "Trust is taking root", "close bond": "A deeply familiar presence", "repair arc": "A little tenderness is needed" };
  return labels[phase] ?? "Here with you";
}
