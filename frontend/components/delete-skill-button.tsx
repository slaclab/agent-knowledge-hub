"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getMe, deleteSkill } from "@/lib/api";

interface Props {
  slug: string;
  submitterId: string;
}

export function DeleteSkillButton({ slug, submitterId }: Props) {
  const router = useRouter();
  const [canDelete, setCanDelete] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const confirmRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getMe().then((user) => {
      if (user && (user.user_id === submitterId || user.is_admin)) {
        setCanDelete(true);
      }
    });
  }, [submitterId]);

  useEffect(() => {
    if (!confirming) return;
    const handler = (e: MouseEvent) => {
      if (confirmRef.current && !confirmRef.current.contains(e.target as Node)) {
        setConfirming(false);
        setError(null);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [confirming]);

  if (!canDelete) return null;

  const handleDelete = async () => {
    setDeleting(true);
    setError(null);
    const { error: err } = await deleteSkill(slug);
    if (err) {
      setDeleting(false);
      setError(err);
      setConfirming(false);
      return;
    }
    router.push("/skills");
  };

  if (confirming) {
    return (
      <div ref={confirmRef} className="flex flex-col items-end gap-1">
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="inline-flex items-center rounded-md border border-destructive/40 bg-destructive/10 px-3 py-1.5 text-sm text-destructive hover:bg-destructive/20 transition-colors disabled:opacity-50"
        >
          {deleting ? "Deleting…" : "Confirm Delete"}
        </button>
        {error && (
          <p className="text-xs text-destructive">{error}</p>
        )}
      </div>
    );
  }

  return (
    <button
      onClick={() => setConfirming(true)}
      className="inline-flex items-center rounded-md border border-destructive/40 px-3 py-1.5 text-sm text-destructive hover:bg-destructive/10 transition-colors"
    >
      Delete
    </button>
  );
}
