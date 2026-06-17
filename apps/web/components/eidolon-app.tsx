"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { ApiError, apiErrorFromResponse, apiFetch, apiJson, getApiBaseUrl } from "@/lib/api";

type AuthMode = "login" | "register";
type Panel =
  | "character"
  | "memory"
  | "journal"
  | "relationship"
  | "adult"
  | "settings"
  | "debug"
  | "data";
type ContentMode = "sfw" | "adult";

type User = {
  id: string;
  email: string;
  display_name: string | null;
  age_gate_confirmed: boolean;
};

type Character = {
  id: string;
  name: string;
  description: string | null;
  personality_core: string | null;
  speech_style: string | null;
  boundaries_json: Record<string, unknown>;
  explicit_age: number | null;
  adult_mode_allowed: boolean;
  content_intensity: number;
};

type Conversation = {
  id: string;
  character_id: string;
  title: string | null;
  created_at?: string;
  updated_at?: string;
};

type DeliveryState = {
  typing_ms?: number;
  read_state?: string;
  away_state?: string;
};

type Message = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  metadata_json: {
    content_mode?: ContentMode;
    proactive?: boolean;
    provider?: string;
    prompt_version?: string;
    delivery_state?: DeliveryState;
    reroll_of?: string;
    edited?: boolean;
  } & Record<string, unknown>;
  created_at: string;
};

type MemoryItem = {
  id: string;
  memory_type: string;
  content: string;
  importance: number;
  confidence: number;
  emotional_weight: number;
  pinned: boolean;
  decay_score: number;
  contradiction_group: string | null;
  last_recalled_at: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

type Relationship = {
  trust: number;
  intimacy: number;
  warmth: number;
  tension: number;
  familiarity: number;
  attachment: number;
  mood: string;
  conflict_state: string;
  repair_needed: boolean;
  tags_json: string[];
  metadata_json: {
    timeline?: RelationshipEvent[];
  } & Record<string, unknown>;
};

type RelationshipEvent = {
  at?: string;
  kind?: string;
  summary?: string;
  tags?: string[];
};

type ScheduledJob = {
  id: string;
  job_type: string;
  status: string;
  run_at: string;
  payload_json?: Record<string, unknown>;
};

type Journal = {
  id: string;
  journal_type: string;
  title: string;
  summary: string;
  emotional_tags_json: string[];
  unresolved_threads_json: string[];
  callbacks_json: string[];
  importance: number;
  created_at: string;
};

type AdultStatus = {
  requested_mode: ContentMode;
  effective_mode: ContentMode;
  allowed: boolean;
  reasons: string[];
  intensity: number;
};

type DebugPayload = {
  relationship?: Relationship & { timeline?: RelationshipEvent[] };
  journals?: Pick<Journal, "id" | "title" | "summary" | "journal_type" | "importance">[];
  prompt_context?: {
    prompt_version: string;
    content_mode: string;
    llm_provider: string;
    prompt_preview: string;
    prompt_chars: number;
  };
};

type CharacterDraft = {
  name: string;
  description: string;
  personality_core: string;
  speech_style: string;
  explicit_age: string;
  adult_mode_allowed: boolean;
  content_intensity: string;
};

type AuthResponse = {
  access_token: string;
  user: User;
};

const emptyRelationship: Relationship = {
  trust: 0,
  intimacy: 0,
  warmth: 0,
  tension: 0,
  familiarity: 0,
  attachment: 0,
  mood: "steady",
  conflict_state: "clear",
  repair_needed: false,
  tags_json: [],
  metadata_json: {}
};

const panels: Panel[] = [
  "character",
  "memory",
  "journal",
  "relationship",
  "adult",
  "settings",
  "debug",
  "data"
];

const relationshipMetrics = [
  "trust",
  "intimacy",
  "warmth",
  "tension",
  "familiarity",
  "attachment"
] as const;

export function EidolonApp() {
  const [token, setToken] = useState<string | null>(() =>
    typeof window === "undefined" ? null : window.localStorage.getItem("eidolon_token")
  );
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("user@example.com");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("Nadhan");

  const [characters, setCharacters] = useState<Character[]>([]);
  const [activeCharacter, setActiveCharacter] = useState<Character | null>(null);
  const [characterDraft, setCharacterDraft] = useState<CharacterDraft>(emptyCharacterDraft());

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [messageDraft, setMessageDraft] = useState("");
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState("");
  const [contentMode, setContentMode] = useState<ContentMode>("sfw");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Message[]>([]);

  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [memoryContent, setMemoryContent] = useState("");
  const [memoryType, setMemoryType] = useState("preference");
  const [memoryImportance, setMemoryImportance] = useState("0.6");
  const [memoryPinned, setMemoryPinned] = useState(false);
  const [editingMemoryId, setEditingMemoryId] = useState<string | null>(null);
  const [memoryEditContent, setMemoryEditContent] = useState("");

  const [journals, setJournals] = useState<Journal[]>([]);
  const [journalTitle, setJournalTitle] = useState("");
  const [journalSummary, setJournalSummary] = useState("");

  const [relationship, setRelationship] = useState<Relationship>(emptyRelationship);
  const [adultStatus, setAdultStatus] = useState<AdultStatus | null>(null);
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [debug, setDebug] = useState<DebugPayload | null>(null);
  const [panel, setPanel] = useState<Panel>("character");

  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const activeCharacterId = activeCharacter?.id ?? activeConversation?.character_id ?? null;
  const timeline = relationship.metadata_json.timeline ?? debug?.relationship?.timeline ?? [];

  useEffect(() => {
    if (token && !user) {
      void bootstrap(token);
    }
    // bootstrap intentionally uses the latest state setters only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, user]);

  const sortedMessages = useMemo(
    () =>
      [...messages].sort(
        (left, right) =>
          new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
      ),
    [messages]
  );

  async function bootstrap(authToken: string) {
    setBusy(true);
    setError(null);
    try {
      const me = await apiJson<User>("/auth/me", { token: authToken });
      setUser(me);
      setDisplayName(me.display_name ?? "");
      const characterList = await apiJson<Character[]>("/characters", { token: authToken });
      setCharacters(characterList);

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
      setConversations(conversationList);

      const conversation = conversationList[0];
      setActiveConversation(conversation);
      const character =
        characterList.find((item) => item.id === conversation.character_id) ??
        (await apiJson<Character>(`/characters/${conversation.character_id}`, {
          token: authToken
        }));
      setCurrentCharacter(character);
      await loadConversation(authToken, conversation.id);
      await refreshSideState(authToken, character.id, conversation.id);
    } catch (caught) {
      setError(readError(caught));
      clearAuth();
    } finally {
      setBusy(false);
    }
  }

  async function handleAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
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
      window.localStorage.setItem("eidolon_token", auth.access_token);
      setToken(auth.access_token);
      setUser(auth.user);
      await bootstrap(auth.access_token);
    } catch (caught) {
      setError(readError(caught));
    } finally {
      setBusy(false);
    }
  }

  async function loadConversation(authToken: string, conversationId: string) {
    const history = await apiJson<Message[]>(`/conversations/${conversationId}/messages`, {
      token: authToken
    });
    setMessages(history);
  }

  async function refreshSideState(
    authToken: string,
    characterId: string,
    conversationId: string
  ) {
    const [memoryResult, relationshipResult, debugResult, jobsResult, journalsResult, adultResult] =
      await Promise.allSettled([
        apiJson<MemoryItem[]>(`/characters/${characterId}/memories`, { token: authToken }),
        apiJson<Relationship>(`/characters/${characterId}/relationship`, { token: authToken }),
        apiJson<DebugPayload>(`/debug/character/${characterId}`, { token: authToken }),
        apiJson<ScheduledJob[]>("/debug/jobs", { token: authToken }),
        apiJson<Journal[]>(`/characters/${characterId}/journals`, { token: authToken }),
        apiJson<AdultStatus>(`/characters/${characterId}/adult-status`, { token: authToken })
      ]);

    if (memoryResult.status === "fulfilled") {
      setMemories(memoryResult.value);
    }
    if (relationshipResult.status === "fulfilled") {
      setRelationship(relationshipResult.value);
    }
    if (debugResult.status === "fulfilled") {
      setDebug(debugResult.value);
    }
    if (jobsResult.status === "fulfilled") {
      setJobs(jobsResult.value);
    }
    if (journalsResult.status === "fulfilled") {
      setJournals(journalsResult.value);
    }
    if (adultResult.status === "fulfilled") {
      setAdultStatus(adultResult.value);
    }
    await loadConversation(authToken, conversationId);
  }

  async function reloadConversations(authToken: string) {
    const conversationList = await apiJson<Conversation[]>("/conversations", {
      token: authToken
    });
    setConversations(conversationList);
    return conversationList;
  }

  async function selectConversation(conversation: Conversation) {
    if (!token) {
      return;
    }
    setActiveConversation(conversation);
    setError(null);
    const character =
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
      const conversationList = await reloadConversations(token);
      const conversation = conversationList.find((item) => item.id === created.id) ?? created;
      await selectConversation(conversation);
      setNotice("Conversation created.");
    } catch (caught) {
      setError(readError(caught));
    } finally {
      setBusy(false);
    }
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !activeConversation || !activeCharacterId || !messageDraft.trim()) {
      return;
    }
    if (editingMessageId) {
      await saveEditedMessage();
      return;
    }

    setSending(true);
    setError(null);
    setNotice(null);
    setStreamingContent("");

    try {
      const response = await apiFetch("/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          conversation_id: activeConversation.id,
          content: messageDraft.trim(),
          content_mode: contentMode
        })
      });
      if (!response.ok) {
        throw await apiErrorFromResponse(response, "/chat/stream");
      }
      if (!response.body) {
        throw new ApiError(
          `Eidolon API at ${getApiBaseUrl()}/chat/stream did not open a response stream.`,
          response.status
        );
      }
      setMessageDraft("");
      await readEventStream(response.body);
      await refreshSideState(token, activeCharacterId, activeConversation.id);
    } catch (caught) {
      setError(readError(caught));
    } finally {
      setSending(false);
      setStreamingContent("");
    }
  }

  async function saveEditedMessage() {
    if (!token || !activeConversation || !editingMessageId || !messageDraft.trim()) {
      return;
    }
    setSending(true);
    setError(null);
    try {
      const updated = await apiJson<Message>(
        `/conversations/${activeConversation.id}/messages/${editingMessageId}`,
        {
          method: "PATCH",
          body: JSON.stringify({ content: messageDraft.trim() }),
          token
        }
      );
      setMessages((current) =>
        current.map((message) => (message.id === updated.id ? updated : message))
      );
      setEditingMessageId(null);
      setMessageDraft("");
      setNotice("Message edited.");
    } catch (caught) {
      setError(readError(caught));
    } finally {
      setSending(false);
    }
  }

  async function readEventStream(body: ReadableStream<Uint8Array>) {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        handleSseEvent(part);
      }
    }
    if (buffer.trim()) {
      handleSseEvent(buffer);
    }
  }

  function handleSseEvent(block: string) {
    const eventLine = block.split("\n").find((line) => line.startsWith("event:"));
    const dataLine = block.split("\n").find((line) => line.startsWith("data:"));
    const event = eventLine?.replace("event:", "").trim();
    const data = dataLine?.replace("data:", "").trim();
    if (!event || !data) {
      return;
    }
    const payload = JSON.parse(data) as Record<string, unknown>;
    if (event === "message_start" && isMessage(payload.user_message)) {
      appendMessage(payload.user_message);
    }
    if (event === "token" && typeof payload.content === "string") {
      setStreamingContent((current) => current + payload.content);
    }
    if (event === "message_done" && isMessage(payload.assistant_message)) {
      appendMessage(payload.assistant_message);
      setStreamingContent("");
    }
    if (event === "error" && typeof payload.detail === "string") {
      setError(payload.detail);
    }
  }

  function appendMessage(message: Message) {
    setMessages((current) => {
      if (current.some((item) => item.id === message.id)) {
        return current;
      }
      return [...current, message];
    });
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

  async function addMemory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !activeCharacterId || !activeConversation || !memoryContent.trim()) {
      return;
    }
    setError(null);
    await apiJson<MemoryItem>(`/characters/${activeCharacterId}/memories`, {
      method: "POST",
      body: JSON.stringify({
        memory_type: memoryType,
        content: memoryContent.trim(),
        importance: parseDecimal(memoryImportance, 0.6),
        confidence: 0.8,
        pinned: memoryPinned
      }),
      token
    });
    setMemoryContent("");
    setMemoryPinned(false);
    await refreshSideState(token, activeCharacterId, activeConversation.id);
  }

  async function saveMemoryEdit(memory: MemoryItem) {
    if (!token || !activeCharacterId || !activeConversation || !memoryEditContent.trim()) {
      return;
    }
    const updated = await apiJson<MemoryItem>(
      `/characters/${activeCharacterId}/memories/${memory.id}`,
      {
        method: "PATCH",
        body: JSON.stringify({ content: memoryEditContent.trim() }),
        token
      }
    );
    setMemories((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    setEditingMemoryId(null);
    setMemoryEditContent("");
  }

  async function toggleMemoryPinned(memory: MemoryItem) {
    if (!token || !activeCharacterId || !activeConversation) {
      return;
    }
    const updated = await apiJson<MemoryItem>(
      `/characters/${activeCharacterId}/memories/${memory.id}`,
      {
        method: "PATCH",
        body: JSON.stringify({ pinned: !memory.pinned }),
        token
      }
    );
    setMemories((current) => current.map((item) => (item.id === updated.id ? updated : item)));
  }

  async function deleteMemory(memory: MemoryItem) {
    if (!token || !activeCharacterId) {
      return;
    }
    await apiJson<{ deleted: number }>(`/characters/${activeCharacterId}/memories/${memory.id}`, {
      method: "DELETE",
      token
    });
    setMemories((current) => current.filter((item) => item.id !== memory.id));
  }

  async function clearMemories() {
    if (!token || !activeCharacterId || !activeConversation) {
      return;
    }
    const response = await apiJson<{ deleted: number }>(`/characters/${activeCharacterId}/memories`, {
      method: "DELETE",
      token
    });
    setMemories([]);
    setNotice(`${response.deleted} memories cleared.`);
    await refreshSideState(token, activeCharacterId, activeConversation.id);
  }

  async function forgetMemories() {
    if (!token || !activeCharacterId || !activeConversation) {
      return;
    }
    const response = await apiJson<{ forgotten: number }>(
      `/characters/${activeCharacterId}/memories/forget`,
      {
        method: "POST",
        token
      }
    );
    setNotice(`${response.forgotten} low-value memories forgotten.`);
    await refreshSideState(token, activeCharacterId, activeConversation.id);
  }

  async function addJournal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !activeCharacterId || !journalTitle.trim() || !journalSummary.trim()) {
      return;
    }
    await apiJson<Journal>(`/characters/${activeCharacterId}/journals`, {
      method: "POST",
      body: JSON.stringify({
        conversation_id: activeConversation?.id ?? null,
        title: journalTitle.trim(),
        summary: journalSummary.trim(),
        journal_type: "manual_note",
        importance: 0.6
      }),
      token
    });
    setJournalTitle("");
    setJournalSummary("");
    if (activeConversation) {
      await refreshSideState(token, activeCharacterId, activeConversation.id);
    }
  }

  async function queueProactive() {
    if (!token || !activeConversation || !activeCharacterId) {
      return;
    }
    const message = await apiJson<Message | null>(
      `/debug/conversation/${activeConversation.id}/proactive`,
      {
        method: "POST",
        body: JSON.stringify({}),
        token
      }
    );
    setNotice(message ? "Queued check-in." : "Cooldown is active.");
    await refreshSideState(token, activeCharacterId, activeConversation.id);
  }

  async function rerollMessage(message: Message) {
    if (!token || !activeConversation || !activeCharacterId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const rerolled = await apiJson<Message>("/chat/reroll", {
        method: "POST",
        body: JSON.stringify({
          conversation_id: activeConversation.id,
          assistant_message_id: message.id,
          content_mode: contentMode
        }),
        token
      });
      appendMessage(rerolled);
      await refreshSideState(token, activeCharacterId, activeConversation.id);
    } catch (caught) {
      setError(readError(caught));
    } finally {
      setBusy(false);
    }
  }

  function startEditMessage(message: Message) {
    setEditingMessageId(message.id);
    setMessageDraft(message.content);
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

  async function clearConversationMessages() {
    if (!token || !activeConversation || !activeCharacterId) {
      return;
    }
    const response = await apiJson<{ deleted: number }>(
      `/conversations/${activeConversation.id}/messages`,
      {
        method: "DELETE",
        token
      }
    );
    setMessages([]);
    setNotice(`${response.deleted} messages cleared.`);
    await refreshSideState(token, activeCharacterId, activeConversation.id);
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

  async function exportAccount() {
    if (!token) {
      return;
    }
    const payload = await apiJson<Record<string, unknown>>("/account/export", { token });
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json"
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `eidolon-export-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function clearAuth() {
    window.localStorage.removeItem("eidolon_token");
    setToken(null);
    setUser(null);
    setMessages([]);
    setCharacters([]);
    setConversations([]);
    setActiveConversation(null);
    setActiveCharacter(null);
    setDebug(null);
    setNotice(null);
  }

  function setCurrentCharacter(character: Character) {
    setActiveCharacter(character);
    setCharacterDraft(toCharacterDraft(character));
  }

  if (!user || !token) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-ink px-4 py-8 text-paper">
        <section className="w-full max-w-sm border border-line bg-panel p-5 shadow-xl">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase text-zinc-500">Private text companion</p>
              <h1 className="text-2xl font-semibold">Eidolon</h1>
            </div>
            <div className="flex overflow-hidden rounded-md border border-line">
              <button
                type="button"
                onClick={() => setAuthMode("login")}
                className={tabClass(authMode === "login")}
              >
                Login
              </button>
              <button
                type="button"
                onClick={() => setAuthMode("register")}
                className={tabClass(authMode === "register")}
              >
                Register
              </button>
            </div>
          </div>

          <form className="space-y-3" onSubmit={handleAuth}>
            <label className="block text-sm text-zinc-300">
              Email
              <input
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className={inputClass}
                type="email"
                autoComplete="email"
              />
            </label>
            <label className="block text-sm text-zinc-300">
              Password
              <input
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className={inputClass}
                type="password"
                autoComplete={authMode === "register" ? "new-password" : "current-password"}
              />
            </label>
            {authMode === "register" ? (
              <label className="block text-sm text-zinc-300">
                Name
                <input
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  className={inputClass}
                  autoComplete="name"
                />
              </label>
            ) : null}
            {error ? <p className={errorClass}>{error}</p> : null}
            <button className={primaryButtonClass} disabled={busy} type="submit">
              {busy ? "Working" : authMode === "register" ? "Create account" : "Enter"}
            </button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-ink text-paper">
      <header className="border-b border-line bg-panel">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <p className="text-xs uppercase text-zinc-500">Eidolon Level 2</p>
            <h1 className="truncate text-xl font-semibold">
              {activeCharacter?.name ?? "Conversation"}
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="rounded-md border border-line px-3 py-2 text-zinc-300">
              {user.display_name ?? user.email}
            </span>
            <span className="rounded-md border border-line px-3 py-2 text-zinc-300">
              {relationship.mood} · {relationship.conflict_state}
            </span>
            <select
              value={contentMode}
              onChange={(event) => setContentMode(event.target.value as ContentMode)}
              className="rounded-md border border-line bg-ink px-3 py-2"
              aria-label="Content mode"
            >
              <option value="sfw">SFW</option>
              <option value="adult">Adult gated</option>
            </select>
            <button className={secondaryButtonClass} onClick={clearAuth} type="button">
              Logout
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-4 px-4 py-4 lg:grid-cols-[250px_minmax(0,1fr)_390px]">
        <ConversationRail
          activeConversation={activeConversation}
          conversations={conversations}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          searchResults={searchResults}
          onCreate={createConversationForCurrentCharacter}
          onSearch={searchMessages}
          onSelect={selectConversation}
        />

        <section className="flex min-h-[calc(100vh-112px)] flex-col border border-line bg-panel">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
            <div className="min-w-0">
              <h2 className="truncate text-base font-medium">
                {activeConversation?.title ?? "Chat"}
              </h2>
              <p className="text-xs text-zinc-500">
                {sortedMessages.length} messages · {memories.length} memories ·{" "}
                {journals.length} journal entries
              </p>
            </div>
            <button
              className={secondaryButtonClass}
              onClick={queueProactive}
              type="button"
              disabled={busy || sending}
            >
              Queue check-in
            </button>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
            {sortedMessages.length === 0 && !streamingContent ? (
              <EmptyState text="No messages yet." />
            ) : null}
            {sortedMessages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                onEdit={startEditMessage}
                onReroll={rerollMessage}
              />
            ))}
            {streamingContent ? (
              <div className="max-w-[86%] border border-line bg-ink px-3 py-2">
                <p className="whitespace-pre-wrap text-sm leading-6">{streamingContent}</p>
                <p className="mt-2 text-xs text-zinc-500">Streaming</p>
              </div>
            ) : null}
          </div>

          <form className="border-t border-line p-3" onSubmit={sendMessage}>
            {error ? <p className={`mb-2 ${errorClass}`}>{error}</p> : null}
            {notice ? <p className={`mb-2 ${noticeClass}`}>{notice}</p> : null}
            <div className="flex gap-2">
              <textarea
                value={messageDraft}
                onChange={(event) => setMessageDraft(event.target.value)}
                className="min-h-12 flex-1 resize-none rounded-md border border-line bg-ink px-3 py-2 text-sm"
                placeholder={editingMessageId ? "Edit message" : "Write a message"}
                disabled={sending}
              />
              <div className="flex w-24 flex-col gap-2">
                <button
                  className="rounded-md bg-paper px-3 py-2 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={sending || !messageDraft.trim()}
                  type="submit"
                >
                  {sending ? "..." : editingMessageId ? "Save" : "Send"}
                </button>
                {editingMessageId ? (
                  <button
                    className={secondaryButtonClass}
                    onClick={() => {
                      setEditingMessageId(null);
                      setMessageDraft("");
                    }}
                    type="button"
                  >
                    Cancel
                  </button>
                ) : null}
              </div>
            </div>
          </form>
        </section>

        <aside className="border border-line bg-panel">
          <div className="grid grid-cols-4 border-b border-line text-sm">
            {panels.map((item) => (
              <button
                key={item}
                className={tabClass(panel === item)}
                onClick={() => setPanel(item)}
                type="button"
              >
                {item}
              </button>
            ))}
          </div>
          <div className="space-y-4 p-4">
            {panel === "character" ? (
              <CharacterPanel
                draft={characterDraft}
                setDraft={setCharacterDraft}
                onSave={saveCharacter}
              />
            ) : null}
            {panel === "memory" ? (
              <MemoryPanel
                memories={memories}
                memoryContent={memoryContent}
                memoryType={memoryType}
                memoryImportance={memoryImportance}
                memoryPinned={memoryPinned}
                editingMemoryId={editingMemoryId}
                memoryEditContent={memoryEditContent}
                setMemoryContent={setMemoryContent}
                setMemoryType={setMemoryType}
                setMemoryImportance={setMemoryImportance}
                setMemoryPinned={setMemoryPinned}
                setEditingMemoryId={setEditingMemoryId}
                setMemoryEditContent={setMemoryEditContent}
                onAdd={addMemory}
                onSaveEdit={saveMemoryEdit}
                onTogglePinned={toggleMemoryPinned}
                onDelete={deleteMemory}
                onForget={forgetMemories}
              />
            ) : null}
            {panel === "journal" ? (
              <JournalPanel
                journals={journals}
                title={journalTitle}
                summary={journalSummary}
                setTitle={setJournalTitle}
                setSummary={setJournalSummary}
                onAdd={addJournal}
              />
            ) : null}
            {panel === "relationship" ? (
              <RelationshipPanel relationship={relationship} timeline={timeline} />
            ) : null}
            {panel === "adult" ? (
              <AdultPanel
                status={adultStatus}
                user={user}
                draft={characterDraft}
                setDraft={setCharacterDraft}
                onToggleAgeGate={() =>
                  void updateUser({ age_gate_confirmed: !user.age_gate_confirmed })
                }
                onSave={saveCharacter}
              />
            ) : null}
            {panel === "settings" ? (
              <SettingsPanel
                user={user}
                displayName={displayName}
                setDisplayName={setDisplayName}
                onSaveName={() => void updateUser({ display_name: displayName })}
                onLogout={clearAuth}
              />
            ) : null}
            {panel === "debug" ? (
              <DebugPanel debug={debug} jobs={jobs} conversations={conversations} />
            ) : null}
            {panel === "data" ? (
              <DataPanel
                onExport={exportAccount}
                onClearMessages={clearConversationMessages}
                onClearMemories={clearMemories}
                onDeleteConversation={deleteActiveConversation}
              />
            ) : null}
          </div>
        </aside>
      </div>
    </main>
  );
}

function ConversationRail({
  activeConversation,
  conversations,
  searchQuery,
  setSearchQuery,
  searchResults,
  onCreate,
  onSearch,
  onSelect
}: {
  activeConversation: Conversation | null;
  conversations: Conversation[];
  searchQuery: string;
  setSearchQuery: (value: string) => void;
  searchResults: Message[];
  onCreate: () => void;
  onSearch: (event: FormEvent<HTMLFormElement>) => void;
  onSelect: (conversation: Conversation) => void;
}) {
  return (
    <aside className="space-y-3 border border-line bg-panel p-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Conversations</h2>
        <button className={secondaryButtonClass} onClick={onCreate} type="button">
          New
        </button>
      </div>
      <div className="space-y-2">
        {conversations.map((conversation) => (
          <button
            className={`w-full rounded-md border px-3 py-2 text-left text-sm ${
              activeConversation?.id === conversation.id
                ? "border-tide bg-cyan-950"
                : "border-line bg-ink hover:border-zinc-500"
            }`}
            key={conversation.id}
            onClick={() => void onSelect(conversation)}
            type="button"
          >
            <span className="block truncate">{conversation.title ?? conversation.id}</span>
            <span className="text-xs text-zinc-500">{conversation.id.slice(0, 8)}</span>
          </button>
        ))}
      </div>
      <form className="space-y-2 border-t border-line pt-3" onSubmit={onSearch}>
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
      <div className="space-y-2">
        {searchResults.map((message) => (
          <p className="rounded-md border border-line bg-ink p-2 text-xs" key={message.id}>
            <span className="text-zinc-500">{message.role}</span> {message.content}
          </p>
        ))}
      </div>
    </aside>
  );
}

function MessageBubble({
  message,
  onEdit,
  onReroll
}: {
  message: Message;
  onEdit: (message: Message) => void;
  onReroll: (message: Message) => void;
}) {
  const isUser = message.role === "user";
  const delivery = message.metadata_json.delivery_state;
  return (
    <article className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[86%] rounded-md border px-3 py-2 ${
          isUser ? "border-tide bg-cyan-950" : "border-line bg-ink"
        }`}
      >
        <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
          <span>
            {message.role} · {formatTimestamp(message.created_at)}
          </span>
          {message.metadata_json.edited ? <span>edited</span> : null}
          {message.metadata_json.proactive ? <span>proactive</span> : null}
          {delivery?.away_state ? <span>{delivery.away_state}</span> : null}
          {isUser ? (
            <button className="text-zinc-300 hover:text-paper" onClick={() => onEdit(message)} type="button">
              Edit
            </button>
          ) : (
            <button
              className="text-zinc-300 hover:text-paper"
              onClick={() => void onReroll(message)}
              type="button"
            >
              Reroll
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

function CharacterPanel({
  draft,
  setDraft,
  onSave
}: {
  draft: CharacterDraft;
  setDraft: (value: CharacterDraft) => void;
  onSave: () => void;
}) {
  return (
    <>
      <label className="block text-sm text-zinc-300">
        Name
        <input
          className={inputClass}
          value={draft.name}
          onChange={(event) => setDraft({ ...draft, name: event.target.value })}
        />
      </label>
      <label className="block text-sm text-zinc-300">
        Description
        <textarea
          className={`${inputClass} min-h-20 resize-none`}
          value={draft.description}
          onChange={(event) => setDraft({ ...draft, description: event.target.value })}
        />
      </label>
      <label className="block text-sm text-zinc-300">
        Personality
        <textarea
          className={`${inputClass} min-h-20 resize-none`}
          value={draft.personality_core}
          onChange={(event) => setDraft({ ...draft, personality_core: event.target.value })}
        />
      </label>
      <label className="block text-sm text-zinc-300">
        Speech
        <textarea
          className={`${inputClass} min-h-16 resize-none`}
          value={draft.speech_style}
          onChange={(event) => setDraft({ ...draft, speech_style: event.target.value })}
        />
      </label>
      <button className={primaryButtonClass} onClick={onSave} type="button">
        Save character
      </button>
    </>
  );
}

function MemoryPanel({
  memories,
  memoryContent,
  memoryType,
  memoryImportance,
  memoryPinned,
  editingMemoryId,
  memoryEditContent,
  setMemoryContent,
  setMemoryType,
  setMemoryImportance,
  setMemoryPinned,
  setEditingMemoryId,
  setMemoryEditContent,
  onAdd,
  onSaveEdit,
  onTogglePinned,
  onDelete,
  onForget
}: {
  memories: MemoryItem[];
  memoryContent: string;
  memoryType: string;
  memoryImportance: string;
  memoryPinned: boolean;
  editingMemoryId: string | null;
  memoryEditContent: string;
  setMemoryContent: (value: string) => void;
  setMemoryType: (value: string) => void;
  setMemoryImportance: (value: string) => void;
  setMemoryPinned: (value: boolean) => void;
  setEditingMemoryId: (value: string | null) => void;
  setMemoryEditContent: (value: string) => void;
  onAdd: (event: FormEvent<HTMLFormElement>) => void;
  onSaveEdit: (memory: MemoryItem) => void;
  onTogglePinned: (memory: MemoryItem) => void;
  onDelete: (memory: MemoryItem) => void;
  onForget: () => void;
}) {
  return (
    <>
      <form className="space-y-2" onSubmit={onAdd}>
        <textarea
          className={`${inputClass} min-h-16 resize-none`}
          value={memoryContent}
          onChange={(event) => setMemoryContent(event.target.value)}
          placeholder="Memory"
        />
        <div className="grid grid-cols-2 gap-2">
          <select
            className={inputClass}
            value={memoryType}
            onChange={(event) => setMemoryType(event.target.value)}
          >
            <option value="preference">preference</option>
            <option value="event">event</option>
            <option value="inside_joke">inside joke</option>
            <option value="boundary">boundary</option>
            <option value="relationship_milestone">milestone</option>
          </select>
          <input
            className={inputClass}
            value={memoryImportance}
            onChange={(event) => setMemoryImportance(event.target.value)}
            inputMode="decimal"
            aria-label="Memory importance"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-zinc-300">
          <input
            type="checkbox"
            checked={memoryPinned}
            onChange={(event) => setMemoryPinned(event.target.checked)}
          />
          Pinned
        </label>
        <div className="flex gap-2">
          <button className={primaryButtonClass} type="submit">
            Add memory
          </button>
          <button className={secondaryButtonClass} onClick={onForget} type="button">
            Forget stale
          </button>
        </div>
      </form>
      <div className="space-y-2">
        {memories.length === 0 ? <EmptyState text="No memories." /> : null}
        {memories.map((memory) => (
          <article className="rounded-md border border-line bg-ink p-3 text-sm" key={memory.id}>
            {editingMemoryId === memory.id ? (
              <textarea
                className={`${inputClass} min-h-20 resize-none`}
                value={memoryEditContent}
                onChange={(event) => setMemoryEditContent(event.target.value)}
              />
            ) : (
              <p>{memory.content}</p>
            )}
            <p className="mt-2 text-xs text-zinc-500">
              {memory.memory_type} · confidence {memory.confidence.toFixed(1)} · importance{" "}
              {memory.importance.toFixed(1)} · decay {memory.decay_score.toFixed(2)}
            </p>
            {memory.contradiction_group ? (
              <p className="mt-1 text-xs text-ember">{memory.contradiction_group}</p>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-2">
              {editingMemoryId === memory.id ? (
                <button
                  className={primaryButtonClass}
                  onClick={() => void onSaveEdit(memory)}
                  type="button"
                >
                  Save
                </button>
              ) : (
                <button
                  className={secondaryButtonClass}
                  onClick={() => {
                    setEditingMemoryId(memory.id);
                    setMemoryEditContent(memory.content);
                  }}
                  type="button"
                >
                  Edit
                </button>
              )}
              <button
                className={secondaryButtonClass}
                onClick={() => void onTogglePinned(memory)}
                type="button"
              >
                {memory.pinned ? "Unpin" : "Pin"}
              </button>
              <button
                className={secondaryButtonClass}
                onClick={() => void onDelete(memory)}
                type="button"
              >
                Delete
              </button>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}

function JournalPanel({
  journals,
  title,
  summary,
  setTitle,
  setSummary,
  onAdd
}: {
  journals: Journal[];
  title: string;
  summary: string;
  setTitle: (value: string) => void;
  setSummary: (value: string) => void;
  onAdd: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <>
      <form className="space-y-2" onSubmit={onAdd}>
        <input
          className={inputClass}
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Journal title"
        />
        <textarea
          className={`${inputClass} min-h-20 resize-none`}
          value={summary}
          onChange={(event) => setSummary(event.target.value)}
          placeholder="Summary"
        />
        <button className={primaryButtonClass} type="submit">
          Add journal
        </button>
      </form>
      <div className="space-y-2">
        {journals.length === 0 ? <EmptyState text="No journal entries." /> : null}
        {journals.map((journal) => (
          <article className="rounded-md border border-line bg-ink p-3 text-sm" key={journal.id}>
            <div className="flex items-start justify-between gap-2">
              <h3 className="font-medium">{journal.title}</h3>
              <span className="text-xs text-zinc-500">{journal.importance.toFixed(1)}</span>
            </div>
            <p className="mt-2 whitespace-pre-wrap leading-6">{journal.summary}</p>
            <p className="mt-2 text-xs text-zinc-500">
              {journal.journal_type} · {formatTimestamp(journal.created_at)}
            </p>
            <TagRow tags={[...journal.emotional_tags_json, ...journal.callbacks_json.slice(0, 2)]} />
          </article>
        ))}
      </div>
    </>
  );
}

function RelationshipPanel({
  relationship,
  timeline
}: {
  relationship: Relationship;
  timeline: RelationshipEvent[];
}) {
  return (
    <>
      <div className="grid grid-cols-2 gap-2 text-sm">
        {relationshipMetrics.map((key) => (
          <div className="rounded-md border border-line bg-ink p-2" key={key}>
            <dt className="text-zinc-500">{key}</dt>
            <dd className="font-mono">{formatMetric(relationship[key])}</dd>
          </div>
        ))}
      </div>
      <div className="rounded-md border border-line bg-ink p-3 text-sm">
        <p>
          {relationship.mood} · {relationship.conflict_state}
        </p>
        {relationship.repair_needed ? <p className="mt-1 text-ember">Repair needed</p> : null}
        <TagRow tags={relationship.tags_json} />
      </div>
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Timeline</h2>
        {timeline.length === 0 ? <EmptyState text="No timeline events." /> : null}
        {timeline
          .slice()
          .reverse()
          .slice(0, 12)
          .map((event, index) => (
            <article className="rounded-md border border-line bg-ink p-3 text-xs" key={index}>
              <p className="text-zinc-300">{event.summary ?? event.kind ?? "state update"}</p>
              <p className="mt-1 text-zinc-500">{event.at ? formatTimestamp(event.at) : ""}</p>
              <TagRow tags={event.tags ?? []} />
            </article>
          ))}
      </section>
    </>
  );
}

function AdultPanel({
  status,
  user,
  draft,
  setDraft,
  onToggleAgeGate,
  onSave
}: {
  status: AdultStatus | null;
  user: User;
  draft: CharacterDraft;
  setDraft: (value: CharacterDraft) => void;
  onToggleAgeGate: () => void;
  onSave: () => void;
}) {
  return (
    <>
      <div className="rounded-md border border-line bg-ink p-3 text-sm">
        <p>{status?.effective_mode === "adult" ? "Adult mode available" : "SFW enforced"}</p>
        <p className="mt-1 text-xs text-zinc-500">Intensity {status?.intensity ?? 0}/3</p>
        {status?.reasons.map((reason) => (
          <p className="mt-2 text-xs text-ember" key={reason}>
            {reason}
          </p>
        ))}
      </div>
      <button className={secondaryButtonClass} onClick={onToggleAgeGate} type="button">
        {user.age_gate_confirmed ? "Age gate confirmed" : "Confirm age gate"}
      </button>
      <div className="grid grid-cols-2 gap-2">
        <label className="block text-sm text-zinc-300">
          Age
          <input
            className={inputClass}
            value={draft.explicit_age}
            onChange={(event) => setDraft({ ...draft, explicit_age: event.target.value })}
            inputMode="numeric"
          />
        </label>
        <label className="block text-sm text-zinc-300">
          Intensity
          <select
            className={inputClass}
            value={draft.content_intensity}
            onChange={(event) => setDraft({ ...draft, content_intensity: event.target.value })}
          >
            <option value="0">0</option>
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3">3</option>
          </select>
        </label>
      </div>
      <label className="flex items-center gap-2 text-sm text-zinc-300">
        <input
          type="checkbox"
          checked={draft.adult_mode_allowed}
          onChange={(event) => setDraft({ ...draft, adult_mode_allowed: event.target.checked })}
        />
        Character adult mode
      </label>
      <button className={primaryButtonClass} onClick={onSave} type="button">
        Save adult settings
      </button>
    </>
  );
}

function SettingsPanel({
  user,
  displayName,
  setDisplayName,
  onSaveName,
  onLogout
}: {
  user: User;
  displayName: string;
  setDisplayName: (value: string) => void;
  onSaveName: () => void;
  onLogout: () => void;
}) {
  return (
    <>
      <p className="rounded-md border border-line bg-ink p-3 text-sm">{user.email}</p>
      <label className="block text-sm text-zinc-300">
        Display name
        <input
          className={inputClass}
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
        />
      </label>
      <button className={primaryButtonClass} onClick={onSaveName} type="button">
        Save settings
      </button>
      <p className="rounded-md border border-line bg-ink p-3 text-xs text-zinc-500">
        API: {getApiBaseUrl()}
      </p>
      <button className={secondaryButtonClass} onClick={onLogout} type="button">
        Logout
      </button>
    </>
  );
}

function DebugPanel({
  debug,
  jobs,
  conversations
}: {
  debug: DebugPayload | null;
  jobs: ScheduledJob[];
  conversations: Conversation[];
}) {
  return (
    <>
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Prompt Preview</h2>
        <p className="text-xs text-zinc-500">
          {debug?.prompt_context?.prompt_version ?? "not loaded"} ·{" "}
          {debug?.prompt_context?.llm_provider ?? "provider unknown"} ·{" "}
          {debug?.prompt_context?.prompt_chars ?? 0} chars
        </p>
        <pre className="max-h-72 overflow-y-auto rounded-md border border-line bg-ink p-3 text-xs leading-5">
          {debug?.prompt_context?.prompt_preview ?? ""}
        </pre>
      </section>
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Jobs</h2>
        {jobs.length === 0 ? <EmptyState text="No jobs." /> : null}
        {jobs.map((job) => (
          <p className="rounded-md border border-line bg-ink p-2 text-xs" key={job.id}>
            {job.job_type} · {job.status} · {formatTimestamp(job.run_at)}
          </p>
        ))}
      </section>
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Conversations</h2>
        {conversations.map((conversation) => (
          <p className="rounded-md border border-line bg-ink p-2 text-xs" key={conversation.id}>
            {conversation.title ?? conversation.id}
          </p>
        ))}
      </section>
    </>
  );
}

function DataPanel({
  onExport,
  onClearMessages,
  onClearMemories,
  onDeleteConversation
}: {
  onExport: () => void;
  onClearMessages: () => void;
  onClearMemories: () => void;
  onDeleteConversation: () => void;
}) {
  return (
    <div className="space-y-3">
      <button className={primaryButtonClass} onClick={onExport} type="button">
        Export JSON
      </button>
      <button className={secondaryButtonClass} onClick={onClearMessages} type="button">
        Clear chat
      </button>
      <button className={secondaryButtonClass} onClick={onClearMemories} type="button">
        Clear memories
      </button>
      <button className={secondaryButtonClass} onClick={onDeleteConversation} type="button">
        Delete conversation
      </button>
    </div>
  );
}

function TagRow({ tags }: { tags: string[] }) {
  if (tags.length === 0) {
    return null;
  }
  return (
    <div className="mt-2 flex flex-wrap gap-1">
      {tags.slice(0, 6).map((tag) => (
        <span className="rounded border border-line px-2 py-1 text-xs text-zinc-400" key={tag}>
          {tag}
        </span>
      ))}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <p className="rounded-md border border-line bg-ink p-3 text-sm text-zinc-500">{text}</p>;
}

function emptyCharacterDraft(): CharacterDraft {
  return {
    name: "",
    description: "",
    personality_core: "",
    speech_style: "",
    explicit_age: "",
    adult_mode_allowed: false,
    content_intensity: "0"
  };
}

function toCharacterDraft(character: Character): CharacterDraft {
  return {
    name: character.name,
    description: character.description ?? "",
    personality_core: character.personality_core ?? "",
    speech_style: character.speech_style ?? "",
    explicit_age: character.explicit_age?.toString() ?? "",
    adult_mode_allowed: character.adult_mode_allowed,
    content_intensity: character.content_intensity.toString()
  };
}

function isMessage(value: unknown): value is Message {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    "role" in value &&
    "content" in value
  );
}

function readError(caught: unknown) {
  if (caught instanceof Error) {
    return caught.message;
  }
  return "The backend did not answer cleanly.";
}

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function formatMetric(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "0.0";
}

function parseDecimal(value: string, fallback: number) {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function tabClass(active: boolean) {
  return `px-2 py-2 text-xs capitalize sm:text-sm ${
    active ? "bg-paper text-ink" : "bg-panel text-zinc-300 hover:bg-ink"
  }`;
}

const inputClass =
  "mt-1 w-full rounded-md border border-line bg-ink px-3 py-2 text-sm text-paper";

const primaryButtonClass =
  "rounded-md bg-paper px-3 py-2 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50";

const secondaryButtonClass =
  "rounded-md border border-line bg-ink px-3 py-2 text-sm text-paper hover:border-zinc-400 disabled:cursor-not-allowed disabled:opacity-50";

const errorClass = "rounded-md border border-amber-700 bg-amber-950 px-3 py-2 text-sm";

const noticeClass = "rounded-md border border-moss bg-lime-950 px-3 py-2 text-sm";
