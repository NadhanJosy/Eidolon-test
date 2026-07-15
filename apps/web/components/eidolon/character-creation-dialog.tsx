"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";

import {
  authoredCharacterDraft,
  canonicalizeCharacterAdultDraft,
  CHARACTER_BUILDER_STEPS,
  type CharacterBuilderStep,
  type CharacterDraftErrors,
  firstInvalidBuilderStep,
  parseCharacterAge,
  stepHasError,
  validateCharacterDraft
} from "./character-builder-model";
import {
  IdentityStep,
  InnerLifeStep,
  TrustStep,
  WorldStep
} from "./character-builder-steps";
import type {
  CharacterCreationResult,
  CharacterDraft
} from "./types";
import {
  errorClass,
  noticeClass,
  primaryButtonClass,
  secondaryButtonClass
} from "./ui";

export function CharacterCreationDialog({
  onClose,
  onCreate
}: {
  onClose: () => void;
  onCreate: (draft: CharacterDraft) => Promise<CharacterCreationResult>;
}) {
  const [draft, setDraft] = useState<CharacterDraft>(authoredCharacterDraft);
  const [step, setStep] = useState<CharacterBuilderStep>("identity");
  const [errors, setErrors] = useState<CharacterDraftErrors>({});
  const [requestError, setRequestError] = useState<string | null>(null);
  const [persisted, setPersisted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const firstFieldRef = useRef<HTMLInputElement>(null);
  const submittingRef = useRef(false);

  useEffect(() => {
    submittingRef.current = submitting;
  }, [submitting]);

  useEffect(() => {
    const previouslyFocused =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusFrame = window.requestAnimationFrame(() => firstFieldRef.current?.focus());

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !submittingRef.current) {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") {
        return;
      }
      const focusable = Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        ) ?? []
      ).filter((element) => element.offsetParent !== null);
      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !dialogRef.current?.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || !dialogRef.current?.contains(active))) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus();
    };
  }, [onClose]);

  const stepIndex = CHARACTER_BUILDER_STEPS.findIndex((item) => item.id === step);
  const atFinalStep = stepIndex === CHARACTER_BUILDER_STEPS.length - 1;
  const adultAge = parseCharacterAge(draft.explicit_age);
  const adultAgeReady = adultAge !== null && adultAge >= 18;

  function updateDraft<K extends keyof CharacterDraft>(field: K, value: CharacterDraft[K]) {
    setDraft((current) =>
      canonicalizeCharacterAdultDraft({ ...current, [field]: value })
    );
    setErrors((current) => {
      if (!current[field] && field !== "private_mode_default") {
        return current;
      }
      const next = { ...current };
      delete next[field];
      if (field === "private_mode_default") {
        delete next.adult_memory_storage;
      }
      return next;
    });
    if (!persisted) {
      setRequestError(null);
    }
  }

  function updateAge(value: string) {
    const age = parseCharacterAge(value);
    const canRemainAdult = age !== null && age >= 18;
    setDraft((current) =>
      canonicalizeCharacterAdultDraft({
        ...current,
        explicit_age: value
      })
    );
    setErrors((current) => {
      const next = { ...current };
      delete next.explicit_age;
      delete next.content_intensity;
      delete next.adult_memory_storage;
      if (canRemainAdult) {
        delete next.adult_mode_allowed;
      }
      return next;
    });
    setRequestError(null);
  }

  function setAdultEligibility(enabled: boolean) {
    if (enabled && !adultAgeReady) {
      setErrors((current) => ({
        ...current,
        explicit_age: "Adult eligibility requires an explicit age of 18 or older.",
        adult_mode_allowed: "Set an adult age before enabling adult eligibility."
      }));
      return;
    }
    setDraft((current) =>
      canonicalizeCharacterAdultDraft({
        ...current,
        adult_mode_allowed: enabled
      })
    );
    setErrors((current) => {
      const next = { ...current };
      delete next.adult_mode_allowed;
      delete next.content_intensity;
      delete next.adult_memory_storage;
      return next;
    });
    setRequestError(null);
  }

  function chooseStep(nextStep: CharacterBuilderStep) {
    if (!submitting && !persisted) {
      setStep(nextStep);
    }
  }

  function continueForward() {
    const nextErrors = validateCharacterDraft(draft, {
      requireAuthoredProfile: true
    });
    setErrors(nextErrors);
    if (stepHasError(step, nextErrors)) {
      focusFirstInvalidField();
      return;
    }
    const nextStep = CHARACTER_BUILDER_STEPS[stepIndex + 1];
    if (nextStep) {
      setStep(nextStep.id);
      scrollDialogToTop();
    }
  }

  function goBack() {
    const previousStep = CHARACTER_BUILDER_STEPS[stepIndex - 1];
    if (previousStep) {
      setStep(previousStep.id);
      scrollDialogToTop();
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submittingRef.current || persisted) {
      return;
    }
    const nextErrors = validateCharacterDraft(draft, {
      requireAuthoredProfile: true
    });
    setErrors(nextErrors);
    const invalidStep = firstInvalidBuilderStep(nextErrors);
    if (invalidStep) {
      setStep(invalidStep);
      focusFirstInvalidField();
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);
    setRequestError(null);
    try {
      const result = await onCreate(draft);
      if (result.ok) {
        onClose();
        return;
      }
      setRequestError(result.error);
      setPersisted(result.persisted);
    } catch {
      setRequestError("The companion could not be created. Your profile is still here.");
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  }

  function focusFirstInvalidField() {
    window.requestAnimationFrame(() => {
      const invalid = dialogRef.current?.querySelector<HTMLElement>(
        '[aria-invalid="true"]'
      );
      invalid?.focus();
    });
  }

  function scrollDialogToTop() {
    window.requestAnimationFrame(() => {
      dialogRef.current?.querySelector<HTMLElement>("[data-builder-scroll]")?.scrollTo({
        top: 0,
        behavior: "smooth"
      });
    });
  }

  function requestClose() {
    if (!submittingRef.current) {
      onClose();
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/80 p-0 backdrop-blur-sm sm:items-center sm:p-5"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          requestClose();
        }
      }}
    >
      <div
        aria-labelledby="character-builder-title"
        aria-modal="true"
        className="flex max-h-[96vh] w-full max-w-4xl flex-col overflow-hidden rounded-t-lg border border-line bg-panel shadow-2xl shadow-black/60 sm:max-h-[90vh] sm:rounded-lg"
        ref={dialogRef}
        role="dialog"
      >
        <header className="flex items-start justify-between gap-4 border-b border-line px-4 py-4 sm:px-6">
          <div className="min-w-0">
            <p className="text-xs uppercase text-zinc-500">New companion</p>
            <h2 className="mt-1 truncate text-xl font-semibold" id="character-builder-title">
              {draft.name.trim() || "Shape a presence"}
            </h2>
            <p className="mt-1 text-sm text-zinc-500">
              {CHARACTER_BUILDER_STEPS[stepIndex]?.summary}
            </p>
          </div>
          <button
            aria-label="Close character builder"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-line bg-ink text-lg text-zinc-400 hover:border-zinc-400 hover:text-paper disabled:opacity-50"
            disabled={submitting}
            onClick={requestClose}
            type="button"
          >
            X
          </button>
        </header>

        <nav
          aria-label="Character builder stages"
          className="grid grid-cols-4 border-b border-line bg-ink/60 p-2"
        >
          {CHARACTER_BUILDER_STEPS.map((item, index) => (
            <button
              aria-current={step === item.id ? "step" : undefined}
              className={`min-h-12 border-b-2 px-1 text-xs sm:px-3 sm:text-sm ${
                step === item.id
                  ? "border-moss text-paper"
                  : stepHasError(item.id, errors)
                    ? "border-amber-700 text-amber-200"
                    : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
              disabled={submitting || persisted}
              key={item.id}
              onClick={() => chooseStep(item.id)}
              type="button"
            >
              <span className="block text-[10px] text-zinc-600">0{index + 1}</span>
              <span className="block truncate">{item.label}</span>
            </button>
          ))}
        </nav>

        <form className="flex min-h-0 flex-1 flex-col" onSubmit={submit}>
          <fieldset
            className="min-h-0 flex-1 disabled:opacity-70"
            disabled={submitting || persisted}
          >
            <div className="h-full overflow-y-auto px-4 py-5 sm:px-6" data-builder-scroll>
              {step === "identity" ? (
                <IdentityStep
                  adultAgeReady={adultAgeReady}
                  draft={draft}
                  errors={errors}
                  firstFieldRef={firstFieldRef}
                  onAgeChange={updateAge}
                  onAdultEligibilityChange={setAdultEligibility}
                  onChange={updateDraft}
                />
              ) : null}
              {step === "inner-life" ? (
                <InnerLifeStep draft={draft} errors={errors} onChange={updateDraft} />
              ) : null}
              {step === "world" ? (
                <WorldStep draft={draft} errors={errors} onChange={updateDraft} />
              ) : null}
              {step === "trust" ? (
                <TrustStep
                  draft={draft}
                  errors={errors}
                  onAdultEligibilityChange={setAdultEligibility}
                  onChange={updateDraft}
                />
              ) : null}
            </div>
          </fieldset>

          <footer className="border-t border-line bg-panel px-4 py-3 sm:px-6">
            {requestError ? (
              <p className={persisted ? noticeClass : errorClass} role="alert">
                {requestError}
              </p>
            ) : null}
            <div className="mt-2 flex items-center justify-between gap-3">
              <p className="text-xs text-zinc-600">
                {stepIndex + 1} of {CHARACTER_BUILDER_STEPS.length}
              </p>
              <div className="flex gap-2">
                {persisted ? (
                  <button className={primaryButtonClass} onClick={requestClose} type="button">
                    Return to characters
                  </button>
                ) : (
                  <>
                    {stepIndex > 0 ? (
                      <button
                        className={secondaryButtonClass}
                        disabled={submitting}
                        onClick={goBack}
                        type="button"
                      >
                        Back
                      </button>
                    ) : null}
                    {atFinalStep ? (
                      <button
                        className={primaryButtonClass}
                        disabled={submitting}
                        type="submit"
                      >
                        {submitting ? "Creating companion" : "Create companion"}
                      </button>
                    ) : (
                      <button
                        className={primaryButtonClass}
                        disabled={submitting}
                        onClick={(event) => {
                          event.preventDefault();
                          continueForward();
                        }}
                        type="button"
                      >
                        Continue
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          </footer>
        </form>
      </div>
    </div>
  );
}
