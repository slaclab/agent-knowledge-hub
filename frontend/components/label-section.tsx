"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { X } from "lucide-react";
import type { LabelOut } from "@/types/skill";
import { useAuth } from "@/lib/auth.tsx";
import { addLabel, removeLabel, listSkillLabels } from "@/lib/api";

interface LabelSectionProps {
  slug: string;
  initialLabels: LabelOut[];
}

export function LabelSection({ slug, initialLabels }: LabelSectionProps) {
  const { user } = useAuth();
  const [labels, setLabels] = useState<LabelOut[]>(initialLabels);
  const [inputValue, setInputValue] = useState("");
  const [suggestions, setSuggestions] = useState<LabelOut[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingAdd, setPendingAdd] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  // Typeahead
  useEffect(() => {
    if (!inputValue.trim()) {
      setSuggestions([]);
      return;
    }
    const controller = new AbortController();
    fetch(`/api/labels?q=${encodeURIComponent(inputValue.trim())}&limit=10`, {
      signal: controller.signal,
    })
      .then((r) => r.json())
      .then((data: LabelOut[]) => setSuggestions(data))
      .catch(() => {});
    return () => controller.abort();
  }, [inputValue]);

  // Close suggestions on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (
        inputRef.current?.contains(e.target as Node) ||
        suggestionsRef.current?.contains(e.target as Node)
      )
        return;
      setShowSuggestions(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const handleAdd = useCallback(
    async (name: string) => {
      const trimmed = name.trim().toLowerCase();
      if (!trimmed) return;
      setError(null);
      setInputValue("");
      setShowSuggestions(false);
      setPendingAdd(trimmed);

      // Optimistic: add a placeholder chip
      const optimistic: LabelOut = { name: trimmed, usage_count: 0, applied_by_me: true };
      setLabels((prev) => (prev.find((l) => l.name === trimmed) ? prev : [...prev, optimistic]));

      const { data, error: err, status } = await addLabel(slug, trimmed);
      setPendingAdd(null);

      if (err || !data) {
        // Revert optimistic update
        setLabels((prev) => prev.filter((l) => l !== optimistic));
        if (status === 409) setError("You've already applied this label.");
        else if (status === 429) setError("Limit reached: max 5 labels per skill.");
        else if (status === 400) setError(err ?? "Invalid label name.");
        else setError("Failed to add label. Please try again.");
        return;
      }

      // Replace optimistic with server response
      setLabels((prev) => prev.map((l) => (l === optimistic ? data : l)));

      // Refresh full list for accurate counts
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

      // Optimistic remove
      setLabels((prev) => prev.filter((l) => l.name !== name));

      const { error: err } = await removeLabel(slug, name);
      if (err) {
        // Revert
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
    <div className="space-y-2">
      {labels.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {labels.map((label) => (
            <span
              key={label.name}
              className="inline-flex items-center gap-1 rounded-full bg-secondary text-secondary-foreground px-2 py-0.5 text-xs font-medium"
            >
              <Link
                href={`/skills?labels=${encodeURIComponent(label.name)}`}
                className="hover:underline cursor-pointer"
              >
                {label.name}
              </Link>
              <span className="text-muted-foreground tabular-nums">{label.usage_count}</span>
              {user && label.applied_by_me && (
                <button
                  onClick={() => handleRemove(label.name)}
                  className="ml-0.5 text-muted-foreground hover:text-foreground transition-colors"
                  aria-label={`Remove label ${label.name}`}
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </span>
          ))}
        </div>
      )}

      {user ? (
        <div className="relative">
          <input
            ref={inputRef}
            value={inputValue}
            onChange={(e) => {
              setInputValue(e.target.value);
              setShowSuggestions(true);
              setError(null);
            }}
            onFocus={() => setShowSuggestions(true)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleAdd(inputValue);
              }
            }}
            placeholder="Add a label…"
            disabled={pendingAdd !== null}
            className="w-full rounded-md border border-input bg-background px-2.5 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
          />
          {showSuggestions && suggestions.length > 0 && (
            <div
              ref={suggestionsRef}
              className="absolute left-0 top-full mt-0.5 z-20 w-full rounded-md border bg-popover shadow-md"
            >
              {suggestions.map((s) => (
                <button
                  key={s.name}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    handleAdd(s.name);
                  }}
                  className="flex w-full items-center justify-between px-2.5 py-1 text-xs hover:bg-muted transition-colors"
                >
                  <span>{s.name}</span>
                  <span className="text-muted-foreground tabular-nums">{s.usage_count}</span>
                </button>
              ))}
            </div>
          )}
          {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
        </div>
      ) : (
        <p
          className="text-xs text-muted-foreground cursor-default"
          title="Authentication required to add labels. Refresh if your session expired."
        >
          Sign in to add labels.
        </p>
      )}
    </div>
  );
}
