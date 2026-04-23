"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import type { LabelOut } from "@/types/skill";
import { useAuth } from "@/lib/auth";
import { addLabel, removeLabel, listSkillLabels } from "@/lib/api";
import { LabelPicker } from "@/components/label-picker";
import { labelColor } from "@/lib/label-color";

interface LabelSectionProps {
  slug: string;
  initialLabels: LabelOut[];
}

export function LabelSection({ slug, initialLabels }: LabelSectionProps) {
  const { user } = useAuth();
  const [labels, setLabels] = useState<LabelOut[]>(initialLabels);
  const [error, setError] = useState<string | null>(null);

  const handleAdd = useCallback(
    async (name: string) => {
      setError(null);
      const optimistic: LabelOut = { name, usage_count: 0, applied_by_me: true };
      setLabels((prev) => (prev.find((l) => l.name === name) ? prev : [...prev, optimistic]));

      const { data, error: err, status } = await addLabel(slug, name);

      if (err || !data) {
        setLabels((prev) => prev.filter((l) => l !== optimistic));
        if (status === 409) setError("You've already applied this label.");
        else if (status === 429) setError("Limit reached: max 5 labels per skill.");
        else if (status === 400) setError(err ?? "Invalid label name.");
        else setError("Failed to add label. Please try again.");
        return;
      }

      setLabels((prev) => prev.map((l) => (l === optimistic ? data : l)));
      const fresh = await listSkillLabels(slug);
      setLabels(fresh);
    },
    [slug],
  );

  const handleRemove = useCallback(
    async (name: string) => {
      setError(null);
      const original = labels.find((l) => l.name === name);
      if (!original) return;
      setLabels((prev) => prev.filter((l) => l.name !== name));
      const { error: err } = await removeLabel(slug, name);
      if (err) {
        setLabels((prev) => {
          const exists = prev.find((l) => l.name === name);
          return exists ? prev : [...prev, original];
        });
        setError("Failed to remove label. Please try again.");
      }
    },
    [slug, labels],
  );

  return (
    <div className="space-y-1">
      {error && <p className="text-xs text-destructive">{error}</p>}
      {user ? (
        <LabelPicker
          labels={labels}
          onAdd={handleAdd}
          onRemove={handleRemove}
          canRemoveAll={user.is_admin}
          renderName={(name) => (
            <Link
              href={`/skills?labels=${encodeURIComponent(name)}`}
              className="hover:underline cursor-pointer"
            >
              {name}
            </Link>
          )}
        />
      ) : (
        <>
          {labels.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {labels.map((label) => (
                <Link
                  key={label.name}
                  href={`/skills?labels=${encodeURIComponent(label.name)}`}
                  className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium hover:opacity-80 transition-opacity ${labelColor(label.name)}`}
                >
                  <span>{label.name}</span>
                  <span className="text-muted-foreground tabular-nums">{label.usage_count}</span>
                </Link>
              ))}
            </div>
          )}
          <p
            className="text-xs text-muted-foreground cursor-default"
            title="Authentication required to add labels. Refresh if your session expired."
          >
            Sign in to add labels.
          </p>
        </>
      )}
    </div>
  );
}
