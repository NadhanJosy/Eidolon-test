"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { ApiError, apiErrorFromResponse, apiFetch, apiJson } from "@/lib/api";

import {
  canonicalAuthEmail,
  canonicalDisplayName,
  completeAuthResponse,
  ownedUser,
  type AuthResponseExpectation
} from "./auth-contract";
import { ownedCharacter, ownedCharacterList } from "./character-contract";
import {
  conversationMatchesCreation,
  ownedConversation,
  ownedConversationList,
  possibleConversationId,
  recoveredCreatedConversation
} from "./conversation-contract";
import { conversationPrivacyMode, readError } from "./controller-utils";
import { completeMessageList } from "./message-contract";
import type {
  AdultStatus,
  AuthMode,
  AuthResponse,
  Character,
  ContentMode,
  Conversation,
  Message,
  RelationshipEvidenceEvent,
  RelationshipMetric,
  User
} from "./types";
import { useAccountController } from "./use-account-controller";
import { useChatController } from "./use-chat-controller";
import { useCompanionStateController } from "./use-companion-state-controller";
import { useKnowledgeController } from "./use-knowledge-controller";
import { useNavigationController } from "./use-navigation-controller";
import { usePrivacyController } from "./use-privacy-controller";

type AuthStage = "submitting" | "opening";

type AuthEntryAction = {
  id: number;
  generation: number;
  mode: AuthMode;
  email: string;
};

type SessionIdentity = {
  generation: number;
  token: string;
  userId: string;
};

type RefreshRequest = {
  generation: number;
  expectedUserId: string | null;
  legacyRefreshToken: string | null;
  promise: Promise<AuthResponse>;
};

class SessionSupersededError extends Error {
  constructor() {
    super("This session action was superseded.");
  }
}

export function useEidolonController() {
  const conversationLoadVersion = useRef(0);
  const sessionResumeStarted = useRef(false);
  const sessionGeneration = useRef(0);
  const sessionIdentity = useRef<SessionIdentity | null>(null);
  const nextAuthEntryId = useRef(0);
  const authEntryAction = useRef<AuthEntryAction | null>(null);
  const refreshRequest = useRef<RefreshRequest | null>(null);
  const sessionRevocation = useRef<Promise<void> | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [sessionReady, setSessionReady] = useState(false);
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");

  const [requestedContentMode, setRequestedContentMode] = useState<ContentMode>("sfw");

  const [busy, setBusy] = useState(false);
  const [authStage, setAuthStage] = useState<AuthStage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const navigation = useNavigationController({
    token,
    sessionOwnerId: user?.id ?? null,
    setBusy,
    setError,
    setNotice,
    onActiveCharacterChange: () => setRequestedContentMode("sfw"),
    refreshSideState
  });
  const activeCharacterId = navigation.state.activeCharacterId;
  const activeConversation = navigation.state.activeConversation;
  const activeConversationId = activeConversation?.id ?? null;
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
    setJournals: knowledge.actions.setJournals,
    setContinuityThreads: knowledge.actions.setContinuityThreads,
    onAdultStatusChange: (_characterId, status) => {
      if (status?.allowed !== true) {
        setRequestedContentMode("sfw");
      }
    }
  });
  const adultStatusReady = Boolean(
    activeCharacterId &&
      companion.state.adultReadinessState === "ready" &&
      companion.state.adultStatus !== null &&
      companion.state.adultStatusCharacterId === activeCharacterId
  );
  const adultProfileEligible = Boolean(
    user?.age_gate_confirmed &&
      navigation.state.activeCharacter?.adult_mode_allowed &&
      navigation.state.activeCharacter.explicit_age !== null &&
      navigation.state.activeCharacter.explicit_age >= 18
  );
  const adultModeAvailable = Boolean(
    adultProfileEligible && adultStatusReady && companion.state.adultStatus?.allowed
  );
  const contentMode: ContentMode =
    requestedContentMode === "adult" && adultModeAvailable ? "adult" : "sfw";
  const chat = useChatController({
    token,
    sessionOwnerId: user?.id ?? null,
    activeConversation: navigation.state.activeConversation,
    activeCharacterId,
    contentMode,
    setError,
    setNotice,
    refreshSideState
  });
  const privacy = usePrivacyController({
    token,
    sessionOwnerId: user?.id ?? null,
    activeConversation,
    activeCharacterId,
    messages: chat.state.messages,
    interactionBusy:
      chat.state.messageMutating ||
      navigation.state.characterMutating ||
      navigation.state.conversationCreating ||
      navigation.state.conversationProvisioning ||
      navigation.state.conversationDeleting ||
      knowledge.state.memoryMutating ||
      knowledge.state.journalMutating ||
      knowledge.state.threadMutating,
    cancelActiveStream: chat.actions.cancelActiveStream,
    resetChat: chat.actions.resetChat,
    setError,
    setNotice,
    refreshSideState
  });
  const account = useAccountController({
    token,
    user,
    activeCharacterId,
    activeConversation,
    interactionBusy:
      busy ||
      chat.state.sending ||
      chat.state.messageMutating ||
      navigation.state.characterMutating ||
      navigation.state.conversationCreating ||
      navigation.state.conversationProvisioning ||
      navigation.state.conversationDeleting ||
      knowledge.state.memoryMutating ||
      knowledge.state.journalMutating ||
      knowledge.state.threadMutating ||
      privacy.conversationMutating,
    setUser,
    setDisplayName,
    setError,
    setNotice,
    onAccountDeleted: (message) => clearAuth({ notice: message, revoke: false }),
    refreshSideState
  });

  function changeContentMode(mode: ContentMode): boolean {
    if (mode === "sfw" && requestedContentMode === "sfw") {
      return true;
    }
    if (
      busy ||
      chat.state.sending ||
      chat.state.messageMutating ||
      navigation.state.characterMutating ||
      navigation.state.conversationCreating ||
      navigation.state.conversationProvisioning ||
      navigation.state.conversationDeleting ||
      knowledge.state.memoryMutating ||
      knowledge.state.journalMutating ||
      knowledge.state.threadMutating ||
      account.state.accountMutating ||
      privacy.conversationMutating
    ) {
      return false;
    }
    setError(null);
    if (mode === "sfw") {
      setRequestedContentMode("sfw");
      setNotice("Safe mode is active.");
      return true;
    }
    if (mode === contentMode) {
      return true;
    }
    if (!adultStatusReady) {
      setRequestedContentMode("sfw");
      setNotice(
        companion.state.adultReadinessState === "error"
          ? "Adult readiness could not be checked. Safe mode remains active."
          : "Adult readiness is still being checked for this companion."
      );
      return false;
    }
    if (!adultModeAvailable) {
      setRequestedContentMode("sfw");
      setNotice(adultModeBlockedNotice(companion.state.adultStatus));
      return false;
    }
    setRequestedContentMode("adult");
    setNotice("Gated adult mode is active. Hard boundaries remain in place.");
    return true;
  }

  async function bootstrap(identity: SessionIdentity, allowRefresh = true): Promise<void> {
    assertSessionApplies(identity);
    try {
      const meValue = await apiJson<unknown>("/auth/me", { token: identity.token });
      assertSessionApplies(identity);
      const me = ownedUser(meValue, { userId: identity.userId });
      if (!me) {
        throw new Error("The account profile returned in an unexpected shape.");
      }
      setUser(me);
      setDisplayName(me.display_name ?? "");

      const characterValue = await apiJson<unknown>("/characters", {
        token: identity.token
      });
      assertSessionApplies(identity);
      const characterList = ownedCharacterList(characterValue, me.id);
      if (!characterList || characterList.length === 0) {
        throw new Error("The companion list returned in an unexpected shape.");
      }

      const conversationValue = await apiJson<unknown>("/conversations", {
        token: identity.token
      });
      assertSessionApplies(identity);
      let conversationList = ownedConversationList(conversationValue, me.id);
      if (!conversationList) {
        throw new Error("Your conversation history could not be opened safely.");
      }
      if (conversationList.length === 0) {
        conversationList = await createInitialConversation(
          identity,
          me.id,
          characterList[0].id,
          conversationList
        );
      }

      const conversation = conversationList[0];
      let character =
        characterList.find((item) => item.id === conversation.character_id) ?? null;
      if (!character) {
        const activeCharacterValue = await apiJson<unknown>(
          `/characters/${conversation.character_id}`,
          { token: identity.token }
        );
        assertSessionApplies(identity);
        character = ownedCharacter(activeCharacterValue, me.id);
      }
      if (!character) {
        throw new Error("The active companion returned in an unexpected shape.");
      }
      await navigation.actions.hydrateNavigation({
        authToken: identity.token,
        characters: characterList,
        conversations: conversationList,
        conversation,
        character,
        shouldApply: () => sessionStillApplies(identity)
      });
      assertSessionApplies(identity);
    } catch (caught) {
      if (
        allowRefresh &&
        sessionStillApplies(identity) &&
        caught instanceof ApiError &&
        caught.status === 401
      ) {
        const refreshedIdentity = await refreshAuthSession();
        await bootstrap(refreshedIdentity, false);
        return;
      }
      throw caught;
    }
  }

  async function createInitialConversation(
    identity: SessionIdentity,
    ownerUserId: string,
    characterId: string,
    knownConversations: Conversation[]
  ): Promise<Conversation[]> {
    const responseValue = await acceptedJsonRequest("/conversations", {
      method: "POST",
      body: JSON.stringify({ character_id: characterId }),
      token: identity.token
    });
    assertSessionApplies(identity);
    const knownConversationIds = new Set(
      knownConversations.map((conversation) => conversation.id)
    );
    const created = ownedConversation(responseValue, ownerUserId);
    if (
      created &&
      !knownConversationIds.has(created.id) &&
      conversationMatchesCreation(created, characterId, "normal")
    ) {
      return [...knownConversations, created];
    }

    const canonicalValue = await apiJson<unknown>("/conversations", {
      token: identity.token
    });
    assertSessionApplies(identity);
    const recovered = recoveredCreatedConversation({
      value: canonicalValue,
      ownerUserId,
      characterId,
      privacyMode: "normal",
      knownConversationIds,
      responseId: possibleConversationId(responseValue)
    });
    if (!recovered) {
      throw new Error(
        "Your first conversation may have opened, but it could not be confirmed. Sign in again before opening another."
      );
    }
    return recovered.conversations;
  }

  async function handleAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (authEntryAction.current) {
      return;
    }
    const canonicalEmail = canonicalAuthEmail(email);
    const canonicalName = canonicalDisplayName(displayName);
    const validationError = authInputError(
      authMode,
      canonicalEmail,
      password,
      canonicalName
    );
    if (validationError) {
      setError(validationError);
      setNotice(null);
      return;
    }
    if (!canonicalEmail || (authMode === "register" && canonicalName === undefined)) {
      return;
    }

    const action: AuthEntryAction = {
      id: ++nextAuthEntryId.current,
      generation: sessionGeneration.current,
      mode: authMode,
      email: canonicalEmail
    };
    authEntryAction.current = action;
    setBusy(true);
    setAuthStage("submitting");
    setError(null);
    setNotice(null);
    let serverSessionMayExist = false;
    try {
      await waitForSessionRevocation();
      assertAuthEntryApplies(action);
      const path = action.mode === "register" ? "/auth/register" : "/auth/login";
      const body =
        action.mode === "register"
          ? { email: action.email, password, display_name: canonicalName ?? null }
          : { email: action.email, password };
      let auth = await withSessionRefreshLock(() =>
        acceptedAuthRequest(
          path,
          {
            method: "POST",
            body: JSON.stringify(body)
          },
          { email: action.email }
        )
      );
      serverSessionMayExist = true;
      assertAuthEntryApplies(action);
      if (!auth) {
        auth = await withSessionRefreshLock(() =>
          acceptedAuthRequest(
            "/auth/refresh",
            { method: "POST", body: JSON.stringify({}) },
            { email: action.email }
          )
        );
        assertAuthEntryApplies(action);
      }
      if (!auth) {
        throw new Error(
          "The account was accepted, but the private session could not be verified. Sign in again before retrying."
        );
      }
      const identity = storeAuth(auth, action.generation);
      setAuthStage("opening");
      await bootstrap(identity, false);
    } catch (caught) {
      if (!authEntryStillApplies(action)) {
        return;
      }
      const message = readError(caught);
      if (serverSessionMayExist || sessionIdentity.current !== null) {
        clearAuth({ revoke: true });
        setError(message);
      } else {
        setError(message);
      }
    } finally {
      finishAuthEntry(action);
    }
  }

  function changeAuthMode(mode: AuthMode) {
    if (mode === authMode || busy || authEntryAction.current) {
      return;
    }
    setAuthMode(mode);
    setPassword("");
    setError(null);
    setNotice(null);
  }

  useEffect(() => {
    if (sessionResumeStarted.current) {
      return;
    }
    sessionResumeStarted.current = true;

    async function resumeSession() {
      const resumeGeneration = sessionGeneration.current;
      const legacyRefreshToken = window.localStorage.getItem("eidolon_refresh_token");
      removeLegacyStoredAuth();
      try {
        const identity = await refreshAuthSession(legacyRefreshToken);
        await bootstrap(identity, false);
      } catch (caught) {
        if (
          resumeGeneration !== sessionGeneration.current ||
          caught instanceof SessionSupersededError
        ) {
          return;
        }
        const invalidSession = caught instanceof ApiError && caught.status === 401;
        clearAuth({ revoke: !invalidSession });
        if (!invalidSession) {
          setError(readError(caught));
        }
      } finally {
        if (resumeGeneration === sessionGeneration.current) {
          setSessionReady(true);
        }
      }
    }
    void resumeSession();

    // Session restoration is intentionally a one-time cookie exchange.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!token || !user) {
      return;
    }
    let active = true;
    let retryTimer: number | null = null;

    async function rotateSession() {
      try {
        await refreshAuthSession();
      } catch (caught) {
        if (!active || caught instanceof SessionSupersededError) {
          return;
        }
        if (caught instanceof ApiError && caught.status === 401) {
          clearAuth({ notice: "Session expired. Please log in again.", revoke: false });
          return;
        }
        retryTimer = window.setTimeout(() => void rotateSession(), 60_000);
      }
    }

    const rotationTimer = window.setTimeout(
      () => void rotateSession(),
      accessTokenRefreshDelay(token)
    );
    return () => {
      active = false;
      window.clearTimeout(rotationTimer);
      if (retryTimer !== null) {
        window.clearTimeout(retryTimer);
      }
    };
    // Rotation follows each newly issued in-memory token.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, user]);

  useEffect(() => {
    if (!token || !user || !activeConversation) {
      return;
    }
    const presenceToken = token;
    const presenceOwnerId = user.id;
    const presenceConversationId = activeConversation.id;
    const presenceCharacterId = activeConversation.character_id;
    let cancelled = false;
    let refreshing = false;
    const abortController = new AbortController();

    async function refreshPresence() {
      if (cancelled || refreshing || document.visibilityState !== "visible") {
        return;
      }
      refreshing = true;
      try {
        const summariesValue = await apiJson<unknown>("/conversations", {
          token: presenceToken,
          signal: abortController.signal
        });
        if (cancelled) {
          return;
        }
        const summaries = ownedConversationList(summariesValue, presenceOwnerId);
        if (!summaries) {
          return;
        }
        const activeSummary = summaries.find(
          (conversation) => conversation.id === presenceConversationId
        );
        if (!activeSummary || activeSummary.character_id !== presenceCharacterId) {
          return;
        }
        navigation.actions.mergeConversationSummaries(summaries);
        if (activeSummary && activeSummary.unread_count > 0) {
          await loadConversation(
            presenceToken,
            activeSummary.id,
            abortController.signal,
            () => !cancelled,
            presenceCharacterId
          );
        }
      } catch {
        // Explicit actions remain the user-facing error path for presence refreshes.
      } finally {
        refreshing = false;
      }
    }

    const interval = window.setInterval(() => void refreshPresence(), 30_000);
    const handleFocus = () => void refreshPresence();
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        void refreshPresence();
      }
    };
    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      cancelled = true;
      abortController.abort();
      window.clearInterval(interval);
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
    // Presence refresh intentionally follows only the authenticated active thread.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, user, activeConversationId]);

  async function loadConversation(
    authToken: string,
    conversationId: string,
    signal?: AbortSignal,
    shouldApply?: () => boolean,
    expectedCharacterId?: string
  ) {
    if (shouldApply !== undefined && !shouldApply()) {
      return;
    }
    const loadVersion = ++conversationLoadVersion.current;
    const loadOwnerId = sessionIdentity.current?.userId;
    if (!loadOwnerId) {
      throw new SessionSupersededError();
    }
    const historyValue = await apiJson<unknown>(`/conversations/${conversationId}/messages`, {
      token: authToken,
      signal
    });
    const history = completeMessageList(historyValue, conversationId);
    if (!history) {
      throw new Error("The conversation history returned in an unexpected shape.");
    }
    if (
      signal?.aborted ||
      loadVersion !== conversationLoadVersion.current ||
      (shouldApply !== undefined && !shouldApply())
    ) {
      return;
    }
    chat.actions.setMessages(history);
    try {
      const lastVisibleAssistant = [...history].reverse().find(
        (message) => message.role === "assistant"
      );
      const receiptValue = await apiJson<unknown>(`/conversations/${conversationId}/read`, {
        method: "POST",
        body: JSON.stringify({
          through_message_id: lastVisibleAssistant?.id ?? null
        }),
        token: authToken,
        signal
      });
      const receipt = ownedConversation(receiptValue, loadOwnerId);
      if (
        !receipt ||
        receipt.id !== conversationId ||
        (expectedCharacterId !== undefined &&
          receipt.character_id !== expectedCharacterId)
      ) {
        throw new Error("The read receipt returned in an unexpected shape.");
      }
      if (
        !signal?.aborted &&
        loadVersion === conversationLoadVersion.current &&
        (shouldApply === undefined || shouldApply())
      ) {
        navigation.actions.mergeConversationSummary(receipt);
      }
    } catch (caught) {
      if (signal?.aborted) {
        return;
      }
      if (caught instanceof ApiError && caught.status === 401) {
        throw caught;
      }
    }
  }

  async function refreshSideState(
    authToken: string,
    characterId: string,
    conversationId: string,
    shouldApply?: () => boolean
  ) {
    if (shouldApply !== undefined && !shouldApply()) {
      return;
    }
    await loadConversation(
      authToken,
      conversationId,
      undefined,
      shouldApply,
      characterId
    );
    if (shouldApply !== undefined && !shouldApply()) {
      return;
    }
    await companion.actions.refreshCompanionState(
      authToken,
      characterId,
      conversationId,
      shouldApply
    );
  }

  async function correctRelationshipMoment(
    eventId: string,
    summary: string,
    eventType?: RelationshipEvidenceEvent["event_type"]
  ) {
    if (!token || !activeCharacterId) return;
    setError(null);
    try {
      await companion.actions.correctRelationshipEvent(
        token,
        activeCharacterId,
        eventId,
        summary,
        eventType
      );
      setNotice("That relationship moment was corrected.");
    } catch (cause) {
      setError(readError(cause));
    }
  }

  async function removeRelationshipMoment(eventId: string) {
    if (!token || !activeCharacterId) return;
    setError(null);
    try {
      await companion.actions.removeRelationshipEvent(token, activeCharacterId, eventId);
      setNotice("That relationship moment was removed.");
    } catch (cause) {
      setError(readError(cause));
    }
  }

  async function resetRelationship(
    mode: "dimensions" | "restart",
    dimensions?: RelationshipMetric[]
  ) {
    if (!token || !activeCharacterId) return;
    setError(null);
    try {
      await companion.actions.resetRelationship(
        token,
        activeCharacterId,
        mode,
        dimensions
      );
      setNotice(
        mode === "restart"
          ? "The relationship was restarted. Your stated boundaries remain active."
          : dimensions
            ? "That part of the relationship interpretation was reset."
          : "The relationship's current interpretation was reset."
      );
    } catch (cause) {
      setError(readError(cause));
    }
  }

  async function refreshAuthSession(
    legacyRefreshToken: string | null = null
  ): Promise<SessionIdentity> {
    const generation = sessionGeneration.current;
    const expectedUserId = sessionIdentity.current?.userId ?? null;
    let request = refreshRequest.current;
    if (
      !request ||
      request.generation !== generation ||
      request.expectedUserId !== expectedUserId ||
      request.legacyRefreshToken !== legacyRefreshToken
    ) {
      const promise = withSessionRefreshLock(async () => {
        const expectation: AuthResponseExpectation = expectedUserId
          ? { userId: expectedUserId }
          : {};
        let auth = await acceptedAuthRequest(
          "/auth/refresh",
          {
            method: "POST",
            body: JSON.stringify(
              legacyRefreshToken ? { refresh_token: legacyRefreshToken } : {}
            )
          },
          expectation
        );
        if (!auth) {
          auth = await acceptedAuthRequest(
            "/auth/refresh",
            { method: "POST", body: JSON.stringify({}) },
            expectation
          );
        }
        if (!auth) {
          throw new Error("The refreshed session returned in an unexpected shape.");
        }
        return auth;
      });
      request = {
        generation,
        expectedUserId,
        legacyRefreshToken,
        promise
      };
      refreshRequest.current = request;
    }
    try {
      const auth = await request.promise;
      if (!refreshContextStillApplies(generation, expectedUserId)) {
        throw new SessionSupersededError();
      }
      return storeAuth(auth, generation);
    } finally {
      if (refreshRequest.current === request) {
        refreshRequest.current = null;
      }
    }
  }

  function storeAuth(auth: AuthResponse, generation: number): SessionIdentity {
    if (generation !== sessionGeneration.current) {
      throw new SessionSupersededError();
    }
    const currentIdentity = sessionIdentity.current;
    if (currentIdentity && currentIdentity.userId !== auth.user.id) {
      throw new SessionSupersededError();
    }
    const identity: SessionIdentity = {
      generation,
      token: auth.access_token,
      userId: auth.user.id
    };
    sessionIdentity.current = identity;
    removeLegacyStoredAuth();
    setPassword("");
    setToken(auth.access_token);
    setUser(auth.user);
    return identity;
  }

  function clearAuth(options: { notice?: string; revoke?: boolean } = {}) {
    const pendingRefresh = refreshRequest.current?.promise ?? null;
    const clearedGeneration = ++sessionGeneration.current;
    sessionIdentity.current = null;
    authEntryAction.current = null;
    conversationLoadVersion.current += 1;
    account.actions.resetAccount();
    removeLegacyStoredAuth();
    setToken(null);
    setUser(null);
    setSessionReady(true);
    setAuthMode("login");
    setPassword("");
    setDisplayName("");
    setAuthStage(null);
    setBusy(false);
    setRequestedContentMode("sfw");
    chat.actions.resetChat();
    knowledge.actions.resetKnowledge();
    navigation.actions.resetNavigation();
    companion.actions.resetCompanionState();
    setError(null);
    setNotice(options.notice ?? null);
    if (options.revoke !== false) {
      queueSessionRevocation(pendingRefresh, clearedGeneration);
    }
  }

  function authEntryStillApplies(action: AuthEntryAction): boolean {
    return (
      authEntryAction.current === action &&
      sessionGeneration.current === action.generation
    );
  }

  function assertAuthEntryApplies(action: AuthEntryAction) {
    if (!authEntryStillApplies(action)) {
      throw new SessionSupersededError();
    }
  }

  function finishAuthEntry(action: AuthEntryAction) {
    if (!authEntryStillApplies(action)) {
      return;
    }
    authEntryAction.current = null;
    setAuthStage(null);
    setBusy(false);
  }

  function sessionStillApplies(identity: SessionIdentity): boolean {
    const currentIdentity = sessionIdentity.current;
    return (
      sessionGeneration.current === identity.generation &&
      currentIdentity?.generation === identity.generation &&
      currentIdentity.userId === identity.userId
    );
  }

  function assertSessionApplies(identity: SessionIdentity) {
    if (!sessionStillApplies(identity)) {
      throw new SessionSupersededError();
    }
  }

  function refreshContextStillApplies(
    generation: number,
    expectedUserId: string | null
  ): boolean {
    if (sessionGeneration.current !== generation) {
      return false;
    }
    const currentIdentity = sessionIdentity.current;
    return expectedUserId === null
      ? currentIdentity === null
      : currentIdentity?.userId === expectedUserId;
  }

  function queueSessionRevocation(
    pendingRefresh: Promise<AuthResponse> | null,
    clearedGeneration: number
  ) {
    const previousRevocation = sessionRevocation.current;
    const request = (async () => {
      await previousRevocation?.catch(() => undefined);
      await pendingRefresh?.catch(() => undefined);
      try {
        await withSessionRefreshLock(() =>
          apiJson<{ status: string }>("/auth/logout", {
            method: "POST",
            body: JSON.stringify({})
          })
        );
      } catch {
        if (
          sessionGeneration.current === clearedGeneration &&
          sessionIdentity.current === null &&
          authEntryAction.current === null
        ) {
          setNotice(
            "This device is signed out locally, but the server session could not be closed. Reload only after the private service is reachable."
          );
        }
      }
    })();
    sessionRevocation.current = request;
    void request.finally(() => {
      if (sessionRevocation.current === request) {
        sessionRevocation.current = null;
      }
    });
  }

  async function waitForSessionRevocation(): Promise<void> {
    const pending = sessionRevocation.current;
    if (pending) {
      await pending;
    }
  }

  return {
    state: {
      token,
      user,
      sessionReady,
      authMode,
      authStage,
      email,
      password,
      displayName,
      characters: navigation.state.characters,
      activeCharacter: navigation.state.activeCharacter,
      characterDraft: navigation.state.characterDraft,
      characterActionId: navigation.state.characterActionId,
      characterMutating: navigation.state.characterMutating,
      conversations: navigation.state.conversations,
      activeConversation: navigation.state.activeConversation,
      conversationCreationMode: navigation.state.conversationCreationMode,
      conversationCreating: navigation.state.conversationCreating,
      provisioningCharacterId: navigation.state.provisioningCharacterId,
      conversationProvisioning: navigation.state.conversationProvisioning,
      deletingConversationId: navigation.state.deletingConversationId,
      conversationDeleting: navigation.state.conversationDeleting,
      conversationSwitchingId: navigation.state.conversationSwitchingId,
      activeConversationPrivacyMode: conversationPrivacyMode(navigation.state.activeConversation),
      conversationTitle: navigation.state.conversationTitle,
      conversationScenarioDraft: navigation.state.conversationScenarioDraft,
      scenarioSaving: navigation.state.scenarioSaving,
      sortedMessages: chat.state.sortedMessages,
      messageDraft: chat.state.messageDraft,
      editingMessageId: chat.state.editingMessageId,
      privateTurn: chat.state.privateTurn,
      pendingOutgoingContent: chat.state.pendingOutgoingContent,
      streamingContent: chat.state.streamingContent,
      streamPhase: chat.state.streamPhase,
      failedTurn: chat.state.failedTurn,
      messageMutating: chat.state.messageMutating,
      conversationMutating: privacy.conversationMutating,
      contentMode,
      adultReadinessState: companion.state.adultReadinessState,
      sideStateError: companion.state.supportingStateError,
      adultStatusReady,
      adultModeAvailable,
      searchQuery: navigation.state.searchQuery,
      searchResults: navigation.state.searchResults,
      searchStatus: navigation.state.searchStatus,
      searchError: navigation.state.searchError,
      memories: knowledge.state.memories,
      continuityThreads: knowledge.state.continuityThreads,
      threadDraft: knowledge.state.threadDraft,
      threadActionId: knowledge.state.threadActionId,
      threadMutating: knowledge.state.threadMutating,
      forgottenMemories: knowledge.state.forgottenMemories,
      memoryView: knowledge.state.memoryView,
      memoryActionId: knowledge.state.memoryActionId,
      memoryMutating: knowledge.state.memoryMutating,
      forgottenMemoriesLoading: knowledge.state.forgottenMemoriesLoading,
      memoryContent: knowledge.state.memoryContent,
      memoryType: knowledge.state.memoryType,
      memoryImportance: knowledge.state.memoryImportance,
      memoryPinned: knowledge.state.memoryPinned,
      editingMemoryId: knowledge.state.editingMemoryId,
      memoryEditContent: knowledge.state.memoryEditContent,
      rememberingMessageId: knowledge.state.rememberingMessageId,
      journals: knowledge.state.journals,
      journalTitle: knowledge.state.journalTitle,
      journalSummary: knowledge.state.journalSummary,
      editingJournalId: knowledge.state.editingJournalId,
      journalEditTitle: knowledge.state.journalEditTitle,
      journalEditSummary: knowledge.state.journalEditSummary,
      journalActionId: knowledge.state.journalActionId,
      journalMutating: knowledge.state.journalMutating,
      accountActionId: account.state.accountActionId,
      accountMutating: account.state.accountMutating,
      relationship: companion.state.relationship,
      relationshipEvents: companion.state.relationshipEvents,
      relationshipActionId: companion.state.relationshipActionId,
      adultStatus: companion.state.adultStatus,
      busy,
      sending: chat.state.sending,
      error,
      notice,
      timeline: companion.state.timeline
    },
    actions: {
      changeAuthMode,
      setEmail,
      setPassword,
      setDisplayName,
      setCharacterDraft: navigation.actions.setCharacterDraft,
      setConversationTitle: navigation.actions.setConversationTitle,
      setConversationScenarioDraft: navigation.actions.setConversationScenarioDraft,
      setMessageDraft: chat.actions.setMessageDraft,
      setPrivateTurn: chat.actions.setPrivateTurn,
      changeContentMode,
      setSearchQuery: navigation.actions.setSearchQuery,
      setMemoryContent: knowledge.actions.setMemoryContent,
      setMemoryType: knowledge.actions.setMemoryType,
      setMemoryImportance: knowledge.actions.setMemoryImportance,
      setMemoryPinned: knowledge.actions.setMemoryPinned,
      setEditingMemoryId: knowledge.actions.setEditingMemoryId,
      setMemoryEditContent: knowledge.actions.setMemoryEditContent,
      changeMemoryView: knowledge.actions.changeMemoryView,
      setJournalTitle: knowledge.actions.setJournalTitle,
      setJournalSummary: knowledge.actions.setJournalSummary,
      setJournalEditTitle: knowledge.actions.setJournalEditTitle,
      setJournalEditSummary: knowledge.actions.setJournalEditSummary,
      setThreadDraft: knowledge.actions.setThreadDraft,
      handleAuth,
      createCharacter: navigation.actions.createCharacter,
      selectCharacter: navigation.actions.selectCharacter,
      createConversationForCurrentCharacter:
        navigation.actions.createConversationForCurrentCharacter,
      selectConversation: navigation.actions.selectConversation,
      searchMessages: navigation.actions.searchMessages,
      sendMessage: chat.actions.sendMessage,
      retryFailedTurn: chat.actions.retryFailedTurn,
      stopResponse: chat.actions.cancelActiveStream,
      saveConversationTitle: navigation.actions.saveConversationTitle,
      setActiveConversationPrivacyMode: navigation.actions.setActiveConversationPrivacyMode,
      saveActiveConversationScenario: navigation.actions.saveActiveConversationScenario,
      resetActiveConversationScenario: navigation.actions.resetActiveConversationScenario,
      cancelEditMessage: chat.actions.cancelEditMessage,
      startEditMessage: chat.actions.startEditMessage,
      rerollMessage: chat.actions.rerollMessage,
      deleteMessage: chat.actions.deleteMessage,
      saveCharacter: navigation.actions.saveCharacter,
      updateUser: account.actions.updateUser,
      addMemory: knowledge.actions.addMemory,
      saveMemoryEdit: knowledge.actions.saveMemoryEdit,
      toggleMemoryPinned: knowledge.actions.toggleMemoryPinned,
      deleteMemory: knowledge.actions.deleteMemory,
      forgetMemory: knowledge.actions.forgetMemory,
      restoreMemory: knowledge.actions.restoreMemory,
      resolveMemoryConflict: knowledge.actions.resolveMemoryConflict,
      rememberMessage: knowledge.actions.rememberMessage,
      forgetMemories: knowledge.actions.forgetMemories,
      addJournal: knowledge.actions.addJournal,
      startJournalEdit: knowledge.actions.startJournalEdit,
      cancelJournalEdit: knowledge.actions.cancelJournalEdit,
      saveJournalEdit: knowledge.actions.saveJournalEdit,
      deleteJournal: knowledge.actions.deleteJournal,
      addContinuityThread: knowledge.actions.addContinuityThread,
      resolveContinuityThread: knowledge.actions.resolveContinuityThread,
      reopenContinuityThread: knowledge.actions.reopenContinuityThread,
      deleteContinuityThread: knowledge.actions.deleteContinuityThread,
      correctRelationshipMoment,
      removeRelationshipMoment,
      resetRelationship,
      exportAccount: account.actions.exportAccount,
      deleteAccount: account.actions.deleteAccount,
      clearConversationMessages: privacy.clearConversationMessages,
      clearMemories: knowledge.actions.clearMemories,
      clearMemoryCategory: knowledge.actions.clearMemoryCategory,
      clearAdultContinuity: knowledge.actions.clearAdultContinuity,
      deleteActiveConversation: navigation.actions.deleteActiveConversation,
      clearAuth: () => clearAuth({ notice: "Logged out." })
    }
  };
}

function adultModeBlockedNotice(status: AdultStatus | null): string {
  const reason = status?.reasons.find((item) => item.trim());
  return reason
    ? `Adult mode stays safe: ${reason}`
    : "Adult mode is locked. Review the Adult settings gates.";
}

function authInputError(
  mode: AuthMode,
  canonicalEmail: string | null,
  password: string,
  canonicalName: string | null | undefined
): string | null {
  if (!canonicalEmail) {
    return "Enter a valid email address.";
  }
  if (password.length === 0 || password.length > 256) {
    return "Enter a password between 1 and 256 characters.";
  }
  if (mode === "register") {
    if (password.length < 12) {
      return "Choose a password with at least 12 characters.";
    }
    if (![...password].some((character) => !/\s/u.test(character))) {
      return "Password must contain at least one non-space character.";
    }
    if (canonicalName === undefined) {
      return "Name must be 120 characters or fewer and cannot contain control characters.";
    }
  }
  return null;
}

async function acceptedAuthRequest(
  path: string,
  options: RequestInit & { token?: string | null },
  expectation: AuthResponseExpectation
): Promise<AuthResponse | null> {
  const value = await acceptedJsonRequest(path, options);
  return completeAuthResponse(value, expectation);
}

async function acceptedJsonRequest(
  path: string,
  options: RequestInit & { token?: string | null }
): Promise<unknown> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }
  const response = await apiFetch(path, { ...options, headers });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, path);
  }
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function removeLegacyStoredAuth() {
  window.localStorage.removeItem("eidolon_token");
  window.localStorage.removeItem("eidolon_refresh_token");
}

async function withSessionRefreshLock<T>(callback: () => Promise<T>): Promise<T> {
  if (typeof navigator !== "undefined" && navigator.locks) {
    return navigator.locks.request("eidolon-session-refresh", callback);
  }
  return callback();
}

function accessTokenRefreshDelay(token: string): number {
  const fallbackDelay = 10 * 60 * 1000;
  try {
    const encodedPayload = token.split(".")[1];
    if (!encodedPayload) {
      return fallbackDelay;
    }
    const normalized = encodedPayload.replaceAll("-", "+").replaceAll("_", "/");
    const padding = "=".repeat((4 - (normalized.length % 4)) % 4);
    const payload = JSON.parse(window.atob(`${normalized}${padding}`)) as {
      exp?: unknown;
    };
    if (typeof payload.exp !== "number" || !Number.isFinite(payload.exp)) {
      return fallbackDelay;
    }
    return Math.max(5_000, payload.exp * 1000 - Date.now() - 60_000);
  } catch {
    return fallbackDelay;
  }
}
