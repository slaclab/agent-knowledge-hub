"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { SkillsetRef } from "@/types/skillset";
import { useAuth } from "@/lib/auth";
import { removeSkillsetMember } from "@/lib/api";
import { membershipMessage } from "@/lib/skillset";

interface Props {
  skillSlug: string;
  skillName: string;
  submitterId: string;
  skillsets: SkillsetRef[];
}

/** FR-10, with FR-2e's Remove control for the skill's submitter. */
export function SkillSkillsetsSection({ skillSlug, skillName, submitterId, skillsets }: Props) {
  const { user } = useAuth();
  const router = useRouter();
  const [confirming, setConfirming] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [refreshing, startRefresh] = useTransition();
  const [message, setMessage] = useState<{ at: string; text: string } | null>(null);
  const isSubmitter = !!user && user.user_id === submitterId;
  const count = skillsets.length;

  const remove = async (skillsetSlug: string) => {
    setPending(true);
    setMessage(null);
    const text = membershipMessage("remove", await removeSkillsetMember(skillsetSlug, skillSlug));
    setPending(false);
    setConfirming(null);
    if (text) setMessage({ at: skillsetSlug, text });
    else startRefresh(() => router.refresh());
  };

  return (
    <div className="rounded-lg border p-4 space-y-2">
      <h3 className="text-sm font-semibold">
        Part of {count} skillset{count !== 1 ? "s" : ""}
      </h3>
      <ul className="space-y-1.5 text-sm">
        {skillsets.map((s) => (
          <li key={s.slug} className="space-y-1">
            <div className="flex items-center justify-between gap-2">
              <Link href={`/skillsets/${s.slug}`} className="truncate hover:underline">
                {s.name}
              </Link>
              {isSubmitter && confirming !== s.slug && (
                <button
                  type="button"
                  onClick={() => setConfirming(s.slug)}
                  disabled={pending || refreshing}
                  aria-label={`Remove ${skillName} from ${s.name}`}
                  className="shrink-0 text-xs text-destructive hover:underline disabled:opacity-50"
                >
                  Remove
                </button>
              )}
            </div>
            {confirming === s.slug && (
              <div className="rounded-md border border-destructive/40 bg-destructive/5 p-2 space-y-1.5">
                <p className="text-xs">
                  Remove {skillName} from {s.name}? Only the skillset&apos;s curator can add it back.
                </p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => remove(s.slug)}
                    disabled={pending}
                    className="rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1 text-xs text-destructive hover:bg-destructive/20 transition-colors disabled:opacity-50"
                  >
                    {pending ? "Removing…" : "Confirm remove"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirming(null)}
                    disabled={pending}
                    className="rounded-md border px-2 py-1 text-xs hover:bg-muted transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
            {message?.at === s.slug && <p className="text-xs text-destructive">{message.text}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
