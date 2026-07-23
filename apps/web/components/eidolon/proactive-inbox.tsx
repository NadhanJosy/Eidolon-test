"use client";

import { useCallback, useEffect, useState } from "react";

import { apiJson } from "@/lib/api";

import { Icon } from "./icons";
import type { ProactiveInboxItem } from "./types";

export function ProactiveInbox({
  token,
  characterId,
  characterName,
  onReturnToChat,
  onUnreadChange
}: {
  token: string;
  characterId: string | null;
  characterName: string;
  onReturnToChat: (item: ProactiveInboxItem) => void;
  onUnreadChange: (count: number) => void;
}) {
  const [items, setItems] = useState<ProactiveInboxItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!characterId) {
      setItems([]);
      setLoading(false);
      onUnreadChange(0);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const next = await fetchProactiveInbox(token, characterId);
      setItems(next);
      onUnreadChange(next.filter((item) => item.state === "delivered").length);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The inbox could not be opened.");
    } finally {
      setLoading(false);
    }
  }, [characterId, onUnreadChange, token]);

  useEffect(() => {
    if (!characterId) return;
    let active = true;
    void fetchProactiveInbox(token, characterId)
      .then((next) => {
        if (!active) return;
        setItems(next);
        setLoading(false);
        onUnreadChange(next.filter((item) => item.state === "delivered").length);
      })
      .catch((caught) => {
        if (!active) return;
        setError(caught instanceof Error ? caught.message : "The inbox could not be opened.");
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [characterId, onUnreadChange, token]);

  async function open(item: ProactiveInboxItem) {
    setActionId(item.id);
    setError(null);
    try {
      const value = await apiJson<unknown>(`/proactive/${item.id}/open`, {
        method: "POST",
        token
      });
      const updated = proactiveInboxItem(value);
      if (!updated) throw new Error("The companion note returned an unreadable response.");
      replace(updated);
      onReturnToChat(updated);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "That note could not be opened.");
    } finally {
      setActionId(null);
    }
  }

  async function dismiss(
    item: ProactiveInboxItem,
    feedback: "irrelevant" | "mute_similar" | null
  ) {
    setActionId(item.id);
    setError(null);
    try {
      await apiJson(`/proactive/${item.id}/dismiss`, {
        body: JSON.stringify({ feedback }),
        method: "POST",
        token
      });
      const next = items.filter((candidate) => candidate.id !== item.id);
      setItems(next);
      onUnreadChange(next.filter((candidate) => candidate.state === "delivered").length);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "That note could not be dismissed.");
    } finally {
      setActionId(null);
    }
  }

  function replace(updated: ProactiveInboxItem) {
    const next = items.map((item) => (item.id === updated.id ? updated : item));
    setItems(next);
    onUnreadChange(next.filter((item) => item.state === "delivered").length);
  }

  return (
    <section className="mx-auto w-full max-w-4xl px-5 py-8 sm:px-8 sm:py-12">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-[0.68rem] uppercase tracking-[0.2em] text-[#9b7968]">Presence</p>
          <h1 className="mt-2 font-eidolon-display text-3xl text-[#eadfd4]">Notes from {characterName}</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-[#8d8379]">
            Companion-initiated notes and reminders arrive here first. Conversation details never
            appear in an external notification preview.
          </p>
        </div>
        <button className="rounded-xl border border-white/[0.09] px-3 py-2 text-xs text-[#a79b90] transition hover:border-white/[0.18] hover:text-[#ded2c7]" onClick={() => void load()} type="button">
          Refresh
        </button>
      </div>

      {error ? <p className="mt-6 rounded-2xl border border-[#9f5d50]/30 bg-[#9f5d50]/10 p-4 text-sm text-[#d9a397]">{error}</p> : null}
      {loading ? <p className="mt-12 text-sm text-[#797169]">Opening the inbox…</p> : null}
      {!loading && items.length === 0 ? (
        <div className="mt-10 rounded-[1.75rem] border border-white/[0.08] bg-white/[0.018] p-8 text-center">
          <Icon className="mx-auto h-6 w-6 text-[#916f5e]" name="moon" />
          <h2 className="mt-4 font-eidolon-display text-xl text-[#d9cec3]">Nothing waiting</h2>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#81786f]">
            Notes stay restrained: they need real context, a suitable time, and room under your
            frequency limits.
          </p>
        </div>
      ) : null}

      <div className="mt-8 space-y-4">
        {items.map((item) => {
          const unread = item.state === "delivered";
          const busy = actionId === item.id;
          return (
            <article className={`rounded-[1.65rem] border p-5 sm:p-6 ${unread ? "border-[#a66e52]/30 bg-[#a66e52]/[0.07]" : "border-white/[0.08] bg-white/[0.018]"}`} key={item.id}>
              <div className="flex items-start gap-4">
                <span aria-hidden="true" className={`mt-1 h-2 w-2 shrink-0 rounded-full ${unread ? "bg-[#bd8163]" : "bg-white/[0.15]"}`} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <p className="text-[0.65rem] uppercase tracking-[0.15em] text-[#a17d6a]">
                      {unread ? <span className="sr-only">Unread. </span> : null}
                      {item.initiative_kind === "reminder" ? "Your reminder" : "Companion note"} · {humanCategory(item.candidate_type)}
                    </p>
                    {item.delivered_at ? <time className="text-[0.65rem] text-[#70685f]" dateTime={item.delivered_at}>{new Date(item.delivered_at).toLocaleString()}</time> : null}
                  </div>
                  <p className="mt-3 font-eidolon-display text-lg leading-7 text-[#ded3c8]">
                    {item.message_preview}
                  </p>
                  <p className="mt-3 text-xs leading-5 text-[#82786f]">{item.rationale}</p>
                  <div className="mt-5 flex flex-wrap gap-2">
                    <button className="rounded-xl bg-[#a86f54] px-3.5 py-2 text-xs font-medium text-[#1b100c] transition hover:bg-[#bd8163] disabled:opacity-50" disabled={busy} onClick={() => void open(item)} type="button">Return to chat</button>
                    <button className="rounded-xl border border-white/[0.09] px-3.5 py-2 text-xs text-[#9c9187] transition hover:border-white/[0.18] hover:text-[#d3c6ba] disabled:opacity-50" disabled={busy} onClick={() => void dismiss(item, null)} type="button">Dismiss</button>
                    <button className="rounded-xl border border-white/[0.09] px-3.5 py-2 text-xs text-[#9c9187] transition hover:border-white/[0.18] hover:text-[#d3c6ba] disabled:opacity-50" disabled={busy} onClick={() => void dismiss(item, "irrelevant")} type="button">Not relevant</button>
                    <button className="rounded-xl border border-white/[0.09] px-3.5 py-2 text-xs text-[#9c9187] transition hover:border-white/[0.18] hover:text-[#d3c6ba] disabled:opacity-50" disabled={busy} onClick={() => void dismiss(item, "mute_similar")} type="button">Mute similar</button>
                  </div>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function proactiveInboxItems(value: unknown): ProactiveInboxItem[] {
  return Array.isArray(value)
    ? value.map(proactiveInboxItem).filter((item): item is ProactiveInboxItem => item !== null)
    : [];
}

export async function fetchProactiveInbox(
  token: string,
  characterId: string
): Promise<ProactiveInboxItem[]> {
  const value = await apiJson<unknown>(
    `/proactive?view=inbox&character_id=${encodeURIComponent(characterId)}`,
    { token }
  );
  return proactiveInboxItems(value);
}

function proactiveInboxItem(value: unknown): ProactiveInboxItem | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  if (
    typeof item.id !== "string" ||
    typeof item.character_id !== "string" ||
    typeof item.candidate_type !== "string" ||
    typeof item.initiative_kind !== "string" ||
    typeof item.rationale !== "string" ||
    typeof item.state !== "string" ||
    typeof item.notification_preview !== "string" ||
    typeof item.created_at !== "string" ||
    typeof item.updated_at !== "string"
  ) return null;
  return item as ProactiveInboxItem;
}

function humanCategory(value: string): string {
  const labels: Record<string, string> = {
    callback: "callback",
    check_in: "check-in",
    follow_up: "follow-up",
    milestone: "milestone",
    queued_thought: "queued thought",
    reminder: "reminder",
    routine: "routine",
    suggestion: "suggestion"
  };
  return labels[value] ?? value.replaceAll("_", " ");
}
