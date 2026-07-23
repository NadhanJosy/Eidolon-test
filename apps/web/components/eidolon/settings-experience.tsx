"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";
import { useState } from "react";

import { resolvedDeviceTimeZone } from "./character-builder-model";
import { Field, PageHeading, PrimaryButton, QuietButton, Toggle, fieldClass } from "./experience-primitives";
import { Icon } from "./icons";
import type { AdultReadinessState, AdultStatus, CharacterDraft, ContentMode, ConversationPrivacyMode, User } from "./types";

type SettingsSection = "companion" | "presence" | "privacy" | "account";

export function SettingsExperience({
  user,
  characterName,
  draft,
  setDraft,
  characterSaving,
  displayName,
  setDisplayName,
  accountActionId,
  contentMode,
  adultStatus,
  adultReadinessState,
  adultModeAvailable,
  privacyMode,
  streaming,
  messageCount,
  memoryCount,
  conversationCount,
  deletingConversationId,
  onSaveCharacter,
  onSaveName,
  onToggleAgeGate,
  onChangeContentMode,
  onSetPrivacyMode,
  onExport,
  onClearMessages,
  onClearMemories,
  onClearAdultContinuity,
  onDeleteConversation,
  onDeleteAccount,
  onLogout
}: {
  user: User;
  characterName: string;
  draft: CharacterDraft;
  setDraft: (draft: CharacterDraft) => void;
  characterSaving: boolean;
  displayName: string;
  setDisplayName: (value: string) => void;
  accountActionId: string | null;
  contentMode: ContentMode;
  adultStatus: AdultStatus | null;
  adultReadinessState: AdultReadinessState;
  adultModeAvailable: boolean;
  privacyMode: ConversationPrivacyMode;
  streaming: boolean;
  messageCount: number;
  memoryCount: number;
  conversationCount: number;
  deletingConversationId: string | null;
  onSaveCharacter: () => Promise<boolean>;
  onSaveName: () => void;
  onToggleAgeGate: () => void;
  onChangeContentMode: (mode: ContentMode) => void;
  onSetPrivacyMode: (mode: ConversationPrivacyMode) => void;
  onExport: () => Promise<boolean>;
  onClearMessages: () => Promise<boolean>;
  onClearMemories: () => Promise<boolean>;
  onClearAdultContinuity: () => void;
  onDeleteConversation: () => Promise<boolean>;
  onDeleteAccount: (password: string, confirmation: string) => Promise<boolean>;
  onLogout: () => void;
}) {
  const [section, setSection] = useState<SettingsSection>("companion");
  const update = <K extends keyof CharacterDraft>(field: K, value: CharacterDraft[K]) => setDraft({ ...draft, [field]: value });

  return (
    <div className="mx-auto w-full max-w-6xl px-5 pb-28 pt-8 sm:px-8 sm:pt-12 lg:px-12">
      <PageHeading
        description="Shape how your companion feels, what may be remembered, when they can reach out, and the private boundaries around your account."
        eyebrow="Your space, your terms"
        title="Settings"
      />

      <div className="mt-9 grid gap-8 lg:grid-cols-[14rem_minmax(0,1fr)] lg:gap-12">
        <nav aria-label="Settings sections" className="grid grid-cols-2 gap-2 lg:block lg:space-y-1">
          <SettingsTab active={section === "companion"} icon="user" label={characterName} onClick={() => setSection("companion")} />
          <SettingsTab active={section === "presence"} icon="moon" label="Presence & timing" onClick={() => setSection("presence")} />
          <SettingsTab active={section === "privacy"} icon="shield" label="Privacy & consent" onClick={() => setSection("privacy")} />
          <SettingsTab active={section === "account"} icon="settings" label="Account" onClick={() => setSection("account")} />
        </nav>

        <div className="min-w-0">
          {section === "companion" ? <CompanionSettings draft={draft} saving={characterSaving} update={update} onSave={onSaveCharacter} /> : null}
          {section === "presence" ? <PresenceSettings draft={draft} saving={characterSaving} update={update} onSave={onSaveCharacter} /> : null}
          {section === "privacy" ? <PrivacySettings adultModeAvailable={adultModeAvailable} adultReadinessState={adultReadinessState} adultStatus={adultStatus} characterName={characterName} contentMode={contentMode} draft={draft} privacyMode={privacyMode} replaceDraft={setDraft} saving={characterSaving} update={update} user={user} onChangeContentMode={onChangeContentMode} onClearAdultContinuity={onClearAdultContinuity} onSave={onSaveCharacter} onSetPrivacyMode={onSetPrivacyMode} onToggleAgeGate={onToggleAgeGate} /> : null}
          {section === "account" ? <AccountSettings accountActionId={accountActionId} conversationCount={conversationCount} deletingConversationId={deletingConversationId} displayName={displayName} memoryCount={memoryCount} messageCount={messageCount} setDisplayName={setDisplayName} streaming={streaming} user={user} onClearMemories={onClearMemories} onClearMessages={onClearMessages} onDeleteAccount={onDeleteAccount} onDeleteConversation={onDeleteConversation} onExport={onExport} onLogout={onLogout} onSaveName={onSaveName} /> : null}
        </div>
      </div>
    </div>
  );
}

function CompanionSettings({ draft, saving, update, onSave }: SettingsFormProps) {
  const themes = [
    { id: "ember", label: "Ember", color: "bg-[#9b5e46]" },
    { id: "cedar", label: "Cedar", color: "bg-[#777355]" },
    { id: "rain", label: "Rain", color: "bg-[#53696c]" },
    { id: "plum", label: "Plum", color: "bg-[#76586a]" }
  ];
  return (
    <SettingsPanel eyebrow="Companion" title="Their presence" description="These details guide a point of view and a way of speaking. They are not a script; the relationship still grows through conversation.">
      <div className="grid gap-5 sm:grid-cols-2"><Field label="Name"><input className={fieldClass} maxLength={120} onChange={(event) => update("name", event.target.value)} value={draft.name} /></Field><Field label="Relationship expectation"><input className={fieldClass} maxLength={2000} onChange={(event) => update("relationship_type", event.target.value)} value={draft.relationship_type} /></Field></div>
      <fieldset><legend className="text-sm font-medium text-[#d8cec3]">Room tone</legend><div className="mt-3 grid grid-cols-4 gap-2">{themes.map((theme) => <button aria-pressed={draft.visual_theme === theme.id} className={`flex min-h-12 items-center gap-2 rounded-2xl border px-3 text-xs transition ${draft.visual_theme === theme.id ? "border-white/[0.22] bg-white/[0.07] text-[#e2d7cc]" : "border-white/[0.08] text-[#837b73] hover:border-white/[0.16]"}`} key={theme.id} onClick={() => update("visual_theme", theme.id)} type="button"><span className={`h-3 w-3 rounded-full ${theme.color}`} /><span className="hidden sm:inline">{theme.label}</span></button>)}</div></fieldset>
      <Field label="Appearance & impression"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={2000} onChange={(event) => update("appearance", event.target.value)} value={draft.appearance} /></Field>
      <Field label="Atmosphere"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={2000} onChange={(event) => update("description", event.target.value)} value={draft.description} /></Field>
      <Field label="Personality"><textarea className={`${fieldClass} min-h-32 resize-none`} maxLength={4000} onChange={(event) => update("personality_core", event.target.value)} value={draft.personality_core} /></Field>
      <div className="grid gap-5 sm:grid-cols-2"><Field label="Flaws"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={2000} onChange={(event) => update("flaws", event.target.value)} value={draft.flaws} /></Field><Field label="Values"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={2000} onChange={(event) => update("values", event.target.value)} value={draft.values} /></Field></div>
      <Field label="Communication style"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={2000} onChange={(event) => update("speech_style", event.target.value)} value={draft.speech_style} /></Field>
      <div className="grid gap-5 sm:grid-cols-2"><Field label="Humour"><input className={fieldClass} maxLength={2000} onChange={(event) => update("humor_style", event.target.value)} value={draft.humor_style} /></Field><Field label="Interests"><input className={fieldClass} maxLength={2000} onChange={(event) => update("interests", event.target.value)} value={draft.interests} /></Field></div>
      <Field label="The greeting at the start of a new conversation"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={600} onChange={(event) => update("greeting", event.target.value)} value={draft.greeting} /></Field>
      <details className="group rounded-[1.5rem] border border-white/[0.08] bg-white/[0.018] p-5">
        <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-4"><span><span className="block text-sm text-[#d0c5ba]">Refine their inner life</span><span className="mt-1 block text-xs text-[#756e67]">Worldview, temperament, affection, conflict, initiative, and shared context</span></span><Icon className="h-4 w-4 text-[#8f7c71] transition group-open:rotate-180" name="chevron-down" /></summary>
        <div className="mt-6 grid gap-5 border-t border-white/[0.07] pt-6 sm:grid-cols-2">
          <Field label="Worldview"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={2000} onChange={(event) => update("worldview", event.target.value)} value={draft.worldview} /></Field>
          <Field label="Emotional temperament"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={2000} onChange={(event) => update("temperament", event.target.value)} value={draft.temperament} /></Field>
          <Field label="How they show care"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={1600} onChange={(event) => update("affection_style", event.target.value)} value={draft.affection_style} /></Field>
          <Field label="Conflict and repair"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={1600} onChange={(event) => update("conflict_style", event.target.value)} value={draft.conflict_style} /></Field>
          <Field label="Initiative"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={1600} onChange={(event) => update("initiative_style", event.target.value)} value={draft.initiative_style} /></Field>
          <Field label="Conversational habits"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={1600} onChange={(event) => update("habits", event.target.value)} value={draft.habits} /></Field>
          <div className="sm:col-span-2"><Field label="Backstory"><textarea className={`${fieldClass} min-h-28 resize-none`} maxLength={4000} onChange={(event) => update("backstory", event.target.value)} value={draft.backstory} /></Field></div>
          <div className="sm:col-span-2"><Field label="Usual shared atmosphere"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={4000} onChange={(event) => update("scenario_preset", event.target.value)} value={draft.scenario_preset} /></Field></div>
        </div>
      </details>
      <SaveRow saving={saving} onSave={onSave} />
    </SettingsPanel>
  );
}

function PresenceSettings({ draft, saving, update, onSave }: SettingsFormProps) {
  const muted = draft.muted_proactive_categories;
  return (
    <SettingsPanel eyebrow="Presence" title="When they may reach out" description="Contextual in-app notes can follow a promise, reminder, routine, or meaningful open thread. A timer by itself is never enough.">
      <SettingGroup>
        <Toggle checked={draft.proactive_enabled} detail="Opting out cancels every pending note immediately." label="Allow companion-initiated notes" onChange={(checked) => update("proactive_enabled", checked)} />
        <div className="py-4">
          <p className="text-sm text-[#d2c7bc]">Delivery channel</p>
          <p className="mt-1 text-xs leading-5 text-[#777068]">In-app inbox only. No browser or lock-screen notification receives conversation details.</p>
        </div>
        <Toggle checked={draft.allow_inactivity_checkins} disabled={!draft.proactive_enabled} detail="Only when a meaningful saved thread supports the check-in." label="Contextual check-ins" onChange={(checked) => update("allow_inactivity_checkins", checked)} />
        <Toggle checked={draft.allow_thinking_of_you} disabled={!draft.proactive_enabled} detail="Use a grounded shared moment as a specific callback." label="Remembered callbacks" onChange={(checked) => update("allow_thinking_of_you", checked)} />
        <Toggle checked={draft.allow_milestone_notes} disabled={!draft.proactive_enabled} detail="Acknowledge dates and landmarks in your shared story." label="Milestone notes" onChange={(checked) => update("allow_milestone_notes", checked)} />
        <Toggle checked={draft.allow_unresolved_thread_nudges} disabled={!draft.proactive_enabled} detail="Includes explicit follow-ups, reminders, and contextual suggestions." label="Open threads and reminders" onChange={(checked) => update("allow_unresolved_thread_nudges", checked)} />
        <Toggle checked={draft.allow_delayed_double_texts} disabled={!draft.proactive_enabled} detail="At most one compact queued thought, still subject to context and caps." label="Delayed follow-up thoughts" onChange={(checked) => update("allow_delayed_double_texts", checked)} />
      </SettingGroup>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Frequency">
          <select className={fieldClass} onChange={(event) => update("proactive_frequency", event.target.value as CharacterDraft["proactive_frequency"])} value={draft.proactive_frequency}>
            <option value="minimal">Minimal</option><option value="balanced">Balanced</option><option value="frequent">More often</option>
          </select>
        </Field>
        <Field label="Maximum notes per local day">
          <select className={fieldClass} onChange={(event) => update("proactive_daily_cap", event.target.value)} value={draft.proactive_daily_cap}>
            <option value="1">One</option><option value="2">Two</option><option value="3">Three</option>
          </select>
        </Field>
      </div>
      <div className="grid gap-5 sm:grid-cols-2"><Field hint="IANA name" label="Your timezone"><div className="flex gap-2"><input className={fieldClass} maxLength={80} onChange={(event) => update("proactive_timezone", event.target.value)} value={draft.proactive_timezone} /><QuietButton onClick={() => update("proactive_timezone", resolvedDeviceTimeZone())}>Use device</QuietButton></div></Field><Field label="Minimum time between notes"><select className={fieldClass} onChange={(event) => update("proactive_cooldown_hours", event.target.value)} value={draft.proactive_cooldown_hours}><option value="8">8 hours</option><option value="12">12 hours</option><option value="24">A day</option><option value="48">Two days</option><option value="72">Three days</option><option value="168">A week</option></select></Field></div>
      <div className="grid gap-5 sm:grid-cols-2"><Field label="Quiet hours begin"><input className={fieldClass} onChange={(event) => update("quiet_hours_start", event.target.value)} type="time" value={draft.quiet_hours_start} /></Field><Field label="Quiet hours end"><input className={fieldClass} onChange={(event) => update("quiet_hours_end", event.target.value)} type="time" value={draft.quiet_hours_end} /></Field></div>
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-4">
        <p className="text-sm text-[#d2c7bc]">Pause all notes</p>
        <p className="mt-1 text-xs text-[#777068]">{draft.proactive_snoozed_until ? `Paused until ${formatPresencePause(draft.proactive_snoozed_until)}.` : "No pause is active."}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <QuietButton onClick={() => update("proactive_snoozed_until", presencePauseFromNow(24))}>Pause 24 hours</QuietButton>
          <QuietButton onClick={() => update("proactive_snoozed_until", presencePauseFromNow(168))}>Pause a week</QuietButton>
          {draft.proactive_snoozed_until ? <QuietButton onClick={() => update("proactive_snoozed_until", "")}>Resume</QuietButton> : null}
        </div>
      </div>
      <SettingGroup>
        <Toggle checked={draft.allow_morning_notes} disabled={!draft.proactive_enabled} label="Morning notes" onChange={(checked) => update("allow_morning_notes", checked)} />
        {draft.allow_morning_notes ? <Field label="Around"><input className={fieldClass} onChange={(event) => update("morning_time", event.target.value)} type="time" value={draft.morning_time} /></Field> : null}
        <Toggle checked={draft.allow_goodnight_notes} disabled={!draft.proactive_enabled} label="Goodnight notes" onChange={(checked) => update("allow_goodnight_notes", checked)} />
        {draft.allow_goodnight_notes ? <Field label="Around"><input className={fieldClass} onChange={(event) => update("goodnight_time", event.target.value)} type="time" value={draft.goodnight_time} /></Field> : null}
      </SettingGroup>
      {muted.length > 0 ? (
        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-4">
          <p className="text-sm text-[#d2c7bc]">Muted from inbox feedback</p>
          <p className="mt-1 text-xs text-[#777068]">{muted.map((item) => item.replaceAll("_", " ")).join(", ")}</p>
          <div className="mt-3"><QuietButton onClick={() => update("muted_proactive_categories", [])}>Unmute all</QuietButton></div>
        </div>
      ) : null}
      <SaveRow saving={saving} onSave={onSave} />
    </SettingsPanel>
  );
}

function presencePauseFromNow(hours: number): string {
  return new Date(Date.now() + hours * 60 * 60 * 1000).toISOString();
}

function formatPresencePause(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "the saved time" : parsed.toLocaleString();
}

function PrivacySettings({ user, characterName, draft, saving, contentMode, privacyMode, adultStatus, adultReadinessState, adultModeAvailable, update, replaceDraft, onToggleAgeGate, onChangeContentMode, onSetPrivacyMode, onClearAdultContinuity, onSave }: SettingsFormProps & { user: User; characterName: string; contentMode: ContentMode; privacyMode: ConversationPrivacyMode; adultStatus: AdultStatus | null; adultReadinessState: AdultReadinessState; adultModeAvailable: boolean; replaceDraft: (draft: CharacterDraft) => void; onToggleAgeGate: () => void; onChangeContentMode: (mode: ContentMode) => void; onSetPrivacyMode: (mode: ConversationPrivacyMode) => void; onClearAdultContinuity: () => void }) {
  const adultAge = Number.parseInt(draft.explicit_age, 10);
  const adultAgeReady = Number.isInteger(adultAge) && adultAge >= 18;
  const reasons = adultStatus?.reasons.filter((reason) => reason.trim()) ?? [];
  const adultContinuityCount =
    (adultStatus?.stored_memory_count ?? 0) + (adultStatus?.stored_moment_count ?? 0);
  return (
    <SettingsPanel eyebrow="Privacy & consent" title="Clear boundaries, kept privately" description="Control what becomes part of continuity and, if you choose, unlock a separate adult space with explicit age and consent gates.">
      <SettingGroup>
        <Toggle checked={draft.remember_preferences} detail={`Allow ${characterName} to remember stable preferences and meaningful details.`} label="Remember what matters" onChange={(checked) => update("remember_preferences", checked)} />
        <Toggle checked={draft.remember_emotional_notes} detail="Let emotional patterns shape tone and future callbacks." label="Remember emotional context" onChange={(checked) => update("remember_emotional_notes", checked)} />
        <div className="py-4"><Field label="How long ordinary details should stay" hint="Boundaries, pinned memories, and reinforced patterns stay protected in every mode."><select className={fieldClass} onChange={(event) => update("retention_mode", event.target.value as CharacterDraft["retention_mode"])} value={draft.retention_mode}><option value="minimal">Keep only the clearest details</option><option value="balanced">Let quiet details soften naturally</option><option value="long_lived">Give ordinary details more time</option></select></Field></div>
        <Toggle checked={draft.private_mode_default} detail="New conversations stay outside memory and relationship changes unless you choose otherwise." label="Begin new conversations privately" onChange={(checked) => update("private_mode_default", checked)} />
        <Toggle checked={privacyMode === "private"} detail="This conversation remains visible to you, but it won’t shape memories, moments, or the relationship." label="Keep the current conversation separate" onChange={(checked) => onSetPrivacyMode(checked ? "private" : "normal")} />
      </SettingGroup>

      <div className="rounded-[1.75rem] border border-white/[0.08] bg-[radial-gradient(circle_at_90%_0%,rgba(169,105,75,0.09),transparent_42%),rgba(255,255,255,0.018)] p-5 sm:p-7">
        <div className="flex items-start gap-4"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-[#b98265]/20 bg-[#b98265]/[0.07] text-[#b98265]"><Icon className="h-4 w-4" name="lock" /></span><div><p className="text-xs uppercase tracking-[0.17em] text-[#8e7a6f]">Private intimacy</p><h3 className="mt-2 font-eidolon-display text-2xl">Adult consent settings</h3><p className="mt-3 text-xs leading-5 text-[#80776f]">Optional, private, and never assumed. Hard safety boundaries remain in place regardless of these choices.</p></div></div>
        <div className="mt-7 divide-y divide-white/[0.07]">
          <Toggle checked={user.age_gate_confirmed} detail="Confirm that you, the account holder, are 18 or older." label="I am an adult" onChange={onToggleAgeGate} />
          <div className="grid gap-4 py-4 sm:grid-cols-2"><Field label={`${characterName}’s explicit age`}><input className={fieldClass} inputMode="numeric" maxLength={3} onChange={(event) => { const value = event.target.value; const age = Number.parseInt(value, 10); replaceDraft({ ...draft, explicit_age: value, ...(Number.isInteger(age) && age >= 18 ? {} : { adult_mode_allowed: false, content_intensity: "0", adult_memory_storage: false }) }); }} placeholder="18 or older" value={draft.explicit_age} /></Field><div className="self-end"><Toggle checked={draft.adult_mode_allowed} disabled={!adultAgeReady} detail={adultAgeReady ? "Allow the consent gates to evaluate for this companion." : "Set an explicit adult age first."} label="Eligible for adult conversations" onChange={(checked) => replaceDraft({ ...draft, adult_mode_allowed: checked, ...(checked ? {} : { content_intensity: "0", adult_memory_storage: false }) })} /></div></div>
          <Field label="How consent should be handled"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={4000} onChange={(event) => update("consent_style", event.target.value)} value={draft.consent_style} /></Field>
          <div className="grid gap-5 py-4 sm:grid-cols-2"><Field label="Soft boundaries"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={4000} onChange={(event) => update("soft_limits", event.target.value)} value={draft.soft_limits} /></Field><Field label="Hard boundaries"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={4000} onChange={(event) => update("hard_limits", event.target.value)} value={draft.hard_limits} /></Field></div>
          <Field label="How to return to calm"><textarea className={`${fieldClass} min-h-20 resize-none`} maxLength={4000} onChange={(event) => update("aftercare_style", event.target.value)} value={draft.aftercare_style} /></Field>
          <div className="py-4"><Field label="Preferred intensity"><select className={fieldClass} disabled={!draft.adult_mode_allowed} onChange={(event) => update("content_intensity", event.target.value)} value={draft.content_intensity}><option value="0">Off</option><option value="1">Tender</option><option value="2">Open</option><option value="3">Expressive</option></select></Field></div>
          <Toggle checked={draft.adult_memory_storage} disabled={!draft.adult_mode_allowed || draft.private_mode_default} detail={draft.private_mode_default ? "Private-by-default conversations never enter durable memory." : "Off by default. Intimate details can remain conversation-only."} label="Allow intimate memory" onChange={(checked) => update("adult_memory_storage", checked)} />
          <div className="flex flex-col gap-4 py-4 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm text-[#c8bdb2]">Separate intimate continuity</p><p className="mt-1 text-xs leading-5 text-[#766f68]">{adultContinuityCount === 0 ? "Nothing is stored in the adult-only archive." : `${adultStatus?.stored_memory_count ?? 0} adult-only memories and ${adultStatus?.stored_moment_count ?? 0} private moments. They never enter everyday recall or notes later.`}</p></div><DangerButton disabled={adultContinuityCount === 0} onClick={onClearAdultContinuity}>Remove intimate continuity</DangerButton></div>
        </div>
        {adultReadinessState === "error" ? <p className="mt-4 rounded-xl bg-[#7e3f34]/10 p-3 text-xs leading-5 text-[#c58e82]">Readiness could not be checked, so the safe setting remains active.</p> : null}
        {reasons.length > 0 && !adultModeAvailable ? <ul className="mt-4 space-y-1 text-xs leading-5 text-[#887c73]">{reasons.map((reason) => <li className="flex gap-2" key={reason}><span aria-hidden="true">·</span><span>{humanAdultReason(reason)}</span></li>)}</ul> : null}
        <div className="mt-6 flex flex-col gap-3 border-t border-white/[0.07] pt-5 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm text-[#c8bdb2]">Conversation tone</p><p className="mt-1 text-xs text-[#766f68]">Changed here, never in the main header.</p></div><div className="grid grid-cols-2 rounded-full border border-white/[0.09] p-1"><button aria-pressed={contentMode === "sfw"} className={`min-h-11 rounded-full px-4 py-2 text-xs ${contentMode === "sfw" ? "bg-white/[0.09] text-[#ded3c8]" : "text-[#746d66]"}`} onClick={() => onChangeContentMode("sfw")} type="button">Everyday</button><button aria-pressed={contentMode === "adult"} className={`min-h-11 rounded-full px-4 py-2 text-xs ${contentMode === "adult" ? "bg-[#b98265]/15 text-[#d8ab93]" : "text-[#746d66]"}`} disabled={!adultModeAvailable} onClick={() => onChangeContentMode("adult")} type="button">Adult</button></div></div>
      </div>
      <SaveRow saving={saving} onSave={onSave} />
    </SettingsPanel>
  );
}

function AccountSettings({ user, displayName, setDisplayName, accountActionId, streaming, messageCount, memoryCount, conversationCount, deletingConversationId, onSaveName, onExport, onClearMessages, onClearMemories, onDeleteConversation, onDeleteAccount, onLogout }: { user: User; displayName: string; setDisplayName: (value: string) => void; accountActionId: string | null; streaming: boolean; messageCount: number; memoryCount: number; conversationCount: number; deletingConversationId: string | null; onSaveName: () => void; onExport: () => Promise<boolean>; onClearMessages: () => Promise<boolean>; onClearMemories: () => Promise<boolean>; onDeleteConversation: () => Promise<boolean>; onDeleteAccount: (password: string, confirmation: string) => Promise<boolean>; onLogout: () => void }) {
  const [cleanup, setCleanup] = useState("");
  const [password, setPassword] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const clearConversationReady = messageCount > 0 && cleanup === "CLEAR CONVERSATION";
  const clearMemoriesReady = memoryCount > 0 && cleanup === "CLEAR MEMORIES";
  const deleteConversationReady = conversationCount > 0 && cleanup === "DELETE CONVERSATION";
  const deleteAccountReady = password.length > 0 && deleteConfirmation === "DELETE MY ACCOUNT";
  return (
    <SettingsPanel eyebrow="Account" title="Your private space" description="Manage how you are addressed, take a copy of your data, or remove parts of the story. Destructive choices always require a deliberate phrase.">
      <div className="rounded-[1.5rem] border border-white/[0.08] bg-white/[0.02] p-5"><p className="text-sm text-[#d0c5ba]">{user.email}</p><p className="mt-1 text-xs text-[#756e67]">Your local private account</p></div>
      <Field label="What your companion calls you"><div className="flex gap-2"><input className={fieldClass} maxLength={120} onChange={(event) => setDisplayName(event.target.value)} value={displayName} /><PrimaryButton disabled={accountActionId !== null} onClick={onSaveName}>{accountActionId === "profile" ? "Saving…" : "Save"}</PrimaryButton></div></Field>
      <SettingGroup><div className="flex flex-col gap-4 py-2 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm text-[#d0c5ba]">Take your story with you</p><p className="mt-1 text-xs leading-5 text-[#756e67]">Download your conversations, memories, moments, companion profiles, and relationship history.</p></div><QuietButton disabled={streaming || accountActionId !== null} onClick={() => void onExport()}>{accountActionId === "export" ? "Preparing…" : "Export my data"}</QuietButton></div><div className="flex flex-col gap-4 py-2 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm text-[#d0c5ba]">Leave this device</p><p className="mt-1 text-xs text-[#756e67]">Your private data stays with your account.</p></div><QuietButton onClick={onLogout}>Sign out</QuietButton></div></SettingGroup>

      <details className="group rounded-[1.5rem] border border-[#ad675a]/15 bg-[#6c3028]/[0.04] p-5"><summary className="flex cursor-pointer list-none items-center justify-between"><span><span className="block text-sm text-[#d2aaa1]">Remove parts of your story</span><span className="mt-1 block text-xs text-[#806d68]">These choices cannot be undone.</span></span><Icon className="h-4 w-4 text-[#916c63] transition group-open:rotate-180" name="chevron-down" /></summary><div className="mt-6 space-y-4 border-t border-[#ad675a]/10 pt-5"><Field label="Confirmation phrase" hint="Use CLEAR CONVERSATION, CLEAR MEMORIES, or DELETE CONVERSATION"><input className={fieldClass} onChange={(event) => setCleanup(event.target.value)} value={cleanup} /></Field><div className="grid gap-2 sm:grid-cols-3"><DangerButton disabled={streaming || !clearConversationReady} onClick={() => void onClearMessages()}>Clear this conversation</DangerButton><DangerButton disabled={streaming || !clearMemoriesReady} onClick={() => void onClearMemories()}>Clear all memories</DangerButton><DangerButton disabled={streaming || !deleteConversationReady} onClick={() => void onDeleteConversation()}>{deletingConversationId ? "Deleting…" : "Delete conversation"}</DangerButton></div></div></details>

      <details className="group rounded-[1.5rem] border border-[#ad675a]/15 bg-[#6c3028]/[0.04] p-5"><summary className="flex cursor-pointer list-none items-center justify-between"><span><span className="block text-sm text-[#d2aaa1]">Delete your account</span><span className="mt-1 block text-xs text-[#806d68]">Permanently removes your entire private space.</span></span><Icon className="h-4 w-4 text-[#916c63] transition group-open:rotate-180" name="chevron-down" /></summary><div className="mt-6 grid gap-4 border-t border-[#ad675a]/10 pt-5 sm:grid-cols-2"><Field label="Current password"><input autoComplete="current-password" className={fieldClass} maxLength={256} onChange={(event) => setPassword(event.target.value)} type="password" value={password} /></Field><Field label="Type DELETE MY ACCOUNT"><input className={fieldClass} maxLength={17} onChange={(event) => setDeleteConfirmation(event.target.value)} value={deleteConfirmation} /></Field><DangerButton className="sm:col-span-2" disabled={streaming || !deleteAccountReady || accountActionId !== null} onClick={() => void onDeleteAccount(password, deleteConfirmation)}>{accountActionId === "delete" ? "Deleting your space…" : "Delete my account permanently"}</DangerButton></div></details>
    </SettingsPanel>
  );
}

function SettingsTab({ active, icon, label, onClick }: { active: boolean; icon: "moon" | "settings" | "shield" | "user"; label: string; onClick: () => void }) { return <button aria-current={active ? "page" : undefined} className={`flex min-h-11 shrink-0 items-center gap-3 rounded-2xl px-3 py-3 text-left text-sm transition lg:w-full lg:rounded-xl lg:px-4 ${active ? "bg-white/[0.075] text-[#e0d5ca]" : "text-[#807870] hover:bg-white/[0.035] hover:text-[#b7ada3]"}`} onClick={onClick} type="button"><Icon className={`h-4 w-4 shrink-0 ${active ? "text-[#b98265]" : ""}`} name={icon} /><span className="min-w-0 leading-4 lg:truncate">{label}</span></button>; }
function SettingsPanel({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children: ReactNode }) { return <section className="reveal-up"><p className="text-xs uppercase tracking-[0.18em] text-[#91786b]">{eyebrow}</p><h2 className="mt-3 font-eidolon-display text-4xl">{title}</h2><p className="mt-4 max-w-2xl text-sm leading-6 text-[#8c837b]">{description}</p><div className="mt-8 space-y-6">{children}</div></section>; }
function SettingGroup({ children }: { children: ReactNode }) { return <div className="divide-y divide-white/[0.07] rounded-[1.5rem] border border-white/[0.08] bg-white/[0.018] px-5 py-2">{children}</div>; }
type SettingsFormProps = { draft: CharacterDraft; saving: boolean; update: <K extends keyof CharacterDraft>(field: K, value: CharacterDraft[K]) => void; onSave: () => Promise<boolean> };
function SaveRow({ saving, onSave }: { saving: boolean; onSave: () => Promise<boolean> }) { return <div className="flex justify-end border-t border-white/[0.08] pt-6"><PrimaryButton disabled={saving} onClick={() => void onSave()}>{saving ? "Saving…" : "Save changes"}</PrimaryButton></div>; }
function DangerButton({ children, className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement>) { return <button className={`min-h-11 rounded-full border border-[#b66859]/25 bg-[#77362c]/10 px-4 text-xs text-[#cc9488] transition hover:border-[#c47b6c]/45 hover:bg-[#77362c]/20 disabled:cursor-not-allowed disabled:opacity-35 ${className}`} type="button" {...props}>{children}</button>; }
function humanAdultReason(reason: string): string { return reason.replace(/sfw/gi, "everyday mode").replace(/character/gi, "companion").replace(/^./, (letter) => letter.toUpperCase()); }
