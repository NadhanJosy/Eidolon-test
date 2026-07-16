"use client";

import { useEffect, useRef, useState } from "react";

import { Icon } from "./icons";

export type ConfirmationRequest = {
  title: string;
  detail: string;
  actionLabel: string;
  onConfirm: () => void | Promise<unknown>;
};

export function ConfirmationDialog({
  request,
  onClose
}: {
  request: ConfirmationRequest | null;
  onClose: () => void;
}) {
  const [submitting, setSubmitting] = useState(false);
  const [failure, setFailure] = useState<{
    request: ConfirmationRequest;
    message: string;
  } | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const submittingRef = useRef(false);

  useEffect(() => {
    if (!request) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !submittingRef.current) {
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>('button:not([disabled])') ?? []
      );
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

    const frame = window.requestAnimationFrame(() => {
      dialogRef.current?.querySelector<HTMLButtonElement>("[data-confirm-cancel]")?.focus();
    });
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
      previouslyFocused?.focus();
    };
  }, [onClose, request]);

  if (!request) return null;
  const activeRequest = request;

  async function confirm() {
    if (submittingRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    setFailure(null);
    try {
      const result = await activeRequest.onConfirm();
      if (result === false) {
        setFailure({
          request: activeRequest,
          message: "That could not be completed. Nothing else was removed; try again in a moment."
        });
        return;
      }
      onClose();
    } catch {
      setFailure({
        request: activeRequest,
        message: "That could not be completed. Nothing else was removed; try again in a moment."
      });
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  }

  const actionError = failure?.request === activeRequest ? failure.message : null;

  return (
    <div className="fixed inset-0 z-[140] grid place-items-end bg-black/70 p-0 backdrop-blur-sm sm:place-items-center sm:p-6">
      <button
        aria-label="Cancel confirmation"
        className="absolute inset-0"
        disabled={submitting}
        onClick={onClose}
        type="button"
      />
      <div
        aria-describedby="confirmation-detail"
        aria-labelledby="confirmation-title"
        aria-modal="true"
        className="safe-area-composer relative w-full max-w-md rounded-t-[2rem] border border-white/[0.1] bg-[#12100e] p-6 shadow-veil reveal-up sm:rounded-[2rem] sm:p-8"
        ref={dialogRef}
        role="alertdialog"
      >
        <span className="grid h-11 w-11 place-items-center rounded-full border border-[#c47b6c]/20 bg-[#77362c]/10 text-[#d39a8c]">
          <Icon className="h-4 w-4" name="trash" />
        </span>
        <h2 className="mt-6 font-eidolon-display text-3xl text-[#eee4da]" id="confirmation-title">
          {request.title}
        </h2>
        <p className="mt-3 text-sm leading-6 text-[#978c82]" id="confirmation-detail">
          {request.detail}
        </p>
        {actionError ? (
          <p className="mt-4 rounded-xl border border-[#c47b6c]/20 bg-[#77362c]/10 px-3 py-2.5 text-xs leading-5 text-[#dda699]" role="alert">
            {actionError}
          </p>
        ) : null}
        <div className="mt-8 grid grid-cols-2 gap-3">
          <button
            className="min-h-11 rounded-full border border-white/[0.12] text-sm text-[#c6bbb0] transition hover:border-white/[0.24] hover:text-[#f0e7de]"
            data-confirm-cancel
            disabled={submitting}
            onClick={onClose}
            type="button"
          >
            Keep it
          </button>
          <button
            className="min-h-11 rounded-full border border-[#c47b6c]/28 bg-[#77362c]/16 px-4 text-sm text-[#dda699] transition hover:border-[#c47b6c]/48 hover:bg-[#77362c]/28 disabled:opacity-50"
            disabled={submitting}
            onClick={() => void confirm()}
            type="button"
          >
            {submitting ? "Removing…" : request.actionLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
