"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown } from "lucide-react";
import type { SkillsetListOut, SkillsetRef } from "@/types/skillset";
import { useAuth } from "@/lib/auth";
import { addSkillsetMember, listSkillsets, removeSkillsetMember } from "@/lib/api";
import { membershipMessage } from "@/lib/skillset";

// The backend's page_size ceiling. A user who owns more skillsets sees only the newest 100.
const MAX_OWNED = 100;

interface Props {
  skillSlug: string;
  /** The skill's `skillsets` field (FR-6): an entry is checked when its skillset holds the skill. */
  memberOf: SkillsetRef[];
}

/** FR-2d: shown to a signed-in user who owns at least one skillset. */
export function AddToSkillsetMenu({ skillSlug, memberOf }: Props) {
  const { user } = useAuth();
  const router = useRouter();
  const [owned, setOwned] = useState<SkillsetListOut[]>([]);
  const [pending, setPending] = useState<string | null>(null);
  const [refreshing, startRefresh] = useTransition();
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    listSkillsets({ created_by: user.user_id, page_size: MAX_OWNED })
      .then((data) => setOwned(data?.items ?? []))
      .catch(() => setOwned([]));
  }, [user]);

  if (!user || owned.length === 0) return null;

  const holding = new Set(memberOf.map((s) => s.slug));

  const toggle = async (skillsetSlug: string) => {
    const op = holding.has(skillsetSlug) ? "remove" : "add";
    setPending(skillsetSlug);
    setMessage(null);
    const status =
      op === "add" ? await addSkillsetMember(skillsetSlug, skillSlug) : await removeSkillsetMember(skillsetSlug, skillSlug);
    const text = membershipMessage(op, status);
    if (text) setMessage(text);
    else startRefresh(() => router.refresh());
    setPending(null);
  };

  return (
    <details className="relative">
      <summary className="inline-flex cursor-pointer list-none items-center gap-1 rounded-md border px-3 py-1.5 text-sm hover:bg-muted transition-colors">
        Add to skillset
        <ChevronDown className="h-3.5 w-3.5" />
      </summary>
      <div className="absolute right-0 top-full z-20 mt-1 w-64 space-y-1 rounded-md border bg-white p-2 shadow-lg dark:bg-zinc-900">
        {owned.map((s) => (
          <label key={s.slug} className="flex cursor-pointer items-center gap-2 rounded px-1.5 py-1 text-sm hover:bg-muted">
            <input
              type="checkbox"
              checked={holding.has(s.slug)}
              disabled={pending !== null || refreshing}
              onChange={() => toggle(s.slug)}
            />
            <span className="truncate">{s.name}</span>
          </label>
        ))}
        {message && <p className="px-1.5 text-xs text-destructive">{message}</p>}
      </div>
    </details>
  );
}
