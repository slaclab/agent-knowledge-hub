"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { searchSkillSummaries } from "@/lib/api";
import type { SkillSummary } from "@/types/skillset";

const SHOWN = 10;

type Search =
  | { state: "idle" }
  | { state: "done"; q: string; results: SkillSummary[] }
  | { state: "failed" };

interface Props {
  skillsetSlug: string;
  memberSlugs: Set<string>;
  disabled: boolean;
  /** The owner view links to the submit form when nothing matches (FR-2a). */
  showAddNew: boolean;
  onAdd: (skillSlug: string) => void;
}

/** FR-2c: a typeahead over GET /api/skills/summary?q=, which matches part of a word. */
export function SkillSearchPicker({ skillsetSlug, memberSlugs, disabled, showAddNew, onAdd }: Props) {
  const [text, setText] = useState("");
  const [search, setSearch] = useState<Search>({ state: "idle" });

  useEffect(() => {
    const q = text.trim();
    if (!q) {
      setSearch({ state: "idle" });
      return;
    }
    const ac = new AbortController();
    searchSkillSummaries(q, ac.signal)
      .then((results) => {
        if (!ac.signal.aborted) setSearch(results ? { state: "done", q, results } : { state: "failed" });
      })
      .catch(() => {
        if (!ac.signal.aborted) setSearch({ state: "failed" });
      });
    return () => ac.abort();
  }, [text]);

  return (
    <div className="space-y-1.5">
      <label htmlFor="skill-search-picker" className="text-sm font-medium">
        Add a skill
      </label>
      <input
        id="skill-search-picker"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Search skills by name or description…"
        autoComplete="off"
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      />
      {search.state === "failed" && <p className="text-xs text-destructive">Search failed. Try again.</p>}
      {search.state === "done" && search.results.length === 0 && (
        <p className="text-xs text-muted-foreground">
          No skills match &quot;{search.q}&quot;. Search looks at skill names and descriptions.
          {showAddNew && (
            <>
              {" "}
              <Link href={`/skills/submit?skillset=${encodeURIComponent(skillsetSlug)}`} className="text-primary underline">
                Add new skill →
              </Link>
            </>
          )}
        </p>
      )}
      {search.state === "done" && search.results.length > 0 && (
        <ul className="rounded-md border divide-y">
          {search.results.slice(0, SHOWN).map((s) => {
            const member = memberSlugs.has(s.slug);
            return (
              <li key={s.slug}>
                <button
                  type="button"
                  disabled={disabled || member}
                  onClick={() => {
                    setText("");
                    onAdd(s.slug);
                  }}
                  className="flex w-full flex-col items-start px-3 py-1.5 text-left text-sm hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-transparent"
                >
                  <span className="font-medium">
                    {s.name}
                    {member && <span className="ml-2 text-xs font-normal text-muted-foreground">already in this set</span>}
                  </span>
                  {s.description && <span className="text-xs text-muted-foreground line-clamp-1">{s.description}</span>}
                </button>
              </li>
            );
          })}
          {search.results.length > SHOWN && (
            <li className="px-3 py-1.5 text-xs text-muted-foreground">
              {search.results.length - SHOWN} more; type more of the name to narrow the list.
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
