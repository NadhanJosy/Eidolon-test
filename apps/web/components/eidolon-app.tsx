"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { ApiError, apiErrorFromResponse, apiFetch, apiJson, getApiBaseUrl } from "@/lib/api";

type AuthMode = "login" | "register";
type Panel = "character" | "memory" | "debug" | "export";
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
};

type Conversation = {
  id: string;
  character_id: string;
  title: string | null;
};

type Message = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

type MemoryItem = {
  id: string;
  memory_type: string;
  content: string;
  confidence: number;
  created_at: string;
};

type Relationship = {
  trust: number;
  intimacy: number;
  warmth: number;
  tension: number;
  familiarity: number;
  attachment: number;
};

const relationshipMetrics = [
  "trust",
  "intimacy",
  "warmth",
  "tension",
  "familiarity",
  "attachment"
] as const;

type ScheduledJob = {
  id: string;
  job_type: string;
  status: string;
  run_at: string;
};

type DebugPayload = {
  prompt_context?: {
    prompt_version: string;
    content_mode: string;
    prompt: string;
  };
};

type CharacterDraft = {
  name: string;
  description: string;
  personality_core: string;
  speech_style: string;
  explicit_age: string;
  adult_mode_allowed: boolean;
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
  attachment: 0
};

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
  const [characterDraft, setCharacterDraft] = useState({
    name: "",
    description: "",
    personality_core: "",
    speech_style: "",
    explicit_age: "",
    adult_mode_allowed: false
  });
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [messageDraft, setMessageDraft] = useState("");
  const [streamingContent, setStreamingContent] = useState("");
  const [contentMode, setContentMode] = useState<ContentMode>("sfw");

  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [memoryDraft, setMemoryDraft] = useState("");
  const [relationship, setRelationship] = useState<Relationship>(emptyRelationship);
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [debug, setDebug] = useState<DebugPayload | null>(null);
  const [panel, setPanel] = useState<Panel>("character");

  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const activeCharacterId = activeCharacter?.id ?? activeConversation?.character_id ?? null;

  useEffect(() => {
    if (token && !user) {
      void bootstrap(token);
    }
    // The bootstrap function intentionally reads the latest state setters only.
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
    const [memoryResult, relationshipResult, debugResult, jobsResult] = await Promise.allSettled([
      apiJson<MemoryItem[]>(`/characters/${characterId}/memories`, { token: authToken }),
      apiJson<Relationship>(`/characters/${characterId}/relationship`, { token: authToken }),
      apiJson<DebugPayload>(`/debug/character/${characterId}`, { token: authToken }),
      apiJson<ScheduledJob[]>("/debug/jobs", { token: authToken })
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
    await loadConversation(authToken, conversationId);
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !activeConversation || !activeCharacterId || !messageDraft.trim()) {
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
          adult_mode_allowed: characterDraft.adult_mode_allowed
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

  async function toggleAgeGate() {
    if (!token || !user) {
      return;
    }
    setError(null);
    const updated = await apiJson<User>("/auth/me", {
      method: "PATCH",
      body: JSON.stringify({ age_gate_confirmed: !user.age_gate_confirmed }),
      token
    });
    setUser(updated);
  }

  async function addMemory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !activeCharacterId || !memoryDraft.trim()) {
      return;
    }
    setError(null);
    await apiJson<MemoryItem>(`/characters/${activeCharacterId}/memories`, {
      method: "POST",
      body: JSON.stringify({
        memory_type: "preference",
        content: memoryDraft.trim(),
        confidence: 0.8
      }),
      token
    });
    setMemoryDraft("");
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
    setNotice(message ? "Queued." : "Cooldown active.");
    await refreshSideState(token, activeCharacterId, activeConversation.id);
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
  }

  function setCurrentCharacter(character: Character) {
    setActiveCharacter(character);
    setCharacterDraft(toCharacterDraft(character));
  }

  if (!user || !token) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-ink px-4 py-8 text-paper">
        <section className="w-full max-w-sm border border-line bg-panel p-5 shadow-xl">
          <div className="mb-5 flex items-center justify-between">
            <h1 className="text-2xl font-semibold">Eidolon</h1>
            <div className="flex border border-line">
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
            {error ? <p className="border border-amber-700 bg-amber-950 p-3 text-sm">{error}</p> : null}
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
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-zinc-500">Eidolon</p>
            <h1 className="text-xl font-semibold">{activeCharacter?.name ?? "Conversation"}</h1>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="border border-line px-3 py-2 text-zinc-300">
              {user.display_name ?? user.email}
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

      <div className="mx-auto grid max-w-7xl gap-4 px-4 py-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="flex min-h-[calc(100vh-112px)] flex-col border border-line bg-panel">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <div>
              <h2 className="text-base font-medium">{activeConversation?.title ?? "Chat"}</h2>
              <p className="text-xs text-zinc-500">{sortedMessages.length} messages</p>
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
              <p className="text-sm text-zinc-500">No messages yet.</p>
            ) : null}
            {sortedMessages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {streamingContent ? (
              <div className="max-w-[82%] border border-line bg-ink px-3 py-2">
                <p className="whitespace-pre-wrap text-sm leading-6">{streamingContent}</p>
                <p className="mt-2 text-xs text-zinc-500">Streaming</p>
              </div>
            ) : null}
          </div>

          <form className="border-t border-line p-3" onSubmit={sendMessage}>
            {error ? (
              <p className="mb-2 border border-amber-700 bg-amber-950 px-3 py-2 text-sm">{error}</p>
            ) : null}
            {notice ? (
              <p className="mb-2 border border-moss bg-lime-950 px-3 py-2 text-sm">{notice}</p>
            ) : null}
            <div className="flex gap-2">
              <textarea
                value={messageDraft}
                onChange={(event) => setMessageDraft(event.target.value)}
                className="min-h-12 flex-1 resize-none rounded-md border border-line bg-ink px-3 py-2 text-sm"
                placeholder="Write a message"
                disabled={sending}
              />
              <button
                className="rounded-md bg-paper px-4 py-2 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50"
                disabled={sending || !messageDraft.trim()}
                type="submit"
              >
                {sending ? "..." : "Send"}
              </button>
            </div>
          </form>
        </section>

        <aside className="border border-line bg-panel">
          <div className="grid grid-cols-4 border-b border-line text-sm">
            {(["character", "memory", "debug", "export"] as Panel[]).map((item) => (
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
                user={user}
                relationship={relationship}
                onSave={saveCharacter}
                onToggleAgeGate={toggleAgeGate}
              />
            ) : null}
            {panel === "memory" ? (
              <MemoryPanel
                memories={memories}
                draft={memoryDraft}
                setDraft={setMemoryDraft}
                onAdd={addMemory}
              />
            ) : null}
            {panel === "debug" ? (
              <DebugPanel debug={debug} jobs={jobs} conversations={conversations} />
            ) : null}
            {panel === "export" ? <ExportPanel onExport={exportAccount} /> : null}
          </div>
        </aside>
      </div>
    </main>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <article className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[82%] border px-3 py-2 ${
          isUser ? "border-tide bg-cyan-950" : "border-line bg-ink"
        }`}
      >
        <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
        <p className="mt-2 text-xs text-zinc-500">
          {message.role} · {formatTimestamp(message.created_at)}
        </p>
      </div>
    </article>
  );
}

function toCharacterDraft(character: Character): CharacterDraft {
  return {
    name: character.name,
    description: character.description ?? "",
    personality_core: character.personality_core ?? "",
    speech_style: character.speech_style ?? "",
    explicit_age: character.explicit_age?.toString() ?? "",
    adult_mode_allowed: character.adult_mode_allowed
  };
}

function CharacterPanel({
  draft,
  setDraft,
  user,
  relationship,
  onSave,
  onToggleAgeGate
}: {
  draft: CharacterDraft;
  setDraft: (value: CharacterDraft) => void;
  user: User;
  relationship: Relationship;
  onSave: () => void;
  onToggleAgeGate: () => void;
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
        <label className="flex items-end gap-2 pb-2 text-sm text-zinc-300">
          <input
            type="checkbox"
            checked={draft.adult_mode_allowed}
            onChange={(event) =>
              setDraft({ ...draft, adult_mode_allowed: event.target.checked })
            }
          />
          Adult mode
        </label>
      </div>
      <div className="flex gap-2">
        <button className={primaryButtonClass} onClick={onSave} type="button">
          Save
        </button>
        <button className={secondaryButtonClass} onClick={onToggleAgeGate} type="button">
          {user.age_gate_confirmed ? "Age gate on" : "Age gate off"}
        </button>
      </div>
      <dl className="grid grid-cols-2 gap-2 text-sm">
        {relationshipMetrics.map((key) => (
          <div className="border border-line p-2" key={key}>
            <dt className="text-zinc-500">{key}</dt>
            <dd className="font-mono">{formatMetric(relationship[key])}</dd>
          </div>
        ))}
      </dl>
    </>
  );
}

function MemoryPanel({
  memories,
  draft,
  setDraft,
  onAdd
}: {
  memories: MemoryItem[];
  draft: string;
  setDraft: (value: string) => void;
  onAdd: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <>
      <form className="flex gap-2" onSubmit={onAdd}>
        <input
          className={inputClass}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Memory"
        />
        <button className={primaryButtonClass} type="submit">
          Add
        </button>
      </form>
      <div className="space-y-2">
        {memories.length === 0 ? <p className="text-sm text-zinc-500">No memories.</p> : null}
        {memories.map((memory) => (
          <article className="border border-line p-3 text-sm" key={memory.id}>
            <p>{memory.content}</p>
            <p className="mt-2 text-xs text-zinc-500">
              {memory.memory_type} · {memory.confidence.toFixed(1)} ·{" "}
              {formatTimestamp(memory.created_at)}
            </p>
          </article>
        ))}
      </div>
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
        <h2 className="text-sm font-semibold">Prompt</h2>
        <p className="text-xs text-zinc-500">
          {debug?.prompt_context?.prompt_version ?? "not loaded"}
        </p>
        <pre className="max-h-72 overflow-y-auto border border-line bg-ink p-3 text-xs leading-5">
          {debug?.prompt_context?.prompt ?? ""}
        </pre>
      </section>
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Jobs</h2>
        {jobs.length === 0 ? <p className="text-sm text-zinc-500">No jobs.</p> : null}
        {jobs.map((job) => (
          <p className="border border-line p-2 text-xs" key={job.id}>
            {job.job_type} · {job.status} · {formatTimestamp(job.run_at)}
          </p>
        ))}
      </section>
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Conversations</h2>
        {conversations.map((conversation) => (
          <p className="border border-line p-2 text-xs" key={conversation.id}>
            {conversation.title ?? conversation.id}
          </p>
        ))}
      </section>
    </>
  );
}

function ExportPanel({ onExport }: { onExport: () => void }) {
  return (
    <div className="space-y-3">
      <button className={primaryButtonClass} onClick={onExport} type="button">
        Export JSON
      </button>
    </div>
  );
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

function tabClass(active: boolean) {
  return `px-3 py-2 text-sm capitalize ${
    active ? "bg-paper text-ink" : "bg-panel text-zinc-300 hover:bg-ink"
  }`;
}

const inputClass =
  "mt-1 w-full rounded-md border border-line bg-ink px-3 py-2 text-sm text-paper";

const primaryButtonClass =
  "rounded-md bg-paper px-3 py-2 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50";

const secondaryButtonClass =
  "rounded-md border border-line bg-ink px-3 py-2 text-sm text-paper hover:border-zinc-400 disabled:cursor-not-allowed disabled:opacity-50";
