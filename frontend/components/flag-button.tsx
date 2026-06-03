"use client";

import { useState } from "react";
import { AlertTriangle, X } from "lucide-react";
import { flagSkill, retractFlag } from "@/lib/api";
import type { FlagOut, FlagReason } from "@/types/skill";

const FLAG_REASONS: { value: FlagReason; label: string }[] = [
  { value: "broken", label: "Broken — skill doesn't work" },
  { value: "stale", label: "Stale — outdated or unmaintained" },
  { value: "superseded", label: "Superseded — replaced by another skill" },
  { value: "inappropriate", label: "Inappropriate content" },
  { value: "other", label: "Other" },
];

interface FlagButtonProps {
  skillSlug: string;
  initialFlagCount: number;
  myFlag: FlagOut | null;
  isAuthenticated: boolean;
}

export function FlagButton({ skillSlug, initialFlagCount, myFlag: initialMyFlag, isAuthenticated }: FlagButtonProps) {
  const [flagCount, setFlagCount] = useState(initialFlagCount);
  const [myFlag, setMyFlag] = useState<FlagOut | null>(initialMyFlag);
  const [modalOpen, setModalOpen] = useState(false);
  const [retractConfirmOpen, setRetractConfirmOpen] = useState(false);
  const [reason, setReason] = useState<FlagReason | "">("");
  const [note, setNote] = useState("");
  const [supersededBySlug, setSupersededBySlug] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const isActive = myFlag?.status === "active";

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  }

  async function handleSubmit() {
    if (!reason) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await flagSkill(skillSlug, reason, note || undefined, supersededBySlug || undefined);
      if (!result) throw new Error("Request failed");
      setFlagCount(result.flag_count);
      setMyFlag(result.my_flag);
      setModalOpen(false);
      setReason("");
      setNote("");
      setSupersededBySlug("");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      if (msg.includes("429")) {
        showToast("You've flagged too many skills recently. Try again later.");
      } else {
        setError("Failed to submit flag. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRetract() {
    setRetractConfirmOpen(false);
    setSubmitting(true);
    try {
      const result = await retractFlag(skillSlug);
      if (!result) throw new Error("Request failed");
      setFlagCount(result.flag_count);
      setMyFlag((prev) => prev ? { ...prev, status: "resolved" } : null);
    } catch {
      showToast("Failed to retract flag. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!isAuthenticated) {
    return (
      <button
        className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted transition-colors"
        onClick={() => window.location.assign("/login")}
        title="Sign in to flag this skill"
      >
        <AlertTriangle className="h-4 w-4" />
        Sign in to flag
      </button>
    );
  }

  return (
    <>
      {toast && (
        <div className="fixed bottom-4 right-4 z-50 rounded-md bg-destructive text-destructive-foreground px-4 py-2 text-sm shadow-lg">
          {toast}
        </div>
      )}

      {isActive ? (
        <div className="relative">
          <button
            className="inline-flex items-center gap-1.5 rounded-md border border-orange-300 bg-orange-50 px-3 py-1.5 text-sm text-orange-700 hover:bg-orange-100 transition-colors"
            onClick={() => setRetractConfirmOpen(true)}
            disabled={submitting}
          >
            <AlertTriangle className="h-4 w-4" />
            Flagged — click to retract
          </button>
          {retractConfirmOpen && (
            <div className="absolute right-0 top-10 z-20 rounded-md border bg-popover p-3 shadow-md w-56 space-y-2">
              <p className="text-sm">Remove your flag for this skill?</p>
              <div className="flex gap-2">
                <button
                  className="flex-1 rounded-md bg-destructive text-destructive-foreground px-2 py-1 text-xs"
                  onClick={handleRetract}
                  disabled={submitting}
                >
                  Remove
                </button>
                <button
                  className="flex-1 rounded-md border px-2 py-1 text-xs"
                  onClick={() => setRetractConfirmOpen(false)}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      ) : (
        <button
          className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-muted transition-colors"
          onClick={() => setModalOpen(true)}
        >
          <AlertTriangle className="h-4 w-4" />
          Flag
          {flagCount > 0 && <span className="ml-1 text-muted-foreground">({flagCount})</span>}
        </button>
      )}

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background rounded-lg border p-6 w-full max-w-md space-y-4 shadow-xl">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Flag this skill</h2>
              <button onClick={() => { setModalOpen(false); setError(null); }} className="text-muted-foreground hover:text-foreground">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-1">
              <label className="text-sm font-medium">Reason <span className="text-destructive">*</span></label>
              <select
                value={reason}
                onChange={(e) => setReason(e.target.value as FlagReason | "")}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              >
                <option value="" disabled>Select a reason…</option>
                {FLAG_REASONS.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>

            {reason === "superseded" && (
              <div className="space-y-1">
                <label className="text-sm font-medium">Replaced by (slug, optional)</label>
                <input
                  type="text"
                  value={supersededBySlug}
                  onChange={(e) => setSupersededBySlug(e.target.value)}
                  placeholder="replacement-skill-slug"
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                />
              </div>
            )}

            <div className="space-y-1">
              <label className="text-sm font-medium">Note (optional)</label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={500}
                rows={3}
                placeholder="Describe the problem…"
                className="w-full rounded-md border bg-background px-3 py-2 text-sm resize-none"
              />
              <p className="text-xs text-muted-foreground text-right">{note.length}/500</p>
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}

            <div className="flex gap-2 justify-end">
              <button
                className="rounded-md border px-3 py-1.5 text-sm"
                onClick={() => { setModalOpen(false); setError(null); }}
                disabled={submitting}
              >
                Cancel
              </button>
              <button
                className="rounded-md bg-destructive text-destructive-foreground px-3 py-1.5 text-sm disabled:opacity-50"
                onClick={handleSubmit}
                disabled={!reason || submitting}
              >
                {submitting ? "Submitting…" : "Submit flag"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
