"use client";

import { FormEvent, useState } from "react";

import { apiJson } from "@/lib/api";

import { emptyCharacterDraft, readError, toCharacterDraft } from "./controller-utils";
import type { Character, CharacterDraft, Conversation, Message } from "./types";

type UseNavigationControllerArgs = {
  token: string | null;
  setBusy: (value: boolean) => void;
  setError: (value: string | null) => void;
  setNotice: (value: string | null) => void;
  loadConversation: (authToken: string, conversationId: string) => Promise<void>;
  refreshSideState: (
    authToken: string,
    characterId: string,
    conversationId: string
  ) => Promise<void>;
};

type BootstrapNavigationArgs = {
  authToken: string;
  characters: Character[];
  conversations: Conversation[];
  conversation: Conversation;
  character: Character;
};

export function useNavigationController({
  token,
  setBusy,
  setError,
  setNotice,
  loadConversation,
  refreshSideState
}: UseNavigationControllerArgs) {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [activeCharacter, setActiveCharacter] = useState<Character | null>(null);
  const [newCharacterName, setNewCharacterName] = useState("");
  const [characterDraft, setCharacterDraft] = useState<CharacterDraft>(emptyCharacterDraft());

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [conversationTitle, setConversationTitle] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Message[]>([]);

  const activeCharacterId = activeCharacter?.id ?? activeConversation?.character_id ?? null;

  async function hydrateNavigation({
    authToken,
    characters: nextCharacters,
    conversations: nextConversations,
    conversation,
    character
  }: BootstrapNavigationArgs) {
    setCharacters(nextCharacters);
    setConversations(nextConversations);
    setActiveConversation(conversation);
    setConversationTitle(conversation.title ?? "");
    setCurrentCharacter(character);
    await loadConversation(authToken, conversation.id);
    await refreshSideState(authToken, character.id, conversation.id);
  }

  async function reloadCharacters(authToken: string) {
    const characterList = await apiJson<Character[]>("/characters", { token: authToken });
    setCharacters(characterList);
    return characterList;
  }

  async function reloadConversations(authToken: string) {
    const conversationList = await apiJson<Conversation[]>("/conversations", {
      token: authToken
    });
    setConversations(conversationList);
    return conversationList;
  }

  async function selectCharacter(character: Character) {
    if (!token) {
      return;
    }
    setError(null);
    setCurrentCharacter(character);
    const conversationList = await reloadConversations(token);
    const characterConversation =
      conversationList.find((conversation) => conversation.character_id === character.id) ??
      (await apiJson<Conversation>("/conversations", {
        method: "POST",
        body: JSON.stringify({ character_id: character.id }),
        token
      }));
    await selectConversation(characterConversation, character);
  }

  async function createCharacter() {
    if (!token) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const name = newCharacterName.trim() || "New Eidolon";
      const created = await apiJson<Character>("/characters", {
        method: "POST",
        body: JSON.stringify({
          name,
          description: "A private text-only companion with continuity and memory.",
          personality_core: "Attentive, grounded, curious, and emotionally consistent.",
          speech_style: "Warm, specific, and concise.",
          boundaries_json: { default: "SFW unless structural adult gates pass" }
        }),
        token
      });
      setNewCharacterName("");
      await reloadCharacters(token);
      await selectCharacter(created);
      setNotice("Character created.");
    } catch (caught) {
      setError(readError(caught));
    } finally {
      setBusy(false);
    }
  }

  async function selectConversation(conversation: Conversation, knownCharacter?: Character) {
    if (!token) {
      return;
    }
    setActiveConversation(conversation);
    setConversationTitle(conversation.title ?? "");
    setError(null);
    const character =
      knownCharacter ??
      characters.find((item) => item.id === conversation.character_id) ??
      (await apiJson<Character>(`/characters/${conversation.character_id}`, { token }));
    setCurrentCharacter(character);
    await refreshSideState(token, character.id, conversation.id);
  }

  async function createConversationForCurrentCharacter() {
    if (!token) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await apiJson<Conversation>("/conversations", {
        method: "POST",
        body: JSON.stringify({ character_id: activeCharacterId }),
        token
      });
      await reloadConversations(token);
      await selectConversation(created, activeCharacter ?? undefined);
      setNotice("Conversation created.");
    } catch (caught) {
      setError(readError(caught));
    } finally {
      setBusy(false);
    }
  }

  async function saveConversationTitle() {
    if (!token || !activeConversation) {
      return;
    }
    const updated = await apiJson<Conversation>(`/conversations/${activeConversation.id}`, {
      method: "PATCH",
      body: JSON.stringify({ title: conversationTitle.trim() || null }),
      token
    });
    setActiveConversation(updated);
    setConversationTitle(updated.title ?? "");
    setConversations((current) =>
      current.map((conversation) => (conversation.id === updated.id ? updated : conversation))
    );
    setNotice("Thread title saved.");
  }

  async function saveCharacter() {
    if (!token || !activeCharacter) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await apiJson<Character>(`/characters/${activeCharacter.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: characterDraft.name,
          description: characterDraft.description,
          personality_core: characterDraft.personality_core,
          speech_style: characterDraft.speech_style,
          explicit_age: characterDraft.explicit_age
            ? Number.parseInt(characterDraft.explicit_age, 10)
            : null,
          adult_mode_allowed: characterDraft.adult_mode_allowed,
          content_intensity: Number.parseInt(characterDraft.content_intensity || "0", 10)
        }),
        token
      });
      setCurrentCharacter(updated);
      setCharacters((current) =>
        current.map((character) => (character.id === updated.id ? updated : character))
      );
      if (activeConversation) {
        await refreshSideState(token, updated.id, activeConversation.id);
      }
      setNotice("Character saved.");
    } catch (caught) {
      setError(readError(caught));
    } finally {
      setBusy(false);
    }
  }

  async function searchMessages(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !activeConversation || !searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const result = await apiJson<Message[]>(
      `/conversations/${activeConversation.id}/search?q=${encodeURIComponent(searchQuery.trim())}`,
      { token }
    );
    setSearchResults(result);
  }

  async function deleteActiveConversation() {
    if (!token || !activeConversation) {
      return;
    }
    await apiJson<{ deleted: number }>(`/conversations/${activeConversation.id}`, {
      method: "DELETE",
      token
    });
    const conversationList = await reloadConversations(token);
    if (conversationList.length === 0) {
      await createConversationForCurrentCharacter();
      return;
    }
    await selectConversation(conversationList[0]);
  }

  function resetNavigation() {
    setCharacters([]);
    setConversations([]);
    setActiveConversation(null);
    setConversationTitle("");
    setActiveCharacter(null);
    setCharacterDraft(emptyCharacterDraft());
    setNewCharacterName("");
    setSearchQuery("");
    setSearchResults([]);
  }

  function setCurrentCharacter(character: Character) {
    setActiveCharacter(character);
    setCharacterDraft(toCharacterDraft(character));
  }

  return {
    state: {
      characters,
      activeCharacter,
      activeCharacterId,
      newCharacterName,
      characterDraft,
      conversations,
      activeConversation,
      conversationTitle,
      searchQuery,
      searchResults
    },
    actions: {
      setCharacters,
      setConversations,
      setNewCharacterName,
      setCharacterDraft,
      setConversationTitle,
      setSearchQuery,
      hydrateNavigation,
      reloadCharacters,
      reloadConversations,
      selectCharacter,
      createCharacter,
      selectConversation,
      createConversationForCurrentCharacter,
      saveConversationTitle,
      saveCharacter,
      searchMessages,
      deleteActiveConversation,
      resetNavigation
    }
  };
}
