"use client";

import { type FormEvent, useCallback, useState } from "react";

import { CharacterCreationDialog } from "./character-creation-dialog";
import { conversationPrivacyMode } from "./controller-utils";
import type {
  Character,
  CharacterCreationResult,
  CharacterDraft,
  Conversation,
  Message,
  SearchStatus
} from "./types";
import type { ConversationPrivacyMode } from "./types";
import {
  EmptyState,
  errorClass,
  formatTimestamp,
  inputClass,
  secondaryButtonClass
} from "./ui";

export function WorkspaceRail({
  characters,
  activeCharacter,
  activeConversation,
  conversations,
  searchQuery,
  setSearchQuery,
  searchResults,
  searchStatus,
  searchError,
  conversationCreationMode,
  provisioningCharacterId,
  mutationBusy,
  onCreateCharacter,
  onSelectCharacter,
  onCreateConversation,
  onSearch,
  onSelectSearchResult,
  onSelectConversation
}: {
  characters: Character[];
  activeCharacter: Character | null;
  activeConversation: Conversation | null;
  conversations: Conversation[];
  searchQuery: string;
  setSearchQuery: (value: string) => void;
  searchResults: Message[];
  searchStatus: SearchStatus;
  searchError: string | null;
  conversationCreationMode: ConversationPrivacyMode | null;
  provisioningCharacterId: string | null;
  mutationBusy: boolean;
  onCreateCharacter: (draft: CharacterDraft) => Promise<CharacterCreationResult>;
  onSelectCharacter: (character: Character) => void;
  onCreateConversation: (privacyMode?: ConversationPrivacyMode) => void;
  onSearch: (event: FormEvent<HTMLFormElement>) => void;
  onSelectSearchResult: (message: Message) => void;
  onSelectConversation: (conversation: Conversation) => void;
}) {
  const [builderOpen, setBuilderOpen] = useState(false);
  const closeBuilder = useCallback(() => setBuilderOpen(false), []);
  const conversationCounts = conversations.reduce<Record<string, number>>((counts, conversation) => {
    counts[conversation.character_id] = (counts[conversation.character_id] ?? 0) + 1;
    return counts;
  }, {});
  const unreadCounts = conversations.reduce<Record<string, number>>((counts, conversation) => {
    counts[conversation.character_id] =
      (counts[conversation.character_id] ?? 0) + conversation.unread_count;
    return counts;
  }, {});
  const sortedCharacters = [...characters].sort(
    (left, right) =>
      Number(activeCharacter?.id === right.id) - Number(activeCharacter?.id === left.id) ||
      left.name.localeCompare(right.name)
  );
  const characterConversations = conversations.filter(
    (conversation) => conversation.character_id === activeCharacter?.id
  );
  const sortedConversations = [...characterConversations].sort(
    (left, right) =>
      new Date(right.updated_at ?? right.created_at ?? 0).getTime() -
      new Date(left.updated_at ?? left.created_at ?? 0).getTime()
  );

  return (
    <>
      <aside className="grid gap-3 lg:content-start">
        <section className="rounded-lg border border-line bg-panel p-3 shadow-xl shadow-black/20">
          <div className="mb-3 flex items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold">Characters</h2>
              <p className="text-xs text-zinc-500">{characters.length} profiles</p>
            </div>
            <button
              className={secondaryButtonClass}
              disabled={mutationBusy}
              onClick={() => setBuilderOpen(true)}
              type="button"
            >
              Create
            </button>
          </div>
          <div className="space-y-2">
            {sortedCharacters.length === 0 ? <EmptyState text="No characters." /> : null}
            {sortedCharacters.map((character) => (
              <button
                aria-busy={provisioningCharacterId === character.id}
                className={`w-full rounded-md border px-3 py-2 text-left text-sm ${
                  activeCharacter?.id === character.id
                    ? "border-tide bg-cyan-950/80"
                    : "border-line bg-ink hover:border-zinc-500"
                }`}
                disabled={provisioningCharacterId === character.id}
                key={character.id}
                onClick={() => void onSelectCharacter(character)}
                type="button"
              >
                <span className="block truncate font-medium">{character.name}</span>
                {provisioningCharacterId === character.id ? (
                  <span className="mt-1 block text-xs text-tide">Opening room...</span>
                ) : (
                  <span className="mt-1 flex flex-wrap gap-1 text-xs text-zinc-500">
                    <span>{conversationCounts[character.id] ?? 0} threads</span>
                    {(unreadCounts[character.id] ?? 0) > 0 ? (
                      <>
                        <span>·</span>
                        <span className="text-moss">{unreadCounts[character.id]} new</span>
                      </>
                    ) : null}
                    <span>·</span>
                    <span>{characterReadiness(character)}</span>
                    <span>·</span>
                    <span>{presencePosture(character)}</span>
                  </span>
                )}
              </button>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-line bg-panel p-3 shadow-xl shadow-black/20">
          <div className="mb-3 flex items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold">Threads</h2>
              <p className="text-xs text-zinc-500">
                {activeCharacter
                  ? `${characterConversations.length} for ${activeCharacter.name}`
                  : "No character"}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                aria-busy={conversationCreationMode === "normal"}
                className={`${secondaryButtonClass} min-w-16`}
                disabled={mutationBusy || !activeCharacter}
                onClick={() => onCreateConversation("normal")}
                type="button"
              >
                {conversationCreationMode === "normal" ? "Opening" : "New"}
              </button>
              <button
                aria-busy={conversationCreationMode === "private"}
                className={`${secondaryButtonClass} min-w-20`}
                disabled={mutationBusy || !activeCharacter}
                onClick={() => onCreateConversation("private")}
                type="button"
              >
                {conversationCreationMode === "private" ? "Opening" : "Private"}
              </button>
            </div>
          </div>
          <div className="space-y-2">
            {characterConversations.length === 0 ? <EmptyState text="No threads." /> : null}
            {sortedConversations.map((conversation) => (
              <button
                className={`w-full rounded-md border px-3 py-2 text-left text-sm ${
                  activeConversation?.id === conversation.id
                    ? "border-moss bg-lime-950/50"
                    : "border-line bg-ink hover:border-zinc-500"
                }`}
                key={conversation.id}
                onClick={() => void onSelectConversation(conversation)}
                type="button"
              >
                <span className="flex min-w-0 items-center justify-between gap-2">
                  <span className="truncate">{conversation.title ?? "Untitled thread"}</span>
                  {conversation.unread_count > 0 ? (
                    <span
                      className="shrink-0 rounded-full bg-moss px-2 py-0.5 text-[11px] font-semibold text-ink"
                      title={`${conversation.unread_count} unread companion ${
                        conversation.unread_count === 1 ? "message" : "messages"
                      }`}
                    >
                      {conversation.unread_count}
                    </span>
                  ) : null}
                </span>
                <span className="mt-1 block text-xs text-zinc-500">
                  {conversation.last_message_at ?? conversation.updated_at
                    ? formatTimestamp(
                        conversation.last_message_at ?? conversation.updated_at ?? ""
                      )
                    : "No messages yet"}
                  {conversationPrivacyMode(conversation) === "private" ? " · private" : ""}
                </span>
              </button>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-line bg-panel p-3 shadow-xl shadow-black/20">
          <form
            aria-busy={searchStatus === "loading"}
            className="space-y-2"
            onSubmit={onSearch}
          >
            <div>
              <h2 className="text-sm font-semibold">Search</h2>
              <p className="text-xs text-zinc-500">Current thread</p>
            </div>
            <input
              aria-label="Search this thread"
              className={inputClass}
              disabled={!activeConversation}
              maxLength={120}
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search chat"
            />
            <button
              className={secondaryButtonClass}
              disabled={
                !activeConversation || !searchQuery.trim() || searchStatus === "loading"
              }
              type="submit"
            >
              {searchStatus === "loading" ? "Searching" : "Search"}
            </button>
          </form>
          <div aria-live="polite" className="mt-3 space-y-2">
            {searchStatus === "loading" ? (
              <EmptyState text="Searching this thread..." />
            ) : null}
            {searchStatus === "ready" && searchResults.length === 0 ? (
              <EmptyState text="No visible matches." />
            ) : null}
            {searchStatus === "error" && searchError ? (
              <p className={errorClass}>{searchError}</p>
            ) : null}
            {searchResults.map((message) => (
              <button
                aria-label={`Open ${searchResultAuthor(message, activeCharacter)} message from ${formatTimestamp(message.created_at)}`}
                className="w-full rounded-md border border-line bg-ink p-2 text-left text-xs hover:border-zinc-500 focus-visible:border-moss focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-moss/40"
                key={message.id}
                onClick={() => onSelectSearchResult(message)}
                type="button"
              >
                <span className="flex items-center justify-between gap-2 text-zinc-500">
                  <span>{searchResultAuthor(message, activeCharacter)}</span>
                  <time dateTime={message.created_at}>{formatTimestamp(message.created_at)}</time>
                </span>
                <span className="mt-1 line-clamp-3 text-zinc-200">{message.content}</span>
              </button>
            ))}
          </div>
        </section>
      </aside>
      {builderOpen ? (
        <CharacterCreationDialog onClose={closeBuilder} onCreate={onCreateCharacter} />
      ) : null}
    </>
  );
}

function searchResultAuthor(message: Message, character: Character | null): string {
  if (message.role === "user") {
    return "You";
  }
  if (message.role === "assistant") {
    return character?.name ?? "Companion";
  }
  return "Thread event";
}

function characterReadiness(character: Character): string {
  if (
    character.explicit_age !== null &&
    character.explicit_age >= 18 &&
    character.adult_mode_allowed
  ) {
    return "adult gates ready";
  }
  if (character.explicit_age !== null && character.explicit_age < 18) {
    return "safe only";
  }
  return "age unset";
}

function memoryPosture(character: Character): string {
  const preferences = character.boundaries_json.memory_preferences;
  if (
    typeof preferences === "object" &&
    preferences !== null &&
    !Array.isArray(preferences) &&
    "private_mode_default" in preferences &&
    preferences.private_mode_default === true
  ) {
    return "private memory";
  }
  return "memory on";
}

function presencePosture(character: Character): string {
  const proactive = character.boundaries_json.proactive_preferences;
  if (typeof proactive !== "object" || proactive === null || Array.isArray(proactive)) {
    return memoryPosture(character);
  }
  if ("enabled" in proactive && proactive.enabled === false) {
    return "presence paused";
  }
  if ("snoozed_until" in proactive && typeof proactive.snoozed_until === "string") {
    const snoozedUntil = new Date(proactive.snoozed_until);
    if (!Number.isNaN(snoozedUntil.getTime()) && snoozedUntil > new Date()) {
      return "presence snoozed";
    }
  }
  return memoryPosture(character) === "private memory" ? "private memory" : "presence on";
}
