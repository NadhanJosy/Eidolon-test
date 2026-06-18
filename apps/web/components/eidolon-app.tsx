"use client";

import type { ContentMode } from "@/components/eidolon/types";
import { AuthScreen } from "@/components/eidolon/auth-screen";
import { ChatSurface } from "@/components/eidolon/chat-surface";
import { Inspector } from "@/components/eidolon/inspector";
import { RuntimeStatusStrip } from "@/components/eidolon/runtime-status-strip";
import { secondaryButtonClass } from "@/components/eidolon/ui";
import { useEidolonController } from "@/components/eidolon/use-eidolon-controller";
import { WorkspaceRail } from "@/components/eidolon/workspace-rail";

export function EidolonApp() {
  const { state, actions } = useEidolonController();

  if (!state.user || !state.token) {
    return (
      <AuthScreen
        authMode={state.authMode}
        setAuthMode={actions.setAuthMode}
        email={state.email}
        setEmail={actions.setEmail}
        password={state.password}
        setPassword={actions.setPassword}
        displayName={state.displayName}
        setDisplayName={actions.setDisplayName}
        busy={state.busy}
        error={state.error}
        notice={state.notice}
        onSubmit={actions.handleAuth}
      />
    );
  }
  const currentUser = state.user;

  return (
    <main className="min-h-screen bg-ink text-paper">
      <header className="border-b border-line bg-panel/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1500px] flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <p className="text-xs uppercase text-zinc-500">Eidolon private runtime</p>
            <h1 className="truncate text-xl font-semibold">
              {state.activeCharacter?.name ?? "Conversation"}
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <RuntimeStatusStrip
              status={state.runtimeStatus}
              onRefresh={() => void actions.refreshRuntimeStatus()}
            />
            <span className="rounded-md border border-line bg-ink px-3 py-2 text-zinc-300">
              {currentUser.display_name ?? currentUser.email}
            </span>
            <span className="rounded-md border border-line bg-ink px-3 py-2 text-zinc-300">
              {state.relationship.mood} · {state.relationship.conflict_state}
            </span>
            <select
              value={state.contentMode}
              onChange={(event) => actions.setContentMode(event.target.value as ContentMode)}
              className="rounded-md border border-line bg-ink px-3 py-2"
              aria-label="Content mode"
            >
              <option value="sfw">SFW</option>
              <option value="adult">Adult gated</option>
            </select>
            <button
              className={secondaryButtonClass}
              onClick={() => actions.clearAuth()}
              type="button"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1500px] gap-4 px-4 py-4 xl:grid-cols-[280px_minmax(0,1fr)_420px]">
        <WorkspaceRail
          characters={state.characters}
          activeCharacter={state.activeCharacter}
          activeConversation={state.activeConversation}
          conversations={state.conversations}
          searchQuery={state.searchQuery}
          setSearchQuery={actions.setSearchQuery}
          searchResults={state.searchResults}
          newCharacterName={state.newCharacterName}
          setNewCharacterName={actions.setNewCharacterName}
          onCreateCharacter={actions.createCharacter}
          onSelectCharacter={actions.selectCharacter}
          onCreateConversation={actions.createConversationForCurrentCharacter}
          onSearch={actions.searchMessages}
          onSelectConversation={actions.selectConversation}
        />

        <ChatSurface
          title={state.activeConversation?.title ?? "Chat"}
          editableTitle={state.conversationTitle}
          setEditableTitle={actions.setConversationTitle}
          messageCount={state.sortedMessages.length}
          memoryCount={state.memories.length}
          journalCount={state.journals.length}
          relationship={state.relationship}
          adultStatus={state.adultStatus}
          contentMode={state.contentMode}
          messages={state.sortedMessages}
          streamingContent={state.streamingContent}
          draft={state.messageDraft}
          setDraft={actions.setMessageDraft}
          sending={state.sending}
          busy={state.busy}
          editingMessageId={state.editingMessageId}
          error={state.error}
          notice={state.notice}
          onSubmit={actions.sendMessage}
          onSaveTitle={actions.saveConversationTitle}
          onQueueProactive={actions.queueProactive}
          onCancelEdit={actions.cancelEditMessage}
          onEdit={actions.startEditMessage}
          onReroll={actions.rerollMessage}
        />

        <Inspector
          panel={state.panel}
          setPanel={actions.setPanel}
          user={currentUser}
          draft={state.characterDraft}
          setDraft={actions.setCharacterDraft}
          relationship={state.relationship}
          timeline={state.timeline}
          memories={state.memories}
          journals={state.journals}
          jobs={state.jobs}
          debug={state.debug}
          conversations={state.conversations}
          messageCount={state.sortedMessages.length}
          activeConversationTitle={state.activeConversation?.title ?? "Untitled thread"}
          adultStatus={state.adultStatus}
          displayName={state.displayName}
          setDisplayName={actions.setDisplayName}
          memoryContent={state.memoryContent}
          memoryType={state.memoryType}
          memoryImportance={state.memoryImportance}
          memoryPinned={state.memoryPinned}
          editingMemoryId={state.editingMemoryId}
          memoryEditContent={state.memoryEditContent}
          journalTitle={state.journalTitle}
          journalSummary={state.journalSummary}
          setMemoryContent={actions.setMemoryContent}
          setMemoryType={actions.setMemoryType}
          setMemoryImportance={actions.setMemoryImportance}
          setMemoryPinned={actions.setMemoryPinned}
          setEditingMemoryId={actions.setEditingMemoryId}
          setMemoryEditContent={actions.setMemoryEditContent}
          setJournalTitle={actions.setJournalTitle}
          setJournalSummary={actions.setJournalSummary}
          onSaveCharacter={actions.saveCharacter}
          onToggleAgeGate={() =>
            void actions.updateUser({ age_gate_confirmed: !currentUser.age_gate_confirmed })
          }
          onSaveName={() => void actions.updateUser({ display_name: state.displayName })}
          onAddMemory={actions.addMemory}
          onSaveMemoryEdit={actions.saveMemoryEdit}
          onToggleMemoryPinned={actions.toggleMemoryPinned}
          onDeleteMemory={actions.deleteMemory}
          onForgetMemories={actions.forgetMemories}
          onAddJournal={actions.addJournal}
          onExport={actions.exportAccount}
          onDeleteAccount={actions.deleteAccount}
          onClearMessages={actions.clearConversationMessages}
          onClearMemories={actions.clearMemories}
          onDeleteConversation={actions.deleteActiveConversation}
          onLogout={actions.clearAuth}
        />
      </div>
    </main>
  );
}
