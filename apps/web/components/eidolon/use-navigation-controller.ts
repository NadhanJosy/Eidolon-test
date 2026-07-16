"use client";

import { FormEvent, useLayoutEffect, useRef, useState } from "react";

import { apiErrorFromResponse, apiFetch, apiJson } from "@/lib/api";

import {
  characterPayloadFromDraft,
  validateCharacterDraft
} from "./character-builder-model";
import {
  characterMatchesPayload,
  ownedCharacter,
  ownedCharacterList,
  possibleCharacterId,
  recoveredCreatedCharacter,
  type CharacterPayload
} from "./character-contract";
import {
  advancedConversationSummary,
  canonicalConversationTitle,
  conversationMatchesCreation,
  conversationMatchesPrivacy,
  conversationMatchesScenario,
  conversationMatchesTitle,
  hasPositiveDeleteCount,
  ownedConversation,
  ownedConversationList,
  possibleConversationId,
  recoveredCreatedConversation,
  type ConversationScenarioExpectation
} from "./conversation-contract";
import {
  conversationCustomScenario,
  conversationPrivacyMode,
  conversationScenarioMode,
  emptyCharacterDraft,
  readError,
  toCharacterDraft
} from "./controller-utils";
import { completeMessageList } from "./message-contract";
import type {
  Character,
  CharacterCreationResult,
  CharacterDraft,
  Conversation,
  Message,
  SearchStatus
} from "./types";
import type { ConversationPrivacyMode } from "./types";

type UseNavigationControllerArgs = {
  token: string | null;
  sessionOwnerId: string | null;
  setBusy: (value: boolean) => void;
  setError: (value: string | null) => void;
  setNotice: (value: string | null) => void;
  onActiveCharacterChange: (characterId: string | null) => void;
  refreshSideState: (
    authToken: string,
    characterId: string,
    conversationId: string,
    shouldApply?: () => boolean
  ) => Promise<void>;
};

type BootstrapNavigationArgs = {
  authToken: string;
  characters: Character[];
  conversations: Conversation[];
  conversation: Conversation;
  character: Character;
  shouldApply?: () => boolean;
};

type StableNavigation = {
  conversation: Conversation;
  character: Character;
  title: string;
};

type SearchRequest = {
  conversationId: string;
  navigationVersion: number;
  query: string;
};

type CharacterActionId = "create" | "save";

type CharacterMutation = {
  id: number;
  actionId: CharacterActionId;
  ownerUserId: string;
  token: string;
  sessionGeneration: number;
  navigationVersion: number;
  characterId: string | null;
};

type ConversationCreation = {
  id: number;
  ownerUserId: string;
  token: string;
  sessionGeneration: number;
  navigationVersion: number;
  character: Character;
  privacyMode: ConversationPrivacyMode;
};

type ConversationProvision = {
  id: number;
  ownerUserId: string;
  token: string;
  sessionGeneration: number;
  navigationVersion: number;
  character: Character;
  parentCharacterMutationId: number | null;
};

type ConversationDeletion = {
  id: number;
  ownerUserId: string;
  token: string;
  sessionGeneration: number;
  navigationVersion: number;
  conversation: Conversation;
  character: Character;
};

type ConversationMetadataIntent =
  | { kind: "title"; title: string | null }
  | { kind: "privacy"; privacyMode: ConversationPrivacyMode }
  | { kind: "scenario"; scenario: ConversationScenarioExpectation };

type ConversationMetadataMutation = {
  id: number;
  ownerUserId: string;
  token: string;
  sessionGeneration: number;
  navigationVersion: number;
  conversationId: string;
  characterId: string;
  intent: ConversationMetadataIntent;
};

export function useNavigationController({
  token,
  sessionOwnerId,
  setBusy,
  setError,
  setNotice,
  onActiveCharacterChange,
  refreshSideState
}: UseNavigationControllerArgs) {
  const navigationVersion = useRef(0);
  const sessionGeneration = useRef(0);
  const nextCharacterMutationId = useRef(0);
  const characterMutation = useRef<CharacterMutation | null>(null);
  const nextConversationCreationId = useRef(0);
  const conversationCreation = useRef<ConversationCreation | null>(null);
  const nextConversationProvisionId = useRef(0);
  const conversationProvision = useRef<ConversationProvision | null>(null);
  const nextConversationDeletionId = useRef(0);
  const conversationDeletion = useRef<ConversationDeletion | null>(null);
  const nextConversationMetadataMutationId = useRef(0);
  const conversationMetadataMutation = useRef<ConversationMetadataMutation | null>(null);
  const sessionOwnerIdRef = useRef(sessionOwnerId);
  const searchRequestInFlight = useRef<SearchRequest | null>(null);
  const stableNavigation = useRef<StableNavigation | null>(null);
  const activeCharacterIdRef = useRef<string | null>(null);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [activeCharacter, setActiveCharacter] = useState<Character | null>(null);
  const [characterDraft, setCharacterDraft] = useState<CharacterDraft>(emptyCharacterDraft());
  const [characterActionId, setCharacterActionId] = useState<CharacterActionId | null>(null);

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [conversationSwitchingId, setConversationSwitchingId] = useState<string | null>(null);
  const activeConversationRef = useRef<Conversation | null>(activeConversation);
  activeConversationRef.current = activeConversation;
  const [conversationTitle, setConversationTitle] = useState("");
  const [conversationCreationMode, setConversationCreationMode] =
    useState<ConversationPrivacyMode | null>(null);
  const [provisioningCharacterId, setProvisioningCharacterId] = useState<string | null>(
    null
  );
  const [deletingConversationId, setDeletingConversationId] = useState<string | null>(null);
  const [conversationScenarioDraft, setConversationScenarioDraft] = useState("");
  const [scenarioSaving, setScenarioSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Message[]>([]);
  const [searchStatus, setSearchStatus] = useState<SearchStatus>("idle");
  const [searchError, setSearchError] = useState<string | null>(null);
  const searchQueryRef = useRef(searchQuery);
  searchQueryRef.current = searchQuery;

  const activeCharacterId = activeCharacter?.id ?? activeConversation?.character_id ?? null;

  useLayoutEffect(() => {
    if (sessionOwnerIdRef.current === sessionOwnerId) {
      return;
    }
    sessionOwnerIdRef.current = sessionOwnerId;
    invalidateSessionMutations();
  }, [sessionOwnerId]);

  async function hydrateNavigation({
    authToken,
    characters: nextCharacters,
    conversations: nextConversations,
    conversation,
    character,
    shouldApply
  }: BootstrapNavigationArgs) {
    if (shouldApply !== undefined && !shouldApply()) {
      return;
    }
    navigationVersion.current += 1;
    clearSearchState();
    setCharacters(nextCharacters);
    setConversations(nextConversations);
    setActiveConversation(conversation);
    setConversationTitle(conversation.title ?? "");
    setConversationScenarioDraft(conversationCustomScenario(conversation));
    setCurrentCharacter(character);
    stableNavigation.current = {
      conversation,
      character,
      title: conversation.title ?? ""
    };
    await refreshSideState(
      authToken,
      character.id,
      conversation.id,
      shouldApply
    );
  }

  async function reloadCharacters(authToken: string) {
    const value = await apiJson<unknown>("/characters", { token: authToken });
    const ownerUserId = sessionOwnerIdRef.current;
    const characterList = ownerUserId ? ownedCharacterList(value, ownerUserId) : null;
    if (!characterList) {
      throw new Error("Your companions could not be opened safely.");
    }
    setCharacters(characterList);
    return characterList;
  }

  async function reloadConversations(authToken: string, shouldApply?: () => boolean) {
    const value = await apiJson<unknown>("/conversations", {
      token: authToken
    });
    const ownerUserId = sessionOwnerIdRef.current;
    const conversationList = ownerUserId
      ? ownedConversationList(value, ownerUserId)
      : null;
    if (!conversationList) {
      throw new Error("Your conversation history could not be opened safely.");
    }
    if (shouldApply === undefined || shouldApply()) {
      syncConversationSummaries(conversationList);
    }
    return conversationList;
  }

  async function selectCharacter(
    character: Character,
    requestedVersion?: number
  ): Promise<boolean> {
    return selectCharacterWithProvision(character, requestedVersion, null);
  }

  async function selectCharacterWithProvision(
    character: Character,
    requestedVersion: number | undefined,
    parentCharacterMutation: CharacterMutation | null
  ): Promise<boolean> {
    if (!token || !sessionOwnerId) {
      return false;
    }
    if (conversationProvision.current?.character.id === character.id) {
      return false;
    }
    const selectionVersion = requestedVersion ?? ++navigationVersion.current;
    if (selectionVersion !== navigationVersion.current) {
      return false;
    }
    clearSearchState();
    setError(null);
    try {
      const conversationList = await reloadConversations(
        token,
        () => selectionVersion === navigationVersion.current
      );
      if (selectionVersion !== navigationVersion.current) {
        return false;
      }
      let characterConversation: Conversation | null =
        conversationList.find(
          (conversation) => conversation.character_id === character.id
        ) ?? null;
      if (!characterConversation) {
        characterConversation = await provisionConversationForSelection(
          character,
          conversationList,
          selectionVersion,
          parentCharacterMutation
        );
        if (!characterConversation) {
          return false;
        }
      }
      if (selectionVersion !== navigationVersion.current) {
        return false;
      }
      return await selectConversation(characterConversation, character, selectionVersion);
    } catch (caught) {
      if (selectionVersion === navigationVersion.current) {
        setError(readError(caught));
        await restoreStableSelection(token, selectionVersion);
      }
      return false;
    }
  }

  async function provisionConversationForSelection(
    character: Character,
    knownConversations: Conversation[],
    selectionVersion: number,
    parentCharacterMutation: CharacterMutation | null
  ): Promise<Conversation | null> {
    const action = beginConversationProvision(
      character,
      selectionVersion,
      parentCharacterMutation
    );
    if (!action) {
      if (selectionVersion === navigationVersion.current) {
        throw new Error(
          "Another companion or room change is still settling. Wait for it to finish before opening this companion."
        );
      }
      return null;
    }
    const knownConversationIds = new Set(
      knownConversations.map((conversation) => conversation.id)
    );
    try {
      const responseValue = await acceptedJsonMutation(
        "/conversations",
        "POST",
        {
          character_id: action.character.id,
          privacy_mode: "normal"
        },
        action.token
      );
      if (!conversationProvisionStillApplies(action)) {
        return null;
      }

      let created = ownedConversation(responseValue, action.ownerUserId);
      let canonicalConversations: Conversation[] | null = null;
      if (
        !created ||
        knownConversationIds.has(created.id) ||
        !conversationMatchesCreation(created, action.character.id, "normal")
      ) {
        let listValue: unknown;
        try {
          listValue = await apiJson<unknown>("/conversations", {
            token: action.token
          });
        } catch {
          throw new Error(
            `A room may have opened for ${action.character.name}, but its saved state could not be verified. Reload Eidolon before trying again.`
          );
        }
        if (!conversationProvisionStillApplies(action)) {
          return null;
        }
        const recovered = recoveredCreatedConversation({
          value: listValue,
          ownerUserId: action.ownerUserId,
          characterId: action.character.id,
          privacyMode: "normal",
          knownConversationIds,
          responseId: possibleConversationId(responseValue)
        });
        if (!recovered) {
          throw new Error(
            `A room may have opened for ${action.character.name}, but the canonical thread list did not verify one exact new room. Reload Eidolon before trying again.`
          );
        }
        created = recovered.conversation;
        canonicalConversations = recovered.conversations;
      }

      if (!conversationProvisionStillApplies(action)) {
        return null;
      }
      if (canonicalConversations) {
        syncConversationSummaries(canonicalConversations);
      } else {
        mergeConversationSummary(created);
      }
      return created;
    } finally {
      finishConversationProvision(action);
    }
  }

  async function createCharacter(draft: CharacterDraft): Promise<CharacterCreationResult> {
    if (!token || !sessionOwnerId) {
      return {
        ok: false,
        error: "Your session is no longer available. Sign in again before creating a companion.",
        persisted: false
      };
    }
    const validationErrors = validateCharacterDraft(draft, {
      requireAuthoredProfile: true
    });
    if (Object.keys(validationErrors).length > 0) {
      const message = "Complete the highlighted companion profile fields before creating it.";
      setError(message);
      return { ok: false, error: message, persisted: false };
    }
    if (characterMutation.current) {
      return {
        ok: false,
        error: "Another companion change is still settling. Wait for it to finish before creating one.",
        persisted: false
      };
    }

    const payload = characterPayloadFromDraft(draft) as CharacterPayload;
    const knownCharacterIds = new Set(characters.map((character) => character.id));
    const operationVersion = navigationVersion.current + 1;
    const action = beginCharacterMutation("create", null, operationVersion);
    if (!action) {
      return {
        ok: false,
        error: "This companion could not be created in the current session.",
        persisted: false
      };
    }
    navigationVersion.current = operationVersion;
    setError(null);
    try {
      const responseValue = await acceptedJsonMutation(
        "/characters",
        "POST",
        payload,
        action.token
      );
      if (!characterActionStillApplies(action)) {
        return {
          ok: false,
          error: `${payload.name} was created for the previous session.`,
          persisted: true
        };
      }

      let created = ownedCharacter(responseValue, action.ownerUserId);
      let canonicalCharacters: Character[] | null = null;
      if (
        !created ||
        knownCharacterIds.has(created.id) ||
        !characterMatchesPayload(created, payload)
      ) {
        let listValue: unknown;
        try {
          listValue = await apiJson<unknown>("/characters", { token: action.token });
        } catch {
          const message =
            `${payload.name} may have been created, but its saved profile could not be verified. ` +
            "Your authored draft is still here.";
          if (characterActionStillApplies(action)) {
            setError(message);
          }
          return { ok: false, error: message, persisted: true };
        }
        if (!characterActionStillApplies(action)) {
          return {
            ok: false,
            error: `${payload.name} was created for the previous session.`,
            persisted: true
          };
        }
        const recovered = recoveredCreatedCharacter({
          value: listValue,
          ownerUserId: action.ownerUserId,
          knownCharacterIds,
          payload,
          responseId: possibleCharacterId(responseValue)
        });
        if (!recovered) {
          const message =
            `${payload.name} may have been created, but the canonical character list did not ` +
            "verify that exact profile. Your authored draft is still here.";
          setError(message);
          return { ok: false, error: message, persisted: true };
        }
        created = recovered.character;
        canonicalCharacters = recovered.characters;
      }

      if (!characterActionStillApplies(action)) {
        return {
          ok: false,
          error: `${payload.name} was created for the previous session.`,
          persisted: true
        };
      }
      if (canonicalCharacters) {
        setCharacters(canonicalCharacters);
      } else {
        mergeCharacterSummary(created);
      }
      if (operationVersion !== navigationVersion.current) {
        const message = `${created.name} was created, but another navigation took priority.`;
        setError(message);
        return { ok: false, error: message, persisted: true };
      }

      const selected = await selectCharacterWithProvision(
        created,
        operationVersion,
        action
      );
      if (!characterActionStillApplies(action)) {
        return {
          ok: false,
          error: `${created.name} was created for the previous session.`,
          persisted: true
        };
      }
      if (!selected) {
        return {
          ok: false,
          error: `${created.name} was created, but its conversation could not be opened. It remains in Characters.`,
          persisted: true
        };
      }
      setNotice(`${created.name} is ready.`);
      return { ok: true };
    } catch (caught) {
      const message = readError(caught);
      if (characterActionStillApplies(action)) {
        setError(message);
        if (operationVersion === navigationVersion.current) {
          await restoreStableSelection(action.token, operationVersion);
        }
      }
      return { ok: false, error: message, persisted: false };
    } finally {
      finishCharacterMutation(action);
    }
  }

  async function selectConversation(
    conversation: Conversation,
    knownCharacter?: Character,
    requestedVersion?: number
  ): Promise<boolean> {
    if (!token || !sessionOwnerId) {
      return false;
    }
    const ownerUserId = sessionOwnerId;
    const selectionVersion = requestedVersion ?? ++navigationVersion.current;
    if (selectionVersion !== navigationVersion.current) {
      return false;
    }
    const fallback = stableNavigation.current;
    setConversationSwitchingId(conversation.id);
    clearSearchState();
    setActiveConversation(conversation);
    setConversationTitle(conversation.title ?? "");
    setConversationScenarioDraft(conversationCustomScenario(conversation));
    setError(null);
    try {
      let character =
        knownCharacter ??
        characters.find((item) => item.id === conversation.character_id) ??
        null;
      if (!character) {
        const value = await apiJson<unknown>(
          `/characters/${conversation.character_id}`,
          { token }
        );
        character = ownedCharacter(value, ownerUserId);
        if (!character || character.id !== conversation.character_id) {
          throw new Error("The companion profile returned in an unexpected shape.");
        }
      }
      if (selectionVersion !== navigationVersion.current) {
        return false;
      }
      setCurrentCharacter(character);
      const shouldApply = () => selectionVersion === navigationVersion.current;
      await refreshSideState(token, character.id, conversation.id, shouldApply);
      if (selectionVersion !== navigationVersion.current) {
        return false;
      }
      stableNavigation.current = {
        conversation,
        character,
        title: conversation.title ?? ""
      };
      return true;
    } catch (caught) {
      if (selectionVersion !== navigationVersion.current) {
        return false;
      }
      setActiveConversation(fallback?.conversation ?? null);
      setConversationTitle(fallback?.title ?? "");
      setConversationScenarioDraft(conversationCustomScenario(fallback?.conversation ?? null));
      if (fallback) {
        setCurrentCharacter(fallback.character);
      } else {
        clearCurrentCharacter();
      }
      setError(readError(caught));
      if (fallback) {
        await refreshSideState(
          token,
          fallback.character.id,
          fallback.conversation.id,
          () => selectionVersion === navigationVersion.current
        ).catch(() => undefined);
      }
      return false;
    } finally {
      if (selectionVersion === navigationVersion.current) {
        setConversationSwitchingId(null);
      }
    }
  }

  async function createConversationForCurrentCharacter(
    privacyMode: ConversationPrivacyMode = "normal"
  ): Promise<boolean> {
    if (privacyMode !== "normal" && privacyMode !== "private") {
      setError("That privacy choice is not available for this conversation.");
      return false;
    }
    const targetCharacter =
      activeCharacter ??
      characters.find((character) => character.id === activeConversation?.character_id);
    if (!token || !sessionOwnerId || !targetCharacter) {
      setError("Choose a companion before opening a new conversation.");
      return false;
    }
    if (
      conversationCreation.current ||
      conversationProvision.current ||
      characterMutation.current
    ) {
      return false;
    }

    const knownConversationIds = new Set(conversations.map((conversation) => conversation.id));
    const operationVersion = navigationVersion.current + 1;
    const action = beginConversationCreation(
      targetCharacter,
      privacyMode,
      operationVersion
    );
    if (!action) {
      return false;
    }
    navigationVersion.current = operationVersion;
    clearSearchState();
    setError(null);
    try {
      const responseValue = await acceptedJsonMutation(
        "/conversations",
        "POST",
        {
          character_id: action.character.id,
          privacy_mode: action.privacyMode
        },
        action.token
      );
      if (!conversationCreationStillApplies(action)) {
        return false;
      }

      let created = ownedConversation(responseValue, action.ownerUserId);
      let canonicalConversations: Conversation[] | null = null;
      if (
        !created ||
        knownConversationIds.has(created.id) ||
        !conversationMatchesCreation(
          created,
          action.character.id,
          action.privacyMode
        )
      ) {
        let listValue: unknown;
        try {
          listValue = await apiJson<unknown>("/conversations", { token: action.token });
        } catch {
          if (conversationCreationStillApplies(action)) {
            setError(
              "The conversation may have opened, but it could not be confirmed. Reload Eidolon before trying again."
            );
          }
          return false;
        }
        if (!conversationCreationStillApplies(action)) {
          return false;
        }
        const recovered = recoveredCreatedConversation({
          value: listValue,
          ownerUserId: action.ownerUserId,
          characterId: action.character.id,
          privacyMode: action.privacyMode,
          knownConversationIds,
          responseId: possibleConversationId(responseValue)
        });
        if (!recovered) {
          setError(
            "The conversation may have opened, but your history could not confirm it. Reload Eidolon before trying again."
          );
          return false;
        }
        created = recovered.conversation;
        canonicalConversations = recovered.conversations;
      }

      if (!conversationCreationStillApplies(action)) {
        return false;
      }
      if (canonicalConversations) {
        syncConversationSummaries(canonicalConversations);
      } else {
        mergeConversationSummary(created);
      }
      if (operationVersion !== navigationVersion.current) {
        return false;
      }
      const selected = await selectConversation(
        created,
        action.character,
        operationVersion
      );
      if (!conversationCreationStillApplies(action) || !selected) {
        return false;
      }
      setNotice(
        action.privacyMode === "private" ? "Private conversation created." : "Conversation created."
      );
      return true;
    } catch (caught) {
      if (conversationCreationStillApplies(action)) {
        setError(readError(caught));
        if (operationVersion === navigationVersion.current) {
          await restoreStableSelection(action.token, operationVersion);
        }
      }
      return false;
    } finally {
      finishConversationCreation(action);
    }
  }

  async function saveConversationTitle(titleOverride?: string): Promise<boolean> {
    const titleSnapshot = canonicalConversationTitle(titleOverride ?? conversationTitle);
    if (titleSnapshot === undefined) {
      setError(
        "Keep the conversation title to 200 characters or fewer."
      );
      return false;
    }
    if (activeConversation?.title === titleSnapshot) {
      setError(null);
      setConversationTitle(titleSnapshot ?? "");
      setNotice("Thread title is already saved.");
      return true;
    }
    const action = beginConversationMetadataMutation({ kind: "title", title: titleSnapshot });
    if (!action) {
      return false;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await persistConversationMetadata(action, {
        title: titleSnapshot
      });
      if (!updated || !conversationMetadataMutationStillApplies(action)) {
        return false;
      }
      const ownsActive = conversationMetadataMutationOwnsActive(action);
      mergeVerifiedMetadataSummary(action, updated, ownsActive);
      if (!ownsActive) {
        return true;
      }
      setConversationTitle(updated.title ?? "");
      setNotice("Thread title saved.");
      return true;
    } catch (caught) {
      if (conversationMetadataMutationOwnsActive(action)) {
        setError(readError(caught));
      }
      return false;
    } finally {
      finishConversationMetadataMutation(action);
    }
  }

  async function setActiveConversationPrivacyMode(privacyMode: ConversationPrivacyMode) {
    if (conversationPrivacyMode(activeConversation) === privacyMode) {
      setError(null);
      setNotice(privacyModeNotice(privacyMode));
      return;
    }
    const action = beginConversationMetadataMutation({ kind: "privacy", privacyMode });
    if (!action) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await persistConversationMetadata(action, {
        privacy_mode: privacyMode
      });
      if (!updated || !conversationMetadataMutationStillApplies(action)) {
        return;
      }
      const ownsActive = conversationMetadataMutationOwnsActive(action);
      mergeVerifiedMetadataSummary(action, updated, ownsActive);
      if (!ownsActive) {
        return;
      }
      try {
        await refreshSideState(
          action.token,
          action.characterId,
          action.conversationId,
          () => conversationMetadataMutationOwnsActive(action)
        );
      } catch {
        if (conversationMetadataMutationOwnsActive(action)) {
          setError(
            "Privacy was saved, but the conversation could not refresh. Reload Eidolon before continuing."
          );
        }
      }
      if (conversationMetadataMutationOwnsActive(action)) {
        setNotice(privacyModeNotice(conversationPrivacyMode(updated)));
      }
    } catch (caught) {
      if (conversationMetadataMutationOwnsActive(action)) {
        setError(readError(caught));
      }
    } finally {
      finishConversationMetadataMutation(action);
    }
  }

  async function saveActiveConversationScenario() {
    const normalized = conversationScenarioDraft.trim().replace(/\s+/g, " ");
    if (!normalized) {
      setError("Write a shared scene before saving it.");
      return;
    }
    if (normalized.length > 1200) {
      setError("Keep the shared scene to 1,200 characters or fewer.");
      return;
    }
    await updateActiveConversationScenario({ mode: "custom", text: normalized });
  }

  async function resetActiveConversationScenario() {
    await updateActiveConversationScenario({ mode: "default" });
  }

  async function updateActiveConversationScenario(
    scenario: ConversationScenarioExpectation
  ) {
    const action = beginConversationMetadataMutation({ kind: "scenario", scenario });
    if (!action) {
      return;
    }
    let persisted = false;
    setScenarioSaving(true);
    setError(null);
    try {
      const updated = await persistConversationMetadata(action, {
        scenario
      });
      persisted = true;
      if (!updated || !conversationMetadataMutationStillApplies(action)) {
        return;
      }
      const ownsActive = conversationMetadataMutationOwnsActive(action);
      mergeVerifiedMetadataSummary(action, updated, ownsActive);
      if (!ownsActive) {
        return;
      }
      setConversationScenarioDraft(conversationCustomScenario(updated));
      await refreshSideState(
        action.token,
        action.characterId,
        action.conversationId,
        () => conversationMetadataMutationOwnsActive(action)
      );
      if (conversationMetadataMutationOwnsActive(action)) {
        setNotice(
          scenario.mode === "custom"
            ? "This conversation has a new shared scene."
            : "This conversation has returned to your usual setting."
        );
      }
    } catch (caught) {
      if (!conversationMetadataMutationOwnsActive(action)) {
        return;
      }
      setError(
        persisted
          ? "The shared scene was saved, but the conversation could not refresh."
          : readError(caught)
      );
    } finally {
      finishConversationMetadataMutation(action);
    }
  }

  async function saveCharacter(draftOverride?: CharacterDraft): Promise<boolean> {
    if (!token || !sessionOwnerId || !activeCharacter || characterMutation.current) {
      return false;
    }
    const targetCharacterId = activeCharacter.id;
    const sourceCharacter = activeCharacter;
    const draftSnapshot = draftOverride ?? characterDraft;
    const validationErrors = validateCharacterDraft(draftSnapshot);
    if (Object.keys(validationErrors).length > 0) {
      setError("Review your companion’s profile before saving.");
      return false;
    }
    const payload = characterPayloadFromDraft(
      draftSnapshot,
      sourceCharacter.boundaries_json
    ) as CharacterPayload;
    const action = beginCharacterMutation(
      "save",
      targetCharacterId,
      navigationVersion.current
    );
    if (!action) {
      return false;
    }
    setError(null);
    try {
      const responseValue = await acceptedJsonMutation(
        `/characters/${targetCharacterId}`,
        "PATCH",
        payload,
        action.token
      );
      if (!characterActionStillApplies(action)) {
        return false;
      }

      let updated = ownedCharacter(responseValue, action.ownerUserId);
      if (
        !updated ||
        updated.id !== targetCharacterId ||
        !characterMatchesPayload(updated, payload)
      ) {
        let canonicalValue: unknown;
        try {
          canonicalValue = await apiJson<unknown>(`/characters/${targetCharacterId}`, {
            token: action.token
          });
        } catch {
          if (
            characterActionStillApplies(action) &&
            activeCharacterIdRef.current === targetCharacterId
          ) {
            setError(
              "Your companion may have been saved, but the change could not be confirmed. Everything you wrote is still here."
            );
          }
          return false;
        }
        if (!characterActionStillApplies(action)) {
          return false;
        }
        updated = ownedCharacter(canonicalValue, action.ownerUserId);
        if (
          !updated ||
          updated.id !== targetCharacterId ||
          !characterMatchesPayload(updated, payload)
        ) {
          if (activeCharacterIdRef.current === targetCharacterId) {
            setError(
              "Your companion may have been saved, but the returned profile did not match. Everything you wrote is still here."
            );
          }
          return false;
        }
      }

      if (!characterActionStillApplies(action)) {
        return false;
      }
      if (stableNavigation.current?.character.id === updated.id) {
        stableNavigation.current = {
          ...stableNavigation.current,
          character: updated
        };
      }
      mergeCharacterSummary(updated);

      if (activeCharacterIdRef.current !== targetCharacterId) {
        return false;
      }
      setCurrentCharacter(updated);
      const targetConversation = activeConversationRef.current;
      if (targetConversation?.character_id === targetCharacterId) {
        const refreshNavigationVersion = navigationVersion.current;
        const shouldApply = () =>
          characterActionStillApplies(action) &&
          refreshNavigationVersion === navigationVersion.current &&
          activeCharacterIdRef.current === targetCharacterId &&
          activeConversationRef.current?.id === targetConversation.id;
        try {
          await refreshSideState(
            action.token,
            updated.id,
            targetConversation.id,
            shouldApply
          );
        } catch {
          if (shouldApply()) {
            setError(
              "Your companion was saved, but consent readiness could not refresh. Reload Eidolon before changing the conversation tone."
            );
            return false;
          }
        }
      }
      if (
        characterActionStillApplies(action) &&
        activeCharacterIdRef.current === targetCharacterId
      ) {
        setNotice("Your companion has been updated.");
      }
      return true;
    } catch (caught) {
      if (
        characterActionStillApplies(action) &&
        activeCharacterIdRef.current === targetCharacterId
      ) {
        setError(readError(caught));
      }
      return false;
    } finally {
      finishCharacterMutation(action);
    }
  }

  async function searchMessages(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = searchQueryRef.current.trim();
    if (!token || !activeConversation || !query) {
      setSearchResults([]);
      setSearchStatus("idle");
      setSearchError(null);
      return;
    }
    if (query.length > 120) {
      setSearchResults([]);
      setSearchStatus("error");
      setSearchError("Keep searches to 120 characters or fewer.");
      return;
    }
    if (searchRequestInFlight.current) {
      return;
    }
    const request: SearchRequest = {
      conversationId: activeConversation.id,
      navigationVersion: navigationVersion.current,
      query
    };
    const shouldApply = () =>
      searchRequestInFlight.current === request &&
      navigationVersion.current === request.navigationVersion &&
      activeConversation?.id === request.conversationId &&
      searchQueryRef.current.trim() === request.query;
    searchRequestInFlight.current = request;
    setSearchResults([]);
    setSearchStatus("loading");
    setSearchError(null);
    try {
      const result = await apiJson<unknown>(
        `/conversations/${request.conversationId}/search?q=${encodeURIComponent(request.query)}`,
        { token }
      );
      if (!shouldApply()) {
        return;
      }
      const messages = completeMessageList(result, request.conversationId);
      if (!messages) {
        throw new Error("Search returned an unreadable response. Try again.");
      }
      setSearchResults(messages);
      setSearchStatus("ready");
    } catch (caught) {
      if (shouldApply()) {
        setSearchResults([]);
        setSearchStatus("error");
        setSearchError(readError(caught));
      }
    } finally {
      if (searchRequestInFlight.current === request) {
        searchRequestInFlight.current = null;
      }
    }
  }

  async function deleteActiveConversation(): Promise<boolean> {
    const targetConversation = activeConversationRef.current;
    const targetCharacter =
      activeCharacter?.id === targetConversation?.character_id
        ? activeCharacter
        : characters.find(
            (character) => character.id === targetConversation?.character_id
          );
    if (!targetConversation || !targetCharacter) {
      setError("Choose a conversation before deleting it.");
      return false;
    }
    const operationVersion = navigationVersion.current + 1;
    const action = beginConversationDeletion(
      targetConversation,
      targetCharacter,
      operationVersion
    );
    if (!action) {
      return false;
    }
    navigationVersion.current = operationVersion;
    setError(null);
    try {
      const responseValue = await acceptedDeleteMutation(
        `/conversations/${action.conversation.id}`,
        action.token
      );
      if (!conversationDeletionStillApplies(action)) {
        return false;
      }

      let canonicalConversations: Conversation[] | null = null;
      try {
        const listValue = await apiJson<unknown>("/conversations", {
          token: action.token
        });
        if (!conversationDeletionStillApplies(action)) {
          return false;
        }
        canonicalConversations = ownedConversationList(
          listValue,
          action.ownerUserId
        );
        if (!canonicalConversations) {
          throw new Error("Your remaining conversations could not be opened safely.");
        }
      } catch (caught) {
        if (!conversationDeletionStillApplies(action)) {
          return false;
        }
        if (!hasPositiveDeleteCount(responseValue)) {
          if (conversationDeletionOwnsNavigation(action)) {
            setError(
              "The conversation may have been deleted, but the change could not be confirmed. Reload Eidolon before trying again."
            );
          }
          return false;
        }
        applyLocallyDeletedConversation(action);
        if (conversationDeletionOwnsNavigation(action)) {
          setError(
            "The conversation was deleted, but the rest of your history could not refresh. Reload Eidolon to continue."
          );
        }
        return true;
      }

      if (
        canonicalConversations.some(
          (conversation) => conversation.id === action.conversation.id
        )
      ) {
        if (conversationDeletionOwnsNavigation(action)) {
          setError(
            hasPositiveDeleteCount(responseValue)
              ? "The conversation could not be confirmed as deleted, so it remains visible."
              : "The conversation was not deleted. Your confirmation is still ready so you can try again."
          );
        }
        return false;
      }

      applyCanonicalDeletion(action, canonicalConversations);
      if (action.navigationVersion !== navigationVersion.current) {
        return true;
      }

      const sibling = canonicalConversations.find(
        (conversation) => conversation.character_id === action.character.id
      );
      if (sibling) {
        const selected = await selectConversation(
          sibling,
          action.character,
          action.navigationVersion
        );
        if (conversationDeletionStillApplies(action) && selected) {
          setNotice("Thread deleted. Another room is open.");
        }
        return true;
      }

      const freshConversation = await createReplacementConversation(
        action,
        canonicalConversations
      );
      if (
        !freshConversation ||
        !conversationDeletionStillApplies(action) ||
        action.navigationVersion !== navigationVersion.current
      ) {
        return true;
      }
      const selected = await selectConversation(
        freshConversation,
        action.character,
        action.navigationVersion
      );
      if (conversationDeletionStillApplies(action) && selected) {
        setNotice("Thread deleted. A fresh room is open.");
      }
      return true;
    } catch (caught) {
      if (conversationDeletionOwnsNavigation(action)) {
        setError(readError(caught));
      }
      return false;
    } finally {
      finishConversationDeletion(action);
    }
  }

  async function createReplacementConversation(
    action: ConversationDeletion,
    canonicalConversations: Conversation[]
  ): Promise<Conversation | null> {
    const knownConversationIds = new Set(
      canonicalConversations.map((conversation) => conversation.id)
    );
    let responseValue: unknown;
    try {
      responseValue = await acceptedJsonMutation(
        "/conversations",
        "POST",
        {
          character_id: action.character.id,
          privacy_mode: "normal"
        },
        action.token
      );
    } catch (caught) {
      if (conversationDeletionOwnsNavigation(action)) {
        setError(
          `The thread was deleted, but a fresh room could not be opened. ${readError(caught)}`
        );
      }
      return null;
    }
    if (!conversationDeletionStillApplies(action)) {
      return null;
    }

    let created = ownedConversation(responseValue, action.ownerUserId);
    if (
      created &&
      !knownConversationIds.has(created.id) &&
      conversationMatchesCreation(created, action.character.id, "normal")
    ) {
      mergeConversationSummary(created);
      return created;
    }

    let listValue: unknown;
    try {
      listValue = await apiJson<unknown>("/conversations", {
        token: action.token
      });
    } catch {
      if (conversationDeletionOwnsNavigation(action)) {
        setError(
          "The conversation was deleted and a fresh one may have opened, but the change could not be confirmed. Reload Eidolon before creating another."
        );
      }
      return null;
    }
    if (!conversationDeletionStillApplies(action)) {
      return null;
    }
    const recovered = recoveredCreatedConversation({
      value: listValue,
      ownerUserId: action.ownerUserId,
      characterId: action.character.id,
      privacyMode: "normal",
      knownConversationIds,
      responseId: possibleConversationId(responseValue)
    });
    if (!recovered) {
      if (conversationDeletionOwnsNavigation(action)) {
        setError(
          "The conversation was deleted, but your history could not confirm the fresh conversation. Reload Eidolon before creating another."
        );
      }
      return null;
    }
    created = recovered.conversation;
    syncConversationSummaries(recovered.conversations);
    return created;
  }

  function applyCanonicalDeletion(
    action: ConversationDeletion,
    canonicalConversations: Conversation[]
  ) {
    syncConversationSummaries(canonicalConversations);
    if (stableNavigation.current?.conversation.id === action.conversation.id) {
      stableNavigation.current = null;
    }
    if (activeConversationRef.current?.id !== action.conversation.id) {
      return;
    }
    setActiveConversation(null);
    setConversationSwitchingId(null);
    setConversationTitle("");
    setConversationScenarioDraft("");
    clearSearchState();
  }

  function applyLocallyDeletedConversation(action: ConversationDeletion) {
    setConversations((current) =>
      current.filter((conversation) => conversation.id !== action.conversation.id)
    );
    if (stableNavigation.current?.conversation.id === action.conversation.id) {
      stableNavigation.current = null;
    }
    if (activeConversationRef.current?.id !== action.conversation.id) {
      return;
    }
    setActiveConversation(null);
    setConversationTitle("");
    setConversationScenarioDraft("");
    clearSearchState();
  }

  function beginConversationMetadataMutation(
    intent: ConversationMetadataIntent
  ): ConversationMetadataMutation | null {
    const conversation = activeConversationRef.current;
    if (
      !token ||
      !sessionOwnerId ||
      sessionOwnerIdRef.current !== sessionOwnerId ||
      !conversation ||
      conversation.user_id !== sessionOwnerId ||
      characterMutation.current ||
      conversationCreation.current ||
      conversationProvision.current ||
      conversationDeletion.current ||
      conversationMetadataMutation.current
    ) {
      return null;
    }
    const mutation: ConversationMetadataMutation = {
      id: ++nextConversationMetadataMutationId.current,
      ownerUserId: sessionOwnerId,
      token,
      sessionGeneration: sessionGeneration.current,
      navigationVersion: navigationVersion.current,
      conversationId: conversation.id,
      characterId: conversation.character_id,
      intent
    };
    conversationMetadataMutation.current = mutation;
    return mutation;
  }

  function conversationMetadataMutationStillApplies(
    mutation: ConversationMetadataMutation
  ): boolean {
    return (
      conversationMetadataMutation.current === mutation &&
      sessionGeneration.current === mutation.sessionGeneration &&
      sessionOwnerIdRef.current === mutation.ownerUserId
    );
  }

  function conversationMetadataMutationOwnsActive(
    mutation: ConversationMetadataMutation
  ): boolean {
    return (
      conversationMetadataMutationStillApplies(mutation) &&
      (activeConversationRef.current?.id === mutation.conversationId ||
        stableNavigation.current?.conversation.id === mutation.conversationId)
    );
  }

  async function persistConversationMetadata(
    mutation: ConversationMetadataMutation,
    payload: unknown
  ): Promise<Conversation | null> {
    const path = `/conversations/${mutation.conversationId}`;
    const responseValue = await acceptedJsonMutation(
      path,
      "PATCH",
      payload,
      mutation.token
    );
    if (!conversationMetadataMutationStillApplies(mutation)) {
      return null;
    }
    let updated = ownedConversation(responseValue, mutation.ownerUserId);
    if (
      !updated ||
      updated.id !== mutation.conversationId ||
      !conversationMatchesMetadataIntent(updated, mutation.intent)
    ) {
      let canonicalValue: unknown;
      try {
        canonicalValue = await apiJson<unknown>("/conversations", {
          token: mutation.token
        });
      } catch {
        throw new Error(metadataVerificationError(mutation.intent));
      }
      if (!conversationMetadataMutationStillApplies(mutation)) {
        return null;
      }
      const canonicalConversations = ownedConversationList(
        canonicalValue,
        mutation.ownerUserId
      );
      updated =
        canonicalConversations?.find(
          (conversation) => conversation.id === mutation.conversationId
        ) ?? null;
      if (
        !updated ||
        updated.id !== mutation.conversationId ||
        !conversationMatchesMetadataIntent(updated, mutation.intent)
      ) {
        throw new Error(metadataVerificationError(mutation.intent));
      }
    }
    return updated;
  }

  function mergeVerifiedMetadataSummary(
    mutation: ConversationMetadataMutation,
    updated: Conversation,
    ownsActive: boolean
  ) {
    setConversations((current) =>
      current.map((conversation) =>
        conversation.id === mutation.conversationId ? updated : conversation
      )
    );
    if (stableNavigation.current?.conversation.id === mutation.conversationId) {
      stableNavigation.current = {
        ...stableNavigation.current,
        conversation: updated,
        title: updated.title ?? ""
      };
    }
    if (ownsActive) {
      setActiveConversation(updated);
    }
  }

  function finishConversationMetadataMutation(mutation: ConversationMetadataMutation) {
    if (!conversationMetadataMutationStillApplies(mutation)) {
      return;
    }
    conversationMetadataMutation.current = null;
    if (mutation.intent.kind === "scenario") {
      setScenarioSaving(false);
    } else {
      setBusy(false);
    }
  }

  function beginCharacterMutation(
    actionId: CharacterActionId,
    characterId: string | null,
    operationNavigationVersion: number
  ): CharacterMutation | null {
    if (
      !token ||
      !sessionOwnerId ||
      sessionOwnerIdRef.current !== sessionOwnerId ||
      characterMutation.current ||
      conversationCreation.current ||
      conversationProvision.current ||
      conversationDeletion.current ||
      conversationMetadataMutation.current
    ) {
      return null;
    }
    const mutation: CharacterMutation = {
      id: ++nextCharacterMutationId.current,
      actionId,
      ownerUserId: sessionOwnerId,
      token,
      sessionGeneration: sessionGeneration.current,
      navigationVersion: operationNavigationVersion,
      characterId
    };
    characterMutation.current = mutation;
    setCharacterActionId(actionId);
    return mutation;
  }

  function characterActionStillApplies(mutation: CharacterMutation): boolean {
    return (
      characterMutation.current === mutation &&
      sessionGeneration.current === mutation.sessionGeneration &&
      sessionOwnerIdRef.current === mutation.ownerUserId
    );
  }

  function finishCharacterMutation(mutation: CharacterMutation) {
    if (!characterActionStillApplies(mutation)) {
      return;
    }
    characterMutation.current = null;
    setCharacterActionId(null);
  }

  function beginConversationCreation(
    character: Character,
    privacyMode: ConversationPrivacyMode,
    operationNavigationVersion: number
  ): ConversationCreation | null {
    if (
      !token ||
      !sessionOwnerId ||
      sessionOwnerIdRef.current !== sessionOwnerId ||
      characterMutation.current ||
      conversationCreation.current ||
      conversationProvision.current ||
      conversationDeletion.current ||
      conversationMetadataMutation.current
    ) {
      return null;
    }
    const action: ConversationCreation = {
      id: ++nextConversationCreationId.current,
      ownerUserId: sessionOwnerId,
      token,
      sessionGeneration: sessionGeneration.current,
      navigationVersion: operationNavigationVersion,
      character,
      privacyMode
    };
    conversationCreation.current = action;
    setConversationCreationMode(privacyMode);
    return action;
  }

  function conversationCreationStillApplies(action: ConversationCreation): boolean {
    return (
      conversationCreation.current === action &&
      sessionGeneration.current === action.sessionGeneration &&
      sessionOwnerIdRef.current === action.ownerUserId
    );
  }

  function finishConversationCreation(action: ConversationCreation) {
    if (!conversationCreationStillApplies(action)) {
      return;
    }
    conversationCreation.current = null;
    setConversationCreationMode(null);
  }

  function beginConversationProvision(
    character: Character,
    operationNavigationVersion: number,
    parentCharacterMutation: CharacterMutation | null
  ): ConversationProvision | null {
    const parentOwnsCharacterMutation =
      parentCharacterMutation !== null &&
      characterActionStillApplies(parentCharacterMutation);
    if (
      !token ||
      !sessionOwnerId ||
      sessionOwnerIdRef.current !== sessionOwnerId ||
      conversationCreation.current ||
      conversationProvision.current ||
      conversationDeletion.current ||
      conversationMetadataMutation.current ||
      (parentCharacterMutation !== null && !parentOwnsCharacterMutation) ||
      (characterMutation.current !== null && !parentOwnsCharacterMutation)
    ) {
      return null;
    }
    const action: ConversationProvision = {
      id: ++nextConversationProvisionId.current,
      ownerUserId: sessionOwnerId,
      token: parentCharacterMutation?.token ?? token,
      sessionGeneration: sessionGeneration.current,
      navigationVersion: operationNavigationVersion,
      character,
      parentCharacterMutationId: parentCharacterMutation?.id ?? null
    };
    conversationProvision.current = action;
    setProvisioningCharacterId(character.id);
    return action;
  }

  function conversationProvisionStillApplies(action: ConversationProvision): boolean {
    if (
      conversationProvision.current !== action ||
      sessionGeneration.current !== action.sessionGeneration ||
      sessionOwnerIdRef.current !== action.ownerUserId
    ) {
      return false;
    }
    return (
      action.parentCharacterMutationId === null ||
      characterMutation.current?.id === action.parentCharacterMutationId
    );
  }

  function finishConversationProvision(action: ConversationProvision) {
    if (!conversationProvisionStillApplies(action)) {
      return;
    }
    conversationProvision.current = null;
    setProvisioningCharacterId(null);
  }

  function beginConversationDeletion(
    conversation: Conversation,
    character: Character,
    operationNavigationVersion: number
  ): ConversationDeletion | null {
    if (
      !token ||
      !sessionOwnerId ||
      sessionOwnerIdRef.current !== sessionOwnerId ||
      characterMutation.current ||
      conversationCreation.current ||
      conversationProvision.current ||
      conversationDeletion.current ||
      conversationMetadataMutation.current ||
      activeConversationRef.current?.id !== conversation.id
    ) {
      return null;
    }
    const action: ConversationDeletion = {
      id: ++nextConversationDeletionId.current,
      ownerUserId: sessionOwnerId,
      token,
      sessionGeneration: sessionGeneration.current,
      navigationVersion: operationNavigationVersion,
      conversation,
      character
    };
    conversationDeletion.current = action;
    setDeletingConversationId(conversation.id);
    return action;
  }

  function conversationDeletionStillApplies(action: ConversationDeletion): boolean {
    return (
      conversationDeletion.current === action &&
      sessionGeneration.current === action.sessionGeneration &&
      sessionOwnerIdRef.current === action.ownerUserId
    );
  }

  function conversationDeletionOwnsNavigation(action: ConversationDeletion): boolean {
    return (
      conversationDeletionStillApplies(action) &&
      navigationVersion.current === action.navigationVersion &&
      activeConversationRef.current?.id === action.conversation.id
    );
  }

  function finishConversationDeletion(action: ConversationDeletion) {
    if (!conversationDeletionStillApplies(action)) {
      return;
    }
    conversationDeletion.current = null;
    setDeletingConversationId(null);
  }

  function invalidateSessionMutations() {
    sessionGeneration.current += 1;
    characterMutation.current = null;
    conversationCreation.current = null;
    conversationProvision.current = null;
    conversationDeletion.current = null;
    conversationMetadataMutation.current = null;
    setCharacterActionId(null);
    setConversationCreationMode(null);
    setProvisioningCharacterId(null);
    setDeletingConversationId(null);
    setScenarioSaving(false);
  }

  function resetNavigation() {
    navigationVersion.current += 1;
    invalidateSessionMutations();
    stableNavigation.current = null;
    setCharacters([]);
    setConversations([]);
    setActiveConversation(null);
    setConversationSwitchingId(null);
    setConversationTitle("");
    setConversationScenarioDraft("");
    setScenarioSaving(false);
    clearCurrentCharacter();
    clearSearchState();
  }

  function updateSearchQuery(value: string) {
    searchRequestInFlight.current = null;
    searchQueryRef.current = value;
    setSearchQuery(value);
    setSearchResults([]);
    setSearchStatus("idle");
    setSearchError(null);
  }

  function clearSearchState() {
    searchRequestInFlight.current = null;
    searchQueryRef.current = "";
    setSearchQuery("");
    setSearchResults([]);
    setSearchStatus("idle");
    setSearchError(null);
  }

  function syncConversationSummaries(nextConversations: Conversation[]) {
    setConversations(nextConversations);
    const stable = stableNavigation.current;
    if (stable) {
      const summary = nextConversations.find(
        (conversation) => conversation.id === stable.conversation.id
      );
      if (summary) {
        stableNavigation.current = {
          ...stable,
          conversation: summary,
          title: summary.title ?? ""
        };
      }
    }
    setActiveConversation((current) => {
      if (!current) {
        return current;
      }
      return (
        nextConversations.find((conversation) => conversation.id === current.id) ?? current
      );
    });
  }

  function mergeConversationSummary(nextConversation: Conversation) {
    setConversations((current) => {
      const existing = current.find(
        (conversation) => conversation.id === nextConversation.id
      );
      if (!existing) {
        return [nextConversation, ...current];
      }
      return current.map((conversation) =>
        conversation.id === nextConversation.id
          ? (advancedConversationSummary(conversation, nextConversation) ?? conversation)
          : conversation
      );
    });
    setActiveConversation((current) => {
      if (current?.id !== nextConversation.id) {
        return current;
      }
      return advancedConversationSummary(current, nextConversation) ?? current;
    });
    if (stableNavigation.current?.conversation.id === nextConversation.id) {
      const merged = advancedConversationSummary(
        stableNavigation.current.conversation,
        nextConversation
      );
      if (!merged) {
        return;
      }
      stableNavigation.current = {
        ...stableNavigation.current,
        conversation: merged,
        title: merged.title ?? ""
      };
    }
  }

  function mergeConversationSummaries(nextConversations: Conversation[]) {
    const incoming = new Map(
      nextConversations.map((conversation) => [conversation.id, conversation])
    );
    setConversations((current) => {
      const currentIds = new Set(current.map((conversation) => conversation.id));
      const merged = current.map((conversation) => {
        const next = incoming.get(conversation.id);
        return next
          ? (advancedConversationSummary(conversation, next) ?? conversation)
          : conversation;
      });
      for (const next of nextConversations) {
        if (!currentIds.has(next.id)) {
          merged.push(next);
        }
      }
      return merged.sort(
        (left, right) => conversationActivity(right) - conversationActivity(left)
      );
    });
    const active = activeConversationRef.current;
    if (active) {
      const next = incoming.get(active.id);
      if (next) {
        const merged = advancedConversationSummary(active, next);
        if (merged) {
          activeConversationRef.current = merged;
          setActiveConversation(merged);
        }
      }
    }
    const stable = stableNavigation.current;
    if (stable) {
      const next = incoming.get(stable.conversation.id);
      const merged = next
        ? advancedConversationSummary(stable.conversation, next)
        : null;
      if (merged) {
        stableNavigation.current = {
          ...stable,
          conversation: merged,
          title: merged.title ?? ""
        };
      }
    }
  }

  function mergeCharacterSummary(nextCharacter: Character) {
    setCharacters((current) => {
      const exists = current.some((character) => character.id === nextCharacter.id);
      if (!exists) {
        return [...current, nextCharacter];
      }
      return current.map((character) =>
        character.id === nextCharacter.id ? nextCharacter : character
      );
    });
  }

  function setCurrentCharacter(character: Character) {
    if (activeCharacterIdRef.current !== character.id) {
      activeCharacterIdRef.current = character.id;
      onActiveCharacterChange(character.id);
    }
    setActiveCharacter(character);
    setCharacterDraft(toCharacterDraft(character));
  }

  function clearCurrentCharacter() {
    if (activeCharacterIdRef.current !== null) {
      activeCharacterIdRef.current = null;
      onActiveCharacterChange(null);
    }
    setActiveCharacter(null);
    setCharacterDraft(emptyCharacterDraft());
  }

  async function restoreStableSelection(
    authToken: string,
    expectedVersion: number
  ): Promise<void> {
    if (expectedVersion !== navigationVersion.current) {
      return;
    }
    const fallback = stableNavigation.current;
    setActiveConversation(fallback?.conversation ?? null);
    setConversationTitle(fallback?.title ?? "");
    setConversationScenarioDraft(conversationCustomScenario(fallback?.conversation ?? null));
    if (!fallback) {
      clearCurrentCharacter();
      return;
    }
    setCurrentCharacter(fallback.character);
    await refreshSideState(
      authToken,
      fallback.character.id,
      fallback.conversation.id,
      () => expectedVersion === navigationVersion.current
    ).catch(() => undefined);
  }

  return {
    state: {
      characters,
      activeCharacter,
      activeCharacterId,
      characterDraft,
      characterActionId,
      characterMutating: characterActionId !== null,
      conversations,
      activeConversation,
      conversationSwitchingId,
      conversationCreationMode,
      conversationCreating: conversationCreationMode !== null,
      provisioningCharacterId,
      conversationProvisioning: provisioningCharacterId !== null,
      deletingConversationId,
      conversationDeleting: deletingConversationId !== null,
      conversationTitle,
      conversationScenarioDraft,
      scenarioSaving,
      searchQuery,
      searchResults,
      searchStatus,
      searchError
    },
    actions: {
      setCharacters,
      setConversations,
      setCharacterDraft,
      setConversationTitle,
      setConversationScenarioDraft,
      setSearchQuery: updateSearchQuery,
      hydrateNavigation,
      reloadCharacters,
      reloadConversations,
      selectCharacter,
      createCharacter,
      selectConversation,
      createConversationForCurrentCharacter,
      saveConversationTitle,
      setActiveConversationPrivacyMode,
      saveActiveConversationScenario,
      resetActiveConversationScenario,
      saveCharacter,
      searchMessages,
      deleteActiveConversation,
      syncConversationSummaries,
      mergeConversationSummaries,
      mergeConversationSummary,
      resetNavigation
    }
  };
}

function conversationActivity(conversation: Conversation): number {
  return Date.parse(conversation.last_message_at ?? conversation.updated_at);
}

function conversationMatchesMetadataIntent(
  conversation: Conversation,
  intent: ConversationMetadataIntent
): boolean {
  if (intent.kind === "title") {
    return conversationMatchesTitle(conversation, intent.title);
  }
  if (intent.kind === "privacy") {
    return conversationMatchesPrivacy(conversation, intent.privacyMode);
  }
  return conversationMatchesScenario(conversation, intent.scenario);
}

function metadataVerificationError(intent: ConversationMetadataIntent): string {
  if (intent.kind === "title") {
    return "The title may have been saved, but the change could not be confirmed. Reload Eidolon before saving it again.";
  }
  if (intent.kind === "privacy") {
    return "The privacy setting may have been saved, but the change could not be confirmed. Reload Eidolon before changing it again.";
  }
  return "The shared scene may have been saved, but the change could not be confirmed. Your words are still here.";
}

function privacyModeNotice(privacyMode: ConversationPrivacyMode): string {
  return privacyMode === "private"
    ? "This conversation is private. Memory, moments, bond changes, and companion notes are paused here."
    : "Shared memory is available again for this conversation.";
}

async function acceptedJsonMutation(
  path: string,
  method: "POST" | "PATCH",
  payload: unknown,
  token: string
): Promise<unknown> {
  const response = await apiFetch(path, {
    method,
    body: JSON.stringify(payload),
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json"
    }
  });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, path);
  }
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function acceptedDeleteMutation(path: string, token: string): Promise<unknown> {
  const response = await apiFetch(path, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, path);
  }
  try {
    return await response.json();
  } catch {
    return null;
  }
}
