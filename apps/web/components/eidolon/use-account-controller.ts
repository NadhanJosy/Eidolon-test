"use client";

import { useLayoutEffect, useRef, useState } from "react";

import { apiJson } from "@/lib/api";

import { readError } from "./controller-utils";
import type { Conversation, User } from "./types";

type AccountActionKind = "profile" | "export" | "delete";

type AccountAction = {
  kind: AccountActionKind;
  key: string;
  token: string;
  userId: string;
  userEmail: string;
  sessionGeneration: number;
};

type UserUpdatePayload = Partial<Pick<User, "display_name" | "age_gate_confirmed">>;

type UseAccountControllerArgs = {
  token: string | null;
  user: User | null;
  activeCharacterId: string | null;
  activeConversation: Conversation | null;
  interactionBusy: boolean;
  setUser: (user: User) => void;
  setDisplayName: (value: string) => void;
  setError: (value: string | null) => void;
  setNotice: (value: string | null) => void;
  onAccountDeleted: (notice: string) => void;
  refreshSideState: (
    authToken: string,
    characterId: string,
    conversationId: string,
    shouldApply?: () => boolean
  ) => Promise<void>;
};

type ActivePair = {
  characterId: string;
  conversationId: string;
};

const EXPORT_COLLECTION_KEYS = [
  "characters",
  "conversations",
  "messages",
  "memories",
  "episodic_journals",
  "relationship_states",
  "relationship_events",
  "scheduled_jobs"
] as const;

const FORBIDDEN_EXPORT_KEYS = new Set([
  "access_token",
  "jwt_secret",
  "password_hash",
  "private_key",
  "refresh_token",
  "refresh_token_hash",
  "secret_key",
  "token_hash"
]);

export function useAccountController({
  token,
  user,
  activeCharacterId,
  activeConversation,
  interactionBusy,
  setUser,
  setDisplayName,
  setError,
  setNotice,
  onAccountDeleted,
  refreshSideState
}: UseAccountControllerArgs) {
  const [accountActionId, setAccountActionId] = useState<string | null>(null);
  const actionInFlight = useRef<AccountAction | null>(null);
  const sessionGeneration = useRef(0);
  const sessionUserId = useRef(user?.id ?? null);
  const activePair = useRef<ActivePair | null>(
    toActivePair(activeCharacterId, activeConversation)
  );

  useLayoutEffect(() => {
    const nextUserId = user?.id ?? null;
    if (sessionUserId.current === nextUserId) {
      return;
    }
    sessionUserId.current = nextUserId;
    invalidateAccountActions();
  }, [user?.id]);

  useLayoutEffect(() => {
    activePair.current = toActivePair(activeCharacterId, activeConversation);
  }, [activeCharacterId, activeConversation]);

  function invalidateAccountActions() {
    sessionGeneration.current += 1;
    actionInFlight.current = null;
    setAccountActionId(null);
  }

  function beginAccountAction(kind: AccountActionKind, key: string): AccountAction | null {
    if (!token || !user || interactionBusy || actionInFlight.current) {
      return null;
    }
    const action: AccountAction = {
      kind,
      key,
      token,
      userId: user.id,
      userEmail: user.email,
      sessionGeneration: sessionGeneration.current
    };
    actionInFlight.current = action;
    setAccountActionId(key);
    return action;
  }

  function actionStillApplies(action: AccountAction): boolean {
    return (
      actionInFlight.current === action &&
      sessionUserId.current === action.userId &&
      sessionGeneration.current === action.sessionGeneration
    );
  }

  function finishAccountAction(action: AccountAction) {
    if (actionInFlight.current !== action) {
      return;
    }
    actionInFlight.current = null;
    setAccountActionId(null);
  }

  async function recoverCanonicalUser(
    action: AccountAction,
    payload: UserUpdatePayload
  ): Promise<User | null> {
    if (!actionStillApplies(action)) {
      return null;
    }
    const value = await apiJson<unknown>("/auth/me", { token: action.token });
    if (!isExpectedUser(value, action.userId, action.userEmail, payload)) {
      throw new Error("The saved account profile could not be verified.");
    }
    return actionStillApplies(action) ? value : null;
  }

  async function refreshCurrentCompanion(action: AccountAction): Promise<boolean> {
    for (let attempt = 0; attempt < 2; attempt += 1) {
      if (!actionStillApplies(action)) {
        return false;
      }
      const pair = activePair.current;
      if (pair === null) {
        return true;
      }
      const pairStillApplies = () =>
        actionStillApplies(action) && activePairMatches(activePair.current, pair);
      await refreshSideState(
        action.token,
        pair.characterId,
        pair.conversationId,
        pairStillApplies
      );
      if (!actionStillApplies(action)) {
        return false;
      }
      if (activePairMatches(activePair.current, pair)) {
        return true;
      }
    }
    throw new Error("Companion readiness changed rooms before it could refresh.");
  }

  async function updateUser(payload: UserUpdatePayload): Promise<boolean> {
    let normalizedPayload: UserUpdatePayload;
    try {
      normalizedPayload = normalizeUserUpdate(payload);
    } catch (caught) {
      setError(readError(caught));
      return false;
    }
    const action = beginAccountAction("profile", "profile");
    if (action === null) {
      return false;
    }
    let persisted = false;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>("/auth/me", {
        method: "PATCH",
        body: JSON.stringify(normalizedPayload),
        token: action.token
      });
      persisted = true;
      const updated = isExpectedUser(
        value,
        action.userId,
        action.userEmail,
        normalizedPayload
      )
        ? value
        : await recoverCanonicalUser(action, normalizedPayload);
      if (updated === null || !actionStillApplies(action)) {
        return true;
      }
      setUser(updated);
      if (Object.hasOwn(normalizedPayload, "display_name")) {
        setDisplayName(updated.display_name ?? "");
      }
      try {
        if (!(await refreshCurrentCompanion(action))) {
          return true;
        }
      } catch {
        if (actionStillApplies(action)) {
          setError(
            "Account settings were saved, but companion readiness could not refresh. Reload Eidolon before changing content mode."
          );
        }
        return true;
      }
      if (actionStillApplies(action)) {
        setNotice(accountUpdateNotice(normalizedPayload));
      }
      return true;
    } catch (caught) {
      if (actionStillApplies(action)) {
        setError(
          persisted
            ? "Account settings were saved, but the profile could not be verified. Reload Eidolon before changing account settings again."
            : readError(caught)
        );
      }
      return persisted;
    } finally {
      finishAccountAction(action);
    }
  }

  async function exportAccount(): Promise<boolean> {
    const action = beginAccountAction("export", "export");
    if (action === null || user === null) {
      return false;
    }
    const expectedUser = user;
    let objectUrl: string | null = null;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>("/account/export", { token: action.token });
      if (!isAccountExport(value, expectedUser)) {
        throw new Error(
          "The private export did not pass its ownership and credential-safety checks. No file was created."
        );
      }
      if (!actionStillApplies(action)) {
        return false;
      }
      const serialized = JSON.stringify(value, null, 2);
      const blob = new Blob([serialized], { type: "application/json" });
      objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = `eidolon-export-${value.exported_at.slice(0, 10)}.json`;
      link.hidden = true;
      document.body.append(link);
      try {
        link.click();
      } finally {
        link.remove();
      }
      const completedUrl = objectUrl;
      objectUrl = null;
      window.setTimeout(() => URL.revokeObjectURL(completedUrl), 0);
      if (actionStillApplies(action)) {
        setNotice("Private export ready.");
      }
      return true;
    } catch (caught) {
      if (objectUrl !== null) {
        URL.revokeObjectURL(objectUrl);
      }
      if (actionStillApplies(action)) {
        setError(readError(caught));
      }
      return false;
    } finally {
      finishAccountAction(action);
    }
  }

  async function deleteAccount(password: string, confirmation: string): Promise<boolean> {
    if (!password || password.length > 256 || confirmation !== "DELETE MY ACCOUNT") {
      setError("Enter the current password and exact account deletion phrase.");
      return false;
    }
    const action = beginAccountAction("delete", "delete");
    if (action === null) {
      return false;
    }
    let accepted = false;
    setError(null);
    setNotice(null);
    try {
      const value = await apiJson<unknown>("/account", {
        method: "DELETE",
        body: JSON.stringify({ password, confirmation }),
        token: action.token
      });
      accepted = true;
      if (!actionStillApplies(action)) {
        return true;
      }
      onAccountDeleted(
        isPositiveDeleteCount(value)
          ? "Account deleted."
          : "Account deletion was accepted. Your local session is closed."
      );
      return true;
    } catch (caught) {
      if (actionStillApplies(action)) {
        setError(readError(caught));
      }
      return accepted;
    } finally {
      finishAccountAction(action);
    }
  }

  return {
    state: {
      accountActionId,
      accountMutating: accountActionId !== null
    },
    actions: {
      updateUser,
      exportAccount,
      deleteAccount,
      resetAccount: invalidateAccountActions
    }
  };
}

function normalizeUserUpdate(payload: UserUpdatePayload): UserUpdatePayload {
  const normalized: UserUpdatePayload = {};
  if (Object.hasOwn(payload, "display_name")) {
    const displayName = payload.display_name;
    if (displayName !== null && typeof displayName !== "string") {
      throw new Error("Display name must be text or blank.");
    }
    if (displayName === null) {
      normalized.display_name = null;
    } else {
      if (/\p{Cc}|\p{Cf}/u.test(displayName)) {
        throw new Error("Display name cannot contain control characters.");
      }
      const compact = displayName.trim().replace(/\s+/gu, " ");
      if (compact.length > 120) {
        throw new Error("Keep the display name to 120 characters or fewer.");
      }
      normalized.display_name = compact || null;
    }
  }
  if (Object.hasOwn(payload, "age_gate_confirmed")) {
    if (typeof payload.age_gate_confirmed !== "boolean") {
      throw new Error("The account age gate must be confirmed or removed explicitly.");
    }
    normalized.age_gate_confirmed = payload.age_gate_confirmed;
  }
  if (!Object.hasOwn(normalized, "display_name") && !Object.hasOwn(normalized, "age_gate_confirmed")) {
    throw new Error("Choose an account setting to update.");
  }
  return normalized;
}

function isExpectedUser(
  value: unknown,
  userId: string,
  userEmail: string,
  payload: UserUpdatePayload
): value is User {
  if (!isUser(value, userId, userEmail)) {
    return false;
  }
  if (
    Object.hasOwn(payload, "display_name") &&
    value.display_name !== payload.display_name
  ) {
    return false;
  }
  return (
    !Object.hasOwn(payload, "age_gate_confirmed") ||
    value.age_gate_confirmed === payload.age_gate_confirmed
  );
}

function isUser(value: unknown, userId: string, userEmail: string): value is User {
  return (
    isRecord(value) &&
    value.id === userId &&
    value.email === userEmail &&
    (value.display_name === null ||
      (typeof value.display_name === "string" && value.display_name.length <= 120)) &&
    typeof value.age_gate_confirmed === "boolean" &&
    isTimestamp(value.created_at)
  );
}

type ValidAccountExport = Record<string, unknown> & {
  exported_at: string;
};

function isAccountExport(value: unknown, expectedUser: User): value is ValidAccountExport {
  if (!isRecord(value) || !isTimestamp(value.exported_at) || containsForbiddenExportKey(value)) {
    return false;
  }
  const exportUser = value.user;
  if (
    !isRecord(exportUser) ||
    exportUser.id !== expectedUser.id ||
    exportUser.email !== expectedUser.email ||
    exportUser.display_name !== expectedUser.display_name ||
    exportUser.age_gate_confirmed !== expectedUser.age_gate_confirmed ||
    !isTimestamp(exportUser.created_at)
  ) {
    return false;
  }
  for (const key of EXPORT_COLLECTION_KEYS) {
    if (!Array.isArray(value[key]) || !value[key].every(isRecord)) {
      return false;
    }
  }
  const characters = value.characters as Record<string, unknown>[];
  const conversations = value.conversations as Record<string, unknown>[];
  const messages = value.messages as Record<string, unknown>[];
  const memories = value.memories as Record<string, unknown>[];
  const journals = value.episodic_journals as Record<string, unknown>[];
  const relationships = value.relationship_states as Record<string, unknown>[];
  const relationshipEvents = value.relationship_events as Record<string, unknown>[];
  const jobs = value.scheduled_jobs as Record<string, unknown>[];
  if (!recordsHaveUniqueIds(characters) || !recordsHaveUniqueIds(conversations)) {
    return false;
  }
  const characterIds = new Set(characters.map((item) => item.id as string));
  const conversationIds = new Set(conversations.map((item) => item.id as string));
  return (
    conversations.every(
      (item) => isNonemptyString(item.id) && characterIds.has(asString(item.character_id))
    ) &&
    messages.every(
      (item) => isNonemptyString(item.id) && conversationIds.has(asString(item.conversation_id))
    ) &&
    memories.every(
      (item) =>
        isNonemptyString(item.id) &&
        item.user_id === expectedUser.id &&
        characterIds.has(asString(item.character_id))
    ) &&
    journals.every(
      (item) =>
        isNonemptyString(item.id) &&
        item.user_id === expectedUser.id &&
        characterIds.has(asString(item.character_id)) &&
        (item.conversation_id === null ||
          conversationIds.has(asString(item.conversation_id)))
    ) &&
    relationships.every(
      (item) =>
        isNonemptyString(item.id) &&
        item.user_id === expectedUser.id &&
        characterIds.has(asString(item.character_id))
    ) &&
    relationshipEvents.every(
      (item) =>
        isNonemptyString(item.id) &&
        item.user_id === expectedUser.id &&
        characterIds.has(asString(item.character_id))
    ) &&
    jobs.every(
      (item) =>
        isNonemptyString(item.id) &&
        item.user_id === expectedUser.id &&
        (item.character_id === null || characterIds.has(asString(item.character_id)))
    )
  );
}

function recordsHaveUniqueIds(records: Record<string, unknown>[]): boolean {
  const ids = records.map((item) => item.id);
  return ids.every(isNonemptyString) && new Set(ids).size === ids.length;
}

function containsForbiddenExportKey(value: unknown): boolean {
  const pending: unknown[] = [value];
  let visited = 0;
  while (pending.length > 0) {
    const current = pending.pop();
    visited += 1;
    if (visited > 1_000_000) {
      return true;
    }
    if (Array.isArray(current)) {
      for (const child of current) {
        pending.push(child);
      }
      continue;
    }
    if (!isRecord(current)) {
      continue;
    }
    for (const [key, child] of Object.entries(current)) {
      if (FORBIDDEN_EXPORT_KEYS.has(key.toLowerCase())) {
        return true;
      }
      pending.push(child);
    }
  }
  return false;
}

function isPositiveDeleteCount(value: unknown): value is { deleted: number } {
  return (
    isRecord(value) &&
    typeof value.deleted === "number" &&
    Number.isInteger(value.deleted) &&
    value.deleted >= 1
  );
}

function toActivePair(
  characterId: string | null,
  conversation: Conversation | null
): ActivePair | null {
  if (!characterId || !conversation || conversation.character_id !== characterId) {
    return null;
  }
  return { characterId, conversationId: conversation.id };
}

function activePairMatches(current: ActivePair | null, expected: ActivePair): boolean {
  return (
    current?.characterId === expected.characterId &&
    current.conversationId === expected.conversationId
  );
}

function accountUpdateNotice(payload: UserUpdatePayload): string {
  if (payload.age_gate_confirmed === true) {
    return "Account age gate confirmed.";
  }
  if (payload.age_gate_confirmed === false) {
    return "Account age gate removed. Safe mode is active.";
  }
  return payload.display_name === null ? "Account name cleared." : "Account name saved.";
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonemptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && !Number.isNaN(Date.parse(value));
}
