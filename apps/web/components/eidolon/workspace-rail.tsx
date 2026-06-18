import type { FormEvent } from "react";

import type { Character, Conversation, Message } from "./types";
import { EmptyState, formatTimestamp, inputClass, secondaryButtonClass } from "./ui";

export function WorkspaceRail({
  characters,
  activeCharacter,
  activeConversation,
  conversations,
  searchQuery,
  setSearchQuery,
  searchResults,
  newCharacterName,
  setNewCharacterName,
  onCreateCharacter,
  onSelectCharacter,
  onCreateConversation,
  onSearch,
  onSelectConversation
}: {
  characters: Character[];
  activeCharacter: Character | null;
  activeConversation: Conversation | null;
  conversations: Conversation[];
  searchQuery: string;
  setSearchQuery: (value: string) => void;
  searchResults: Message[];
  newCharacterName: string;
  setNewCharacterName: (value: string) => void;
  onCreateCharacter: () => void;
  onSelectCharacter: (character: Character) => void;
  onCreateConversation: () => void;
  onSearch: (event: FormEvent<HTMLFormElement>) => void;
  onSelectConversation: (conversation: Conversation) => void;
}) {
  const conversationCounts = conversations.reduce<Record<string, number>>((counts, conversation) => {
    counts[conversation.character_id] = (counts[conversation.character_id] ?? 0) + 1;
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
    <aside className="grid gap-3 lg:content-start">
      <section className="rounded-lg border border-line bg-panel p-3 shadow-xl shadow-black/20">
        <div className="mb-3 flex items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold">Characters</h2>
            <p className="text-xs text-zinc-500">{characters.length} profiles</p>
          </div>
        </div>
        <div className="space-y-2">
          {sortedCharacters.length === 0 ? <EmptyState text="No characters." /> : null}
          {sortedCharacters.map((character) => (
            <button
              className={`w-full rounded-md border px-3 py-2 text-left text-sm ${
                activeCharacter?.id === character.id
                  ? "border-tide bg-cyan-950/80"
                  : "border-line bg-ink hover:border-zinc-500"
              }`}
              key={character.id}
              onClick={() => void onSelectCharacter(character)}
              type="button"
            >
              <span className="block truncate font-medium">{character.name}</span>
              <span className="mt-1 flex flex-wrap gap-1 text-xs text-zinc-500">
                <span>{conversationCounts[character.id] ?? 0} threads</span>
                <span>·</span>
                <span>{character.explicit_age ? `${character.explicit_age}` : "age unset"}</span>
                <span>·</span>
                <span>intensity {character.content_intensity}</span>
              </span>
            </button>
          ))}
        </div>
        <form
          className="mt-3 flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            onCreateCharacter();
          }}
        >
          <input
            className={inputClass}
            value={newCharacterName}
            onChange={(event) => setNewCharacterName(event.target.value)}
            placeholder="Name"
          />
          <button className={secondaryButtonClass} type="submit">
            New
          </button>
        </form>
      </section>

      <section className="rounded-lg border border-line bg-panel p-3 shadow-xl shadow-black/20">
        <div className="mb-3 flex items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold">Threads</h2>
            <p className="text-xs text-zinc-500">
              {activeCharacter ? `${characterConversations.length} for ${activeCharacter.name}` : "No character"}
            </p>
          </div>
          <button className={secondaryButtonClass} onClick={onCreateConversation} type="button">
            New
          </button>
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
              <span className="block truncate">{conversation.title ?? conversation.id}</span>
              <span className="text-xs text-zinc-500">
                {conversation.updated_at
                  ? formatTimestamp(conversation.updated_at)
                  : conversation.id.slice(0, 8)}
              </span>
            </button>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-line bg-panel p-3 shadow-xl shadow-black/20">
        <form className="space-y-2" onSubmit={onSearch}>
          <div>
            <h2 className="text-sm font-semibold">Search</h2>
            <p className="text-xs text-zinc-500">Current thread</p>
          </div>
          <input
            className={inputClass}
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Search chat"
          />
          <button className={secondaryButtonClass} type="submit">
            Search
          </button>
        </form>
        <div className="mt-3 space-y-2">
          {searchQuery.trim() && searchResults.length === 0 ? (
            <EmptyState text="No visible matches." />
          ) : null}
          {searchResults.map((message) => (
            <p className="rounded-md border border-line bg-ink p-2 text-xs" key={message.id}>
              <span className="text-zinc-500">{message.role}</span>{" "}
              <span className="line-clamp-3">{message.content}</span>
            </p>
          ))}
        </div>
      </section>
    </aside>
  );
}
