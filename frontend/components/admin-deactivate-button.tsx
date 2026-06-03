"use client";

import { useState } from "react";
import { ShieldOff, ShieldCheck } from "lucide-react";
import { deactivateSkill, reactivateSkill } from "@/lib/api";

interface AdminDeactivateButtonProps {
  slug: string;
  isDeactivated?: boolean;
  onDeactivated?: () => void;
}

export function AdminDeactivateButton({ slug, isDeactivated = false, onDeactivated }: AdminDeactivateButtonProps) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [supersededBySlug, setSupersededBySlug] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [doneMessage, setDoneMessage] = useState("");

  async function handleDeactivate() {
    if (!reason.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await deactivateSkill(slug, reason, supersededBySlug || undefined);
      if (!result) throw new Error("Request failed");
      setDialogOpen(false);
      setDone(true);
      setDoneMessage("Deactivated");
      onDeactivated?.();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      if (msg.includes("409")) {
        setError("Skill is already deactivated.");
      } else {
        setError("Failed to deactivate. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReactivate() {
    setSubmitting(true);
    setError(null);
    try {
      const result = await reactivateSkill(slug, "Reactivated by admin");
      if (!result) throw new Error("Request failed");
      setDone(true);
      setDoneMessage("Reactivated — reload to see updated status");
    } catch {
      setError("Failed to reactivate. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm text-muted-foreground">
        {doneMessage}
      </span>
    );
  }

  if (isDeactivated) {
    return (
      <button
        className="inline-flex items-center gap-1.5 rounded-md border border-green-300 bg-green-50 px-3 py-1.5 text-sm text-green-700 hover:bg-green-100 transition-colors"
        onClick={handleReactivate}
        disabled={submitting}
      >
        <ShieldCheck className="h-4 w-4" />
        {submitting ? "Reactivating…" : "Reactivate"}
      </button>
    );
  }

  return (
    <>
      <button
        className="inline-flex items-center gap-1.5 rounded-md border border-destructive/50 bg-destructive/5 px-3 py-1.5 text-sm text-destructive hover:bg-destructive/10 transition-colors"
        onClick={() => setDialogOpen(true)}
      >
        <ShieldOff className="h-4 w-4" />
        Deactivate
      </button>

      {dialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background rounded-lg border p-6 w-full max-w-md space-y-4 shadow-xl">
            <h2 className="text-lg font-semibold text-destructive">Deactivate skill</h2>
            <p className="text-sm text-muted-foreground">
              Deactivated skills show a tombstone to all users. Active flags will be auto-resolved.
            </p>

            <div className="space-y-1">
              <label className="text-sm font-medium">Reason <span className="text-destructive">*</span></label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                maxLength={1000}
                rows={3}
                placeholder="Explain why this skill is being deactivated…"
                className="w-full rounded-md border bg-background px-3 py-2 text-sm resize-none"
              />
            </div>

            <div className="space-y-1">
              <label className="text-sm font-medium">Superseded by slug (optional)</label>
              <input
                type="text"
                value={supersededBySlug}
                onChange={(e) => setSupersededBySlug(e.target.value)}
                placeholder="replacement-skill-slug"
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              />
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}

            <div className="flex gap-2 justify-end">
              <button
                className="rounded-md border px-3 py-1.5 text-sm"
                onClick={() => { setDialogOpen(false); setError(null); }}
                disabled={submitting}
              >
                Cancel
              </button>
              <button
                className="rounded-md bg-destructive text-destructive-foreground px-3 py-1.5 text-sm disabled:opacity-50"
                onClick={handleDeactivate}
                disabled={!reason.trim() || submitting}
              >
                {submitting ? "Deactivating…" : "Deactivate"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
