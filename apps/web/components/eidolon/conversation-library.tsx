"use client";

import type { FormEvent } from "react";
import { useEffect, useRef } from "react";

import { CompanionPortrait, EmptyExperience, IconButton, PrimaryButton, QuietButton, fieldClass } from "./experience-primitives";
import { Icon } from "./icons";
import type { Character, Conversation, Message, SearchStatus } from "./types";

export function ConversationLibrary({
  open,
  onClose,
  characters,
  activeCharacter,
  activeConversation,
  conversations,
  searchQuery,
  setSearchQuery,
  searchResults,
  searchStatus,
  searchError,
  creating,
  busy,
  onSelectCharacter,
  onSelectConversation,
  onCreateConversation,
  onCreateCompanion,
  onSearch,
  onSelectSearchResult
}: {
  open: boolean;
  onClose: () => void;
  characters: Character[];
  activeCharacter: Character | null;
  activeConversation: Conversation | null;
  conversations: Conversation[];
  searchQuery: string;
  setSearchQuery: (value: string) => void;
  searchResults: Message[];
  searchStatus: SearchStatus;
  searchError: string | null;
  creating: boolean;
  busy: boolean;
  onSelectCharacter: (character: Character) => void;
  onSelectConversation: (conversation: Conversation) => void;
  onCreateConversation: () => void;
  onCreateCompanion: () => void;
  onSearch: (event: FormEvent<HTMLFormElement>) => void;
  onSelectSearchResult: (message: Message) => void;
}) {
  const panelRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab") {
        return;
      }
      const focusable = Array.from(
        panelRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        ) ?? []
      ).filter((element) => element.offsetParent !== null);
      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (
        event.shiftKey &&
        (document.activeElement === first || !panelRef.current?.contains(document.activeElement))
      ) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    const focusFrame = window.requestAnimationFrame(() => {
      panelRef.current?.querySelector<HTMLElement>("button")?.focus();
    });
    document.addEventListener("keydown", onKeyDown);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  if (!open) {
    return null;
  }
  const currentConversations = conversations
    .filter((conversation) => conversation.character_id === activeCharacter?.id)
    .sort((left, right) => Date.parse(right.last_message_at ?? right.updated_at) - Date.parse(left.last_message_at ?? left.updated_at));

  return (
    <div className="fixed inset-0 z-[80]" role="presentation">
      <button aria-label="Close past conversations" className="absolute inset-0 bg-black/65 backdrop-blur-sm" onClick={onClose} type="button" />
      <aside
        aria-label="Past conversations"
        aria-modal="true"
        className="safe-area-header absolute bottom-0 left-0 top-0 flex w-[min(92vw,28rem)] flex-col border-r border-white/[0.09] bg-[#0f0e0d]/98 shadow-[30px_0_90px_rgba(0,0,0,0.45)] reveal-up"
        ref={panelRef}
        role="dialog"
      >
        <header className="flex items-start justify-between gap-4 border-b border-white/[0.08] px-5 py-5 sm:px-7 sm:py-7">
          <div>
            <p className="text-[0.67rem] uppercase tracking-[0.2em] text-[#8b7f74]">Your shared history</p>
            <h2 className="mt-2 font-eidolon-display text-3xl">Past conversations</h2>
          </div>
          <IconButton icon="close" label="Close past conversations" onClick={onClose} />
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-8 sm:px-7">
          <section className="border-b border-white/[0.08] py-6">
            <div className="flex items-center justify-between">
              <h3 className="text-xs uppercase tracking-[0.17em] text-[#81776e]">Companions</h3>
              <button className="flex items-center gap-1.5 text-xs text-[#ad816b] hover:text-[#d4a88f]" disabled={busy} onClick={onCreateCompanion} type="button"><Icon className="h-3.5 w-3.5" name="plus" /> Shape another</button>
            </div>
            <div className="hide-scrollbar -mx-2 mt-4 flex gap-2 overflow-x-auto px-2 pb-1">
              {characters.map((character) => {
                const active = character.id === activeCharacter?.id;
                return (
                  <button
                    aria-pressed={active}
                    className={`flex min-w-36 items-center gap-3 rounded-2xl border px-3 py-3 text-left transition ${active ? "border-[#b98265]/30 bg-[#b98265]/[0.08]" : "border-white/[0.07] bg-white/[0.02] hover:border-white/[0.14]"}`}
                    key={character.id}
                    onClick={() => onSelectCharacter(character)}
                    type="button"
                  >
                    <CompanionPortrait name={character.name} quiet={!active} size="small" theme={characterTheme(character)} />
                    <span className="min-w-0"><span className="block truncate text-sm text-[#ded4ca]">{character.name}</span><span className="mt-0.5 block truncate text-[0.66rem] text-[#776f68]">{active ? "Here with you" : "Open their room"}</span></span>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="py-6">
            <form className="relative" onSubmit={onSearch}>
              <Icon className="pointer-events-none absolute left-4 top-3.5 h-4 w-4 text-[#6d665f]" name="search" />
              <input
                aria-label="Search this conversation"
                className={`${fieldClass} py-2.5 pl-11 pr-20`}
                maxLength={120}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Find something you said…"
                value={searchQuery}
              />
              <button className="absolute right-3 top-2.5 rounded-full px-2 py-1 text-xs text-[#9f7b68] disabled:opacity-40" disabled={!searchQuery.trim() || searchStatus === "loading"} type="submit">Find</button>
            </form>
            {searchError ? <p className="mt-3 text-xs text-[#d69587]" role="alert">{searchError}</p> : null}
            {searchStatus === "ready" && searchResults.length > 0 ? (
              <div className="mt-3 space-y-1 rounded-2xl border border-white/[0.08] bg-black/20 p-2">
                {searchResults.map((message) => (
                  <button className="block w-full rounded-xl px-3 py-2.5 text-left hover:bg-white/[0.05]" key={message.id} onClick={() => onSelectSearchResult(message)} type="button">
                    <span className="line-clamp-2 text-xs leading-5 text-[#b7ada2]">{message.content}</span>
                    <span className="mt-1 block text-[0.63rem] text-[#6e6861]">{message.role === "user" ? "You" : activeCharacter?.name ?? "Your companion"} · {shortDate(message.created_at)}</span>
                  </button>
                ))}
              </div>
            ) : null}
            {searchStatus === "ready" && searchResults.length === 0 && searchQuery.trim() ? <p className="mt-3 text-xs text-[#756e67]">Nothing in this conversation matches that yet.</p> : null}
          </section>

          <section>
            <div className="flex items-center justify-between gap-4">
              <div><h3 className="text-xs uppercase tracking-[0.17em] text-[#81776e]">With {activeCharacter?.name ?? "Eidolon"}</h3><p className="mt-1 text-xs text-[#68625c]">Each conversation keeps its own atmosphere.</p></div>
              <QuietButton disabled={busy} onClick={onCreateConversation}><span className="flex items-center gap-1.5"><Icon className="h-3.5 w-3.5" name="plus" /> {creating ? "Opening…" : "New conversation"}</span></QuietButton>
            </div>
            <div className="mt-5 space-y-2">
              {currentConversations.map((conversation) => {
                const active = conversation.id === activeConversation?.id;
                return (
                  <button
                    aria-current={active ? "page" : undefined}
                    className={`group flex w-full items-center gap-4 rounded-2xl border px-4 py-4 text-left transition ${active ? "border-[#b98265]/25 bg-[#b98265]/[0.07]" : "border-transparent hover:border-white/[0.08] hover:bg-white/[0.025]"}`}
                    key={conversation.id}
                    onClick={() => onSelectConversation(conversation)}
                    type="button"
                  >
                    <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-full border ${active ? "border-[#b98265]/30 text-[#bd886c]" : "border-white/[0.08] text-[#736b64]"}`}><Icon className="h-4 w-4" name={conversation.metadata_json.privacy_mode === "private" ? "lock" : "message"} /></span>
                    <span className="min-w-0 flex-1"><span className="block truncate text-sm text-[#d3c9be]">{conversation.title || "An unnamed conversation"}</span><span className="mt-1 block text-[0.66rem] text-[#716a63]">{conversation.last_message_at ? `Last shared ${relativeDate(conversation.last_message_at)}` : "Waiting for its first words"}</span></span>
                    {conversation.unread_count > 0 ? <span aria-label={`${conversation.unread_count} unread messages`} className="h-2 w-2 shrink-0 rounded-full bg-[#c28869] shadow-[0_0_14px_rgba(194,136,105,0.6)]" /> : null}
                  </button>
                );
              })}
              {currentConversations.length === 0 ? (
                <EmptyExperience icon="message" title="No chapters yet"><p>Your first conversation with this companion will begin here.</p><PrimaryButton className="mt-4" disabled={busy} onClick={onCreateConversation}>Begin a conversation</PrimaryButton></EmptyExperience>
              ) : null}
            </div>
          </section>
        </div>
      </aside>
    </div>
  );
}

function shortDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

function relativeDate(value: string): string {
  const elapsed = Date.now() - Date.parse(value);
  const minutes = Math.max(0, Math.floor(elapsed / 60_000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(new Date(value));
}

function characterTheme(character: Character): string {
  const theme = character.boundaries_json.visual_theme;
  return typeof theme === "string" ? theme : "";
}
