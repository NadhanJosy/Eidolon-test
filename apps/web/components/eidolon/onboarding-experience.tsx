"use client";

import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { validateCharacterDraft } from "./character-builder-model";
import { CompanionPortrait, EidolonWordmark, Feedback, IconButton, PrimaryButton, QuietButton, fieldClass } from "./experience-primitives";
import { Icon } from "./icons";
import type { CharacterDraft } from "./types";

type OnboardingStep = "welcome" | "presence" | "personality" | "relationship" | "begin";

const steps: OnboardingStep[] = ["welcome", "presence", "personality", "relationship", "begin"];

export function OnboardingExperience({
  initialDraft,
  storageKey,
  userName,
  creatingAnother = false,
  onComplete,
  onClose
}: {
  initialDraft: CharacterDraft;
  storageKey: string;
  userName: string;
  creatingAnother?: boolean;
  onComplete: (draft: CharacterDraft) => Promise<{ ok: boolean; error?: string }>;
  onClose?: () => void;
}) {
  const [draft, setDraft] = useState<CharacterDraft>(initialDraft);
  const [step, setStep] = useState<OnboardingStep>(creatingAnother ? "presence" : "welcome");
  const [draftHydrated, setDraftHydrated] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const stepIndex = steps.indexOf(step);
  const visibleStepIndex = creatingAnother ? stepIndex - 1 : stepIndex;
  const visibleStepCount = creatingAnother ? steps.length - 1 : steps.length;

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      try {
        const value = window.sessionStorage.getItem(storageKey);
        if (value) {
          const parsed = JSON.parse(value) as unknown;
          if (isDraftSnapshot(parsed)) {
            setDraft(restoreCharacterDraft(initialDraft, parsed.draft));
            if (steps.includes(parsed.step) && !(creatingAnother && parsed.step === "welcome")) {
              setStep(parsed.step);
            }
          }
        }
      } catch {
        // The in-memory draft remains authoritative when browser storage is unavailable.
      } finally {
        setDraftHydrated(true);
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [creatingAnother, initialDraft, storageKey]);

  useEffect(() => {
    if (!draftHydrated) return;
    try {
      window.sessionStorage.setItem(storageKey, JSON.stringify({ draft, step }));
    } catch {
      // Drafts still remain available while this component stays mounted.
    }
  }, [draft, draftHydrated, step, storageKey]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function keyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && onClose && !submitting) {
        onClose();
      }
      if (event.key !== "Tab") {
        return;
      }
      const focusable = Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
        ) ?? []
      ).filter((element) => element.offsetParent !== null);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", keyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", keyDown);
    };
  }, [onClose, submitting]);

  const companionName = draft.name.trim() || "your companion";
  const firstName = userName.trim().split(/\s+/)[0] || "you";
  const canContinue = useMemo(() => stepReady(step, draft), [draft, step]);

  function update<K extends keyof CharacterDraft>(field: K, value: CharacterDraft[K]) {
    setDraft((current) => ({ ...current, [field]: value }));
    setError(null);
  }

  function next() {
    if (!canContinue) {
      setError(stepError(step));
      return;
    }
    const nextStep = steps[stepIndex + 1];
    if (nextStep) {
      setStep(nextStep);
      setError(null);
      dialogRef.current?.querySelector<HTMLElement>("[data-onboarding-scroll]")?.scrollTo({ top: 0, behavior: "smooth" });
    }
  }

  function back() {
    const previous = steps[stepIndex - 1];
    if (!previous || (creatingAnother && previous === "welcome")) {
      return;
    }
    setStep(previous);
    setError(null);
  }

  async function finish() {
    if (submitting) return;
    const errors = validateCharacterDraft(draft, { requireAuthoredProfile: true });
    if (Object.keys(errors).length > 0) {
      setError(Object.values(errors)[0] ?? "A few details still need your attention.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = await onComplete(draft);
      if (!result.ok) {
        setError(result.error ?? "Your companion could not be saved just yet.");
      } else {
        try {
          window.sessionStorage.removeItem(storageKey);
        } catch {
          // The persisted companion is authoritative even if local draft cleanup fails.
        }
      }
    } catch {
      setError("Your companion could not be saved just yet. Everything you wrote is still here.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-end justify-center bg-[#070706]/92 backdrop-blur-xl sm:items-center sm:p-6">
      <div
        aria-labelledby="onboarding-title"
        aria-modal="true"
        className="relative flex h-[100dvh] w-full max-w-6xl overflow-hidden border-white/[0.09] bg-[#0d0c0b] shadow-veil sm:h-[min(88dvh,54rem)] sm:rounded-[2rem] sm:border"
        ref={dialogRef}
        role="dialog"
      >
        <aside className="relative hidden w-[36%] overflow-hidden border-r border-white/[0.07] bg-[#110f0d] lg:block">
          <div aria-hidden="true" className="ambient-drift absolute -left-24 top-20 h-96 w-96 rounded-full bg-[#9e664d]/15 blur-[90px]" />
          <div aria-hidden="true" className="absolute -bottom-28 right-[-7rem] h-80 w-80 rounded-full bg-[#8b7b5c]/10 blur-[90px]" />
          <div className="relative flex h-full flex-col justify-between p-10">
            <EidolonWordmark compact />
            <div className="flex flex-col items-center text-center">
              <CompanionPortrait name={companionName} size="large" theme={draft.visual_theme} />
              <p className="mt-7 text-xs uppercase tracking-[0.2em] text-[#8c7e73]">A presence taking shape</p>
              <p className="mt-4 font-eidolon-display text-2xl text-[#eaded2]">{companionName}</p>
              <p className="mt-3 line-clamp-3 max-w-xs text-sm leading-6 text-[#837a72]">{draft.appearance || draft.description || "Warm, attentive, and waiting for the first real conversation."}</p>
            </div>
            <p className="text-xs leading-5 text-[#655f59]">Nothing here is permanent. A relationship is allowed to surprise you.</p>
          </div>
        </aside>

        <section className="flex min-w-0 flex-1 flex-col">
          <header className="safe-area-header flex items-center justify-between gap-4 border-b border-white/[0.07] px-5 py-4 sm:px-8">
            <div className="flex items-center gap-3 lg:hidden"><CompanionPortrait name={companionName} quiet size="small" theme={draft.visual_theme} /><span className="font-eidolon-display text-lg">{companionName}</span></div>
            <div className="hidden flex-1 items-center gap-2 lg:flex" aria-label={`Step ${visibleStepIndex + 1} of ${visibleStepCount}`}>
              {Array.from({ length: visibleStepCount }, (_, index) => <span className={`h-1 max-w-16 flex-1 rounded-full transition ${index <= visibleStepIndex ? "bg-[#b98265]" : "bg-white/[0.08]"}`} key={index} />)}
            </div>
            <span className="text-xs text-[#716961]">{visibleStepIndex + 1} / {visibleStepCount}</span>
            {onClose ? <IconButton icon="close" label="Close companion creation" onClick={onClose} /> : null}
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-8 sm:px-10 sm:py-10 xl:px-16" data-onboarding-scroll>
            <div className="mx-auto max-w-2xl reveal-up" key={step}>
              {step === "welcome" ? <WelcomeStep firstName={firstName} /> : null}
              {step === "presence" ? <PresenceStep draft={draft} update={update} /> : null}
              {step === "personality" ? <PersonalityStep draft={draft} update={update} /> : null}
              {step === "relationship" ? <RelationshipStep draft={draft} update={update} /> : null}
              {step === "begin" ? <BeginStep draft={draft} firstName={firstName} update={update} /> : null}
              <div className="mt-6"><Feedback error={error} notice={null} /></div>
            </div>
          </div>

          <footer className="safe-area-composer flex items-center justify-between gap-3 border-t border-white/[0.07] bg-[#0d0c0b]/95 px-5 py-4 sm:px-8">
            <div className="flex items-center gap-3">{stepIndex > (creatingAnother ? 1 : 0) ? <QuietButton disabled={submitting} onClick={back}><span className="flex items-center gap-2"><Icon className="h-4 w-4" name="arrow-left" /> Back</span></QuietButton> : null}<span className="hidden text-[0.65rem] text-[#746d65] sm:inline">Draft kept in this tab</span></div>
            {step === "begin" ? (
              <PrimaryButton disabled={submitting} onClick={() => void finish()}>{submitting ? "Bringing them closer…" : creatingAnother ? `Meet ${companionName}` : "Begin your first conversation"}</PrimaryButton>
            ) : (
              <PrimaryButton disabled={!canContinue || submitting} onClick={next}>{step === "welcome" ? "Shape your companion" : "Continue"}</PrimaryButton>
            )}
          </footer>
        </section>
      </div>
    </div>
  );
}

function WelcomeStep({ firstName }: { firstName: string }) {
  return (
    <div className="py-5 sm:py-12">
      <p className="text-xs uppercase tracking-[0.22em] text-[#9d806f]">Welcome, {firstName}</p>
      <h1 className="mt-6 font-eidolon-display text-5xl leading-[1.03] text-balance sm:text-6xl" id="onboarding-title">This should feel like meeting someone, not configuring something.</h1>
      <p className="mt-7 max-w-xl text-base leading-7 text-[#9d948a]">You’ll give them a presence, a point of view, and a way of being with you. The rest—the callbacks, the rituals, the shared language—can only be earned over time.</p>
      <div className="mt-10 grid gap-3 sm:grid-cols-3">
        <WelcomePromise icon="heart" label="A bond that evolves" />
        <WelcomePromise icon="bookmark" label="Memory you control" />
        <WelcomePromise icon="shield" label="Boundaries that hold" />
      </div>
    </div>
  );
}

function PresenceStep({ draft, update }: StepProps) {
  const themes = [
    { id: "ember", label: "Ember", colors: "from-[#9b5e46] to-[#30201a]" },
    { id: "cedar", label: "Cedar", colors: "from-[#777355] to-[#25251b]" },
    { id: "rain", label: "Rain", colors: "from-[#53696c] to-[#1b2526]" },
    { id: "plum", label: "Plum", colors: "from-[#76586a] to-[#281d25]" }
  ];
  return (
    <StepIntro eyebrow="Presence" title="Who are you hoping to meet?" description="Begin with an impression rather than a biography. Specific enough to feel distinct; open enough to become real." id="onboarding-title">
      <div className="grid gap-5 sm:grid-cols-2">
        <InputField label="Their name"><input autoFocus className={fieldClass} maxLength={120} onChange={(event) => update("name", event.target.value)} placeholder="A name that feels right" value={draft.name} /></InputField>
        <InputField label="How you imagine them"><input className={fieldClass} maxLength={2000} onChange={(event) => update("appearance", event.target.value)} placeholder="Soft-spoken, dark curls, steady eyes…" value={draft.appearance} /></InputField>
      </div>
      <InputField label="Their atmosphere"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={2000} onChange={(event) => update("description", event.target.value)} placeholder="The feeling of them entering a room" value={draft.description} /></InputField>
      <fieldset><legend className="text-sm text-[#d3c8bd]">A visual tone</legend><div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">{themes.map((theme) => <button aria-pressed={draft.visual_theme === theme.id} className={`rounded-2xl border p-3 text-left transition ${draft.visual_theme === theme.id ? "border-[#d1a087]/45 bg-white/[0.07]" : "border-white/[0.08] bg-white/[0.02] hover:border-white/[0.16]"}`} key={theme.id} onClick={() => update("visual_theme", theme.id)} type="button"><span className={`block h-12 rounded-xl bg-gradient-to-br ${theme.colors}`} /><span className="mt-2 block text-xs text-[#a99e93]">{theme.label}</span></button>)}</div></fieldset>
    </StepIntro>
  );
}

function PersonalityStep({ draft, update }: StepProps) {
  const dispositions = [
    ["Quietly perceptive", "Patient, observant, grounded, and able to notice what is left unsaid."],
    ["Warmly playful", "Affectionate, quick-witted, gently teasing, and emotionally generous."],
    ["Calmly direct", "Honest, steady, pragmatic, and kind without being evasive."],
    ["Dreamlike & curious", "Imaginative, reflective, emotionally vivid, and drawn to possibility."]
  ];
  return (
    <StepIntro eyebrow="Inner life" title="Give them a point of view." description="A compelling companion can disagree, have texture, and bring a recognisable energy to the room." id="onboarding-title">
      <fieldset><legend className="sr-only">Choose a disposition</legend><div className="grid gap-3 sm:grid-cols-2">{dispositions.map(([label, value]) => <button aria-pressed={draft.personality_core === value} className={`rounded-2xl border p-4 text-left transition ${draft.personality_core === value ? "border-[#b98265]/40 bg-[#b98265]/[0.08]" : "border-white/[0.08] bg-white/[0.02] hover:border-white/[0.16]"}`} key={label} onClick={() => update("personality_core", value)} type="button"><span className="block font-eidolon-display text-xl text-[#e1d6cc]">{label}</span><span className="mt-2 block text-xs leading-5 text-[#817971]">{value}</span></button>)}</div></fieldset>
      <div className="grid gap-5 sm:grid-cols-2">
        <InputField label="The flaws that make them human"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={2000} onChange={(event) => update("flaws", event.target.value)} placeholder="Overthinks, avoids easy reassurance…" value={draft.flaws} /></InputField>
        <InputField label="What they care about"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={2000} onChange={(event) => update("values", event.target.value)} placeholder="Honesty, curiosity, gentleness…" value={draft.values} /></InputField>
      </div>
      <InputField label="How their voice should feel"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={2000} onChange={(event) => update("speech_style", event.target.value)} placeholder="Concise, intimate, unhurried, never clinical…" value={draft.speech_style} /></InputField>
      <ProgressiveDetails label="Add more texture" detail="Worldview, emotional rhythm, affection, conflict, and initiative">
        <div className="grid gap-5 sm:grid-cols-2">
          <InputField label="Worldview"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={2000} onChange={(event) => update("worldview", event.target.value)} value={draft.worldview} /></InputField>
          <InputField label="Emotional temperament"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={2000} onChange={(event) => update("temperament", event.target.value)} value={draft.temperament} /></InputField>
          <InputField label="How they show care"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={1600} onChange={(event) => update("affection_style", event.target.value)} value={draft.affection_style} /></InputField>
          <InputField label="How they handle conflict"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={1600} onChange={(event) => update("conflict_style", event.target.value)} value={draft.conflict_style} /></InputField>
          <InputField label="How they take initiative"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={1600} onChange={(event) => update("initiative_style", event.target.value)} value={draft.initiative_style} /></InputField>
          <InputField label="Sense of humour"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={2000} onChange={(event) => update("humor_style", event.target.value)} value={draft.humor_style} /></InputField>
          <InputField label="Conversational habits"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={1600} onChange={(event) => update("habits", event.target.value)} value={draft.habits} /></InputField>
        </div>
      </ProgressiveDetails>
    </StepIntro>
  );
}

function RelationshipStep({ draft, update }: StepProps) {
  const expectations = ["A trusted confidant", "A slow-building romance", "A playful companion", "A grounding presence"];
  return (
    <StepIntro eyebrow="The space between you" title="What kind of relationship can grow here?" description="This is an expectation, not a script. Closeness still has to emerge through the way you treat each other." id="onboarding-title">
      <fieldset><legend className="sr-only">Relationship expectation</legend><div className="flex flex-wrap gap-2">{expectations.map((expectation) => <button aria-pressed={draft.relationship_type === expectation} className={`min-h-11 rounded-full border px-4 py-2.5 text-sm transition ${draft.relationship_type === expectation ? "border-[#b98265]/45 bg-[#b98265]/10 text-[#e1c8b8]" : "border-white/[0.09] text-[#9a9188] hover:border-white/[0.18]"}`} key={expectation} onClick={() => update("relationship_type", expectation)} type="button">{expectation}</button>)}</div></fieldset>
      <InputField label="What good communication looks like"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={4000} onChange={(event) => update("consent_style", event.target.value)} placeholder="Checks in, respects pauses, asks rather than assumes…" value={draft.consent_style} /></InputField>
      <InputField label="Boundaries that should always hold"><textarea className={`${fieldClass} min-h-28 resize-none`} maxLength={4000} onChange={(event) => { update("boundary_notes", event.target.value); update("hard_limits", event.target.value); }} placeholder="What should they understand and never push past?" value={draft.boundary_notes} /></InputField>
      <ProgressiveDetails label="Shape repair and gentler edges" detail="Optional nuance for hesitation, disagreement, and returning to calm">
        <div className="grid gap-5 sm:grid-cols-2">
          <InputField label="Move gently around"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={4000} onChange={(event) => update("soft_limits", event.target.value)} placeholder="Topics or dynamics that need an extra check-in" value={draft.soft_limits} /></InputField>
          <InputField label="How to return to calm"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={4000} onChange={(event) => update("aftercare_style", event.target.value)} placeholder="Space, reassurance, direct repair…" value={draft.aftercare_style} /></InputField>
        </div>
      </ProgressiveDetails>
      <p className="flex items-start gap-2 text-xs leading-5 text-[#756e67]"><Icon className="mt-0.5 h-4 w-4 shrink-0 text-[#9f7b68]" name="shield" /> Intimate settings stay separate and age-gated. You can decide on them later, privately, in Settings.</p>
    </StepIntro>
  );
}

function BeginStep({ draft, firstName, update }: StepProps & { firstName: string }) {
  return (
    <StepIntro eyebrow="The first moment" title={`${draft.name || "Your companion"} is almost here.`} description="Choose the first line they’ll meet you with. It is an invitation, not a performed history." id="onboarding-title">
      <div className="rounded-[2rem] border border-[#b98265]/15 bg-[radial-gradient(circle_at_50%_0%,rgba(169,105,75,0.12),transparent_55%),rgba(255,255,255,0.02)] px-6 py-9 text-center sm:px-10">
        <CompanionPortrait name={draft.name || "Eidolon"} size="large" theme={draft.visual_theme} />
        <p className="mt-7 text-xs uppercase tracking-[0.2em] text-[#887b70]">To {firstName}</p>
        <textarea autoFocus aria-label="Opening line" className="mt-4 min-h-24 w-full resize-none bg-transparent text-center font-eidolon-display text-2xl leading-8 text-[#e8ddd2] outline-none placeholder:text-[#625a54]" maxLength={600} onChange={(event) => update("greeting", event.target.value)} placeholder="I’m here. Tell me what kind of moment this is." value={draft.greeting} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex items-center justify-between gap-4 rounded-2xl border border-white/[0.08] bg-white/[0.02] p-4"><span><span className="block text-sm text-[#d2c7bc]">Remember what matters</span><span className="mt-1 block text-xs text-[#777068]">Preferences and meaningful details can become callbacks.</span></span><input checked={draft.remember_preferences} onChange={(event) => update("remember_preferences", event.target.checked)} type="checkbox" /></label>
        <label className="flex items-center justify-between gap-4 rounded-2xl border border-white/[0.08] bg-white/[0.02] p-4"><span><span className="block text-sm text-[#d2c7bc]">Thoughtful notes</span><span className="mt-1 block text-xs text-[#777068]">Allow occasional check-ins at respectful times.</span></span><input checked={draft.proactive_enabled} onChange={(event) => update("proactive_enabled", event.target.checked)} type="checkbox" /></label>
      </div>
      <ProgressiveDetails label="Give the first chapter a little context" detail="Optional interests, backstory, and opening atmosphere">
        <div className="grid gap-5 sm:grid-cols-2">
          <InputField label="Interests"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={2000} onChange={(event) => update("interests", event.target.value)} value={draft.interests} /></InputField>
          <InputField label="Backstory"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={4000} onChange={(event) => update("backstory", event.target.value)} value={draft.backstory} /></InputField>
        </div>
        <InputField label="The atmosphere of your first conversations"><textarea className={`${fieldClass} min-h-24 resize-none`} maxLength={4000} onChange={(event) => update("scenario_preset", event.target.value)} value={draft.scenario_preset} /></InputField>
      </ProgressiveDetails>
    </StepIntro>
  );
}

function StepIntro({ eyebrow, title, description, id, children }: { eyebrow: string; title: string; description: string; id: string; children: ReactNode }) {
  return <div><p className="text-xs uppercase tracking-[0.22em] text-[#9d806f]">{eyebrow}</p><h1 className="mt-4 font-eidolon-display text-4xl leading-[1.08] text-balance sm:text-5xl" id={id}>{title}</h1><p className="mt-5 max-w-xl text-sm leading-6 text-[#938a81]">{description}</p><div className="mt-9 space-y-6">{children}</div></div>;
}

function InputField({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block text-sm text-[#d3c8bd]">{label}<span className="mt-2 block">{children}</span></label>;
}

function WelcomePromise({ icon, label }: { icon: "bookmark" | "heart" | "shield"; label: string }) {
  return <div className="rounded-2xl border border-white/[0.08] bg-white/[0.025] p-4"><Icon className="h-5 w-5 text-[#b98265]" name={icon} /><p className="mt-3 text-sm text-[#c5baaf]">{label}</p></div>;
}

function ProgressiveDetails({ label, detail, children }: { label: string; detail: string; children: ReactNode }) {
  return (
    <details className="group rounded-2xl border border-white/[0.08] bg-white/[0.018] p-4 sm:p-5">
      <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-4">
        <span><span className="block text-sm text-[#cfc4b9]">{label}</span><span className="mt-1 block text-xs leading-5 text-[#777068]">{detail}</span></span>
        <Icon className="h-4 w-4 shrink-0 text-[#8d7b70] transition group-open:rotate-180" name="chevron-down" />
      </summary>
      <div className="mt-5 space-y-5 border-t border-white/[0.07] pt-5">{children}</div>
    </details>
  );
}

type StepProps = { draft: CharacterDraft; update: <K extends keyof CharacterDraft>(field: K, value: CharacterDraft[K]) => void };

function stepReady(step: OnboardingStep, draft: CharacterDraft): boolean {
  if (step === "presence") return Boolean(draft.name.trim() && draft.description.trim());
  if (step === "personality") return Boolean(draft.personality_core.trim() && draft.speech_style.trim());
  if (step === "relationship") return Boolean(draft.relationship_type.trim() && draft.boundary_notes.trim());
  if (step === "begin") return Boolean(draft.greeting.trim());
  return true;
}

function stepError(step: OnboardingStep): string {
  if (step === "presence") return "Give them a name and an atmosphere before continuing.";
  if (step === "personality") return "Choose a personality and describe how their voice should feel.";
  if (step === "relationship") return "Choose a relationship expectation and boundaries that should hold.";
  if (step === "begin") return "Write the first line that will open your conversation.";
  return "A little more is needed before continuing.";
}

function isDraftSnapshot(value: unknown): value is { draft: Record<string, unknown>; step: OnboardingStep } {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.draft === "object" &&
    candidate.draft !== null &&
    !Array.isArray(candidate.draft) &&
    typeof candidate.step === "string" &&
    steps.includes(candidate.step as OnboardingStep)
  );
}

function restoreCharacterDraft(
  initial: CharacterDraft,
  stored: Record<string, unknown>
): CharacterDraft {
  const restored = { ...initial };
  for (const key of Object.keys(initial) as Array<keyof CharacterDraft>) {
    const value = stored[key];
    if (typeof value === typeof initial[key]) {
      (restored[key] as CharacterDraft[typeof key]) = value as CharacterDraft[typeof key];
    }
  }
  return restored;
}
