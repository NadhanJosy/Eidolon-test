"use client";

import { FormEvent, useEffect, useState } from "react";

import { ApiError, apiJson } from "@/lib/api";

import { readError } from "./controller-utils";
import type {
  AuthMode,
  AuthResponse,
  Character,
  ContentMode,
  Conversation,
  Message,
  User
} from "./types";
import { useChatController } from "./use-chat-controller";
import { useCompanionStateController } from "./use-companion-state-controller";
import { useKnowledgeController } from "./use-knowledge-controller";
import { useNavigationController } from "./use-navigation-controller";
import { usePrivacyController } from "./use-privacy-controller";
import { useRuntimeStatus } from "./use-runtime-status";

export function useEidolonController() {
  const [token, setToken] = useState<string | null>(() =>
    typeof window === "undefined" ? null : window.localStorage.getItem("eidolon_token")
  );
  const [refreshToken, setRefreshToken] = useState<string | null>(() =>
    typeof window === "undefined" ? null : window.localStorage.getItem("eidolon_refresh_token")
  );
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("user@example.com");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("Nadhan");

  const [contentMode, setContentMode] = useState<ContentMode>("sfw");

  const { runtimeStatus, refreshRuntimeStatus } = useRuntimeStatus();

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const navigation = useNavigationController({
    token,
    setBusy,
    setError,
    setNotice,
    loadConversation,
    refreshSideState
  });
  const activeCharacterId = navigation.state.activeCharacterId;
  const activeConversation = navigation.state.activeConversation;
  const chat = useChatController({
    token,
    activeConversation: navigation.state.activeConversation,
    activeCharacterId,
    contentMode,
    setBusy,
    setError,
    setNotice,
    refreshSideState
  });
  const knowledge = useKnowledgeController({
    token,
    activeCharacterId,
    activeConversation: navigation.state.activeConversation,
    setError,
    setNotice,
    refreshSideState
  });
  const companion = useCompanionStateController({
    setMemories: knowledge.actions.setMemories,
    setJournals: knowledge.actions.setJournals
  });
  const privacy = usePrivacyController({
    token,
    activeConversation,
    activeCharacterId,
    setMessages: chat.actions.setMessages,
    setError,
    setNotice,
    onAccountDeleted: (message) => clearAuth({ notice: message, revoke: false }),
    refreshSideState
  });

  async function bootstrap(authToken: string, allowRefresh = true) {
    setBusy(true);
    setError(null);
    try {
      const me = await apiJson<User>("/auth/me", { token: authToken });
      setUser(me);
      setDisplayName(me.display_name ?? "");

      const characterList = await apiJson<Character[]>("/characters", { token: authToken });

      let conversationList = await apiJson<Conversation[]>("/conversations", {
        token: authToken
      });
      if (conversationList.length === 0) {
        const created = await apiJson<Conversation>("/conversations", {
          method: "POST",
          body: JSON.stringify({}),
          token: authToken
        });
        conversationList = [created];
      }

      const conversation = conversationList[0];
      const character =
        characterList.find((item) => item.id === conversation.character_id) ??
        (await apiJson<Character>(`/characters/${conversation.character_id}`, {
          token: authToken
        }));
      await navigation.actions.hydrateNavigation({
        authToken,
        characters: characterList,
        conversations: conversationList,
        conversation,
        character
      });
    } catch (caught) {
      if (allowRefresh && caught instanceof ApiError && caught.status === 401 && refreshToken) {
        try {
          const nextAccessToken = await refreshAuthSession(refreshToken);
          await bootstrap(nextAccessToken, false);
          return;
        } catch {
          // Fall through to normal session cleanup.
        }
      }
      const message = readError(caught);
      const sessionExpired = caught instanceof ApiError && caught.status === 401;
      clearAuth({
        notice: sessionExpired ? "Session expired. Please log in again." : undefined
      });
      if (!sessionExpired) {
        setError(message);
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const path = authMode === "register" ? "/auth/register" : "/auth/login";
      const body =
        authMode === "register"
          ? { email, password, display_name: displayName }
          : { email, password };
      const auth = await apiJson<AuthResponse>(path, {
        method: "POST",
        body: JSON.stringify(body)
      });
      storeAuth(auth);
      await bootstrap(auth.access_token, false);
    } catch (caught) {
      setError(readError(caught));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function resumeSession() {
      await Promise.resolve();
      if (!cancelled && token && !user) {
        await bootstrap(token);
      }
    }
    void resumeSession();
    return () => {
      cancelled = true;
    };
    // bootstrap intentionally reads the latest state setters only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, user]);

  async function loadConversation(authToken: string, conversationId: string) {
    const history = await apiJson<Message[]>(`/conversations/${conversationId}/messages`, {
      token: authToken
    });
    chat.actions.setMessages(history);
  }

  async function refreshSideState(
    authToken: string,
    characterId: string,
    conversationId: string
  ) {
    await companion.actions.refreshCompanionState(authToken, characterId);
    await loadConversation(authToken, conversationId);
  }

  async function updateUser(payload: Partial<Pick<User, "display_name" | "age_gate_confirmed">>) {
    if (!token) {
      return;
    }
    const updated = await apiJson<User>("/auth/me", {
      method: "PATCH",
      body: JSON.stringify(payload),
      token
    });
    setUser(updated);
    if (activeCharacterId && activeConversation) {
      await refreshSideState(token, activeCharacterId, activeConversation.id);
    }
  }

  async function refreshAuthSession(currentRefreshToken: string) {
    const auth = await apiJson<AuthResponse>("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: currentRefreshToken })
    });
    storeAuth(auth);
    return auth.access_token;
  }

  function storeAuth(auth: AuthResponse) {
    window.localStorage.setItem("eidolon_token", auth.access_token);
    window.localStorage.setItem("eidolon_refresh_token", auth.refresh_token);
    setToken(auth.access_token);
    setRefreshToken(auth.refresh_token);
    setUser(auth.user);
  }

  function clearAuth(options: { notice?: string; revoke?: boolean } = {}) {
    const tokenToRevoke = refreshToken;
    window.localStorage.removeItem("eidolon_token");
    window.localStorage.removeItem("eidolon_refresh_token");
    setToken(null);
    setRefreshToken(null);
    setUser(null);
    chat.actions.resetChat();
    knowledge.actions.resetKnowledge();
    navigation.actions.resetNavigation();
    companion.actions.resetCompanionState();
    setError(null);
    setNotice(options.notice ?? null);
    if (tokenToRevoke && options.revoke !== false) {
      void apiJson<{ status: string }>("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: tokenToRevoke })
      }).catch(() => undefined);
    }
  }

  return {
    state: {
      token,
      user,
      authMode,
      email,
      password,
      displayName,
      characters: navigation.state.characters,
      activeCharacter: navigation.state.activeCharacter,
      newCharacterName: navigation.state.newCharacterName,
      characterDraft: navigation.state.characterDraft,
      conversations: navigation.state.conversations,
      activeConversation: navigation.state.activeConversation,
      conversationTitle: navigation.state.conversationTitle,
      sortedMessages: chat.state.sortedMessages,
      messageDraft: chat.state.messageDraft,
      editingMessageId: chat.state.editingMessageId,
      streamingContent: chat.state.streamingContent,
      contentMode,
      searchQuery: navigation.state.searchQuery,
      searchResults: navigation.state.searchResults,
      memories: knowledge.state.memories,
      memoryContent: knowledge.state.memoryContent,
      memoryType: knowledge.state.memoryType,
      memoryImportance: knowledge.state.memoryImportance,
      memoryPinned: knowledge.state.memoryPinned,
      editingMemoryId: knowledge.state.editingMemoryId,
      memoryEditContent: knowledge.state.memoryEditContent,
      journals: knowledge.state.journals,
      journalTitle: knowledge.state.journalTitle,
      journalSummary: knowledge.state.journalSummary,
      relationship: companion.state.relationship,
      adultStatus: companion.state.adultStatus,
      jobs: companion.state.jobs,
      debug: companion.state.debug,
      panel: companion.state.panel,
      runtimeStatus,
      busy,
      sending: chat.state.sending,
      error,
      notice,
      timeline: companion.state.timeline
    },
    actions: {
      setAuthMode,
      setEmail,
      setPassword,
      setDisplayName,
      setNewCharacterName: navigation.actions.setNewCharacterName,
      setCharacterDraft: navigation.actions.setCharacterDraft,
      setConversationTitle: navigation.actions.setConversationTitle,
      setMessageDraft: chat.actions.setMessageDraft,
      setContentMode,
      setSearchQuery: navigation.actions.setSearchQuery,
      setMemoryContent: knowledge.actions.setMemoryContent,
      setMemoryType: knowledge.actions.setMemoryType,
      setMemoryImportance: knowledge.actions.setMemoryImportance,
      setMemoryPinned: knowledge.actions.setMemoryPinned,
      setEditingMemoryId: knowledge.actions.setEditingMemoryId,
      setMemoryEditContent: knowledge.actions.setMemoryEditContent,
      setJournalTitle: knowledge.actions.setJournalTitle,
      setJournalSummary: knowledge.actions.setJournalSummary,
      setPanel: companion.actions.setPanel,
      refreshRuntimeStatus,
      handleAuth,
      createCharacter: navigation.actions.createCharacter,
      selectCharacter: navigation.actions.selectCharacter,
      createConversationForCurrentCharacter:
        navigation.actions.createConversationForCurrentCharacter,
      selectConversation: navigation.actions.selectConversation,
      searchMessages: navigation.actions.searchMessages,
      sendMessage: chat.actions.sendMessage,
      saveConversationTitle: navigation.actions.saveConversationTitle,
      queueProactive: privacy.queueProactive,
      cancelEditMessage: chat.actions.cancelEditMessage,
      startEditMessage: chat.actions.startEditMessage,
      rerollMessage: chat.actions.rerollMessage,
      saveCharacter: navigation.actions.saveCharacter,
      updateUser,
      addMemory: knowledge.actions.addMemory,
      saveMemoryEdit: knowledge.actions.saveMemoryEdit,
      toggleMemoryPinned: knowledge.actions.toggleMemoryPinned,
      deleteMemory: knowledge.actions.deleteMemory,
      forgetMemories: knowledge.actions.forgetMemories,
      addJournal: knowledge.actions.addJournal,
      exportAccount: privacy.exportAccount,
      deleteAccount: privacy.deleteAccount,
      clearConversationMessages: privacy.clearConversationMessages,
      clearMemories: knowledge.actions.clearMemories,
      deleteActiveConversation: navigation.actions.deleteActiveConversation,
      clearAuth: () => clearAuth({ notice: "Logged out." })
    }
  };
}
