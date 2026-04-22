"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { X } from "lucide-react";
import type { LabelOut } from "@/types/skill";
import { labelColor } from "@/lib/label-color";

interface LabelChip {
  name: string;
  count?: number;
  canRemove: boolean;
}

interface LabelPickerProps {
  /** Accepted as LabelOut[] (live mode) or string[] (draft mode). */
  labels: LabelOut[] | string[];
  onAdd: (name: string) => void | Promise<void>;
  onRemove: (name: string) => void | Promise<void>;
  /** When true, every chip shows ×. When false, chip shows × only if applied_by_me (or is_admin handled by caller filtering). Default false. */
  canRemoveAll?: boolean;
  /** Forwarded to the suggestion fetch limit. Default 10. */
  suggestionLimit?: number;
  /** Optional renderer for the chip name — defaults to a plain <span>. Use to wrap in a Link. */
  renderName?: (name: string) => React.ReactNode;
  /** Extra class on the root div. */
  className?: string;
}

function normalise(labels: LabelOut[] | string[]): LabelChip[] {
  return labels.map((l) =>
    typeof l === "string"
      ? { name: l, canRemove: true }
      : { name: l.name, count: l.usage_count, canRemove: l.applied_by_me },
  );
}

export function LabelPicker({
  labels,
  onAdd,
  onRemove,
  canRemoveAll = false,
  suggestionLimit = 10,
  renderName,
  className,
}: LabelPickerProps) {
  const chips = normalise(labels);
  const [adding, setAdding] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [suggestions, setSuggestions] = useState<LabelOut[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  // Typeahead fetch
  useEffect(() => {
    if (!inputValue.trim()) { setSuggestions([]); return; }
    const ac = new AbortController();
    fetch(`/api/labels?q=${encodeURIComponent(inputValue.trim())}&limit=${suggestionLimit}`, { signal: ac.signal })
      .then((r) => r.json())
      .then((d: LabelOut[]) => setSuggestions(d))
      .catch(() => {});
    return () => ac.abort();
  }, [inputValue, suggestionLimit]);

  // Collapse on outside click
  useEffect(() => {
    function onMouseDown(e: MouseEvent) {
      if (
        inputRef.current?.contains(e.target as Node) ||
        suggestionsRef.current?.contains(e.target as Node)
      ) return;
      setShowSuggestions(false);
      if (!inputValue.trim()) setAdding(false);
    }
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [inputValue]);

  const openInput = useCallback(() => {
    setAdding(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  }, []);

  const commit = useCallback(async (name: string) => {
    const trimmed = name.trim().toLowerCase();
    if (!trimmed) return;
    setInputValue("");
    setShowSuggestions(false);
    await onAdd(trimmed);
    setAdding(false);
  }, [onAdd]);

  const existingNames = new Set(chips.map((c) => c.name));

  return (
    <div className={`flex flex-wrap gap-1.5 ${className ?? ""}`}>
      {chips.map((chip) => (
        <span
          key={chip.name}
          className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${labelColor(chip.name)}`}
        >
          {renderName ? renderName(chip.name) : <span>{chip.name}</span>}
          {chip.count !== undefined && (
            <span className="text-muted-foreground tabular-nums">{chip.count}</span>
          )}
          {(canRemoveAll || chip.canRemove) && (
            <button
              type="button"
              onClick={() => onRemove(chip.name)}
              className="ml-0.5 text-muted-foreground hover:text-foreground transition-colors"
              aria-label={`Remove label ${chip.name}`}
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </span>
      ))}

      <div className="relative">
        {adding ? (
          <>
            <input
              ref={inputRef}
              value={inputValue}
              onChange={(e) => {
                setInputValue(e.target.value);
                setShowSuggestions(true);
              }}
              onFocus={() => setShowSuggestions(true)}
              onKeyDown={(e) => {
                if (e.key === "Enter") { e.preventDefault(); commit(inputValue); }
                if (e.key === "Escape") { setInputValue(""); setAdding(false); setShowSuggestions(false); }
              }}
              onBlur={() => { if (!inputValue.trim()) setAdding(false); }}
              placeholder="Label name…"
              size={Math.max(inputValue.length, 10)}
              className="rounded-full border border-input bg-background px-3 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring min-w-0"
            />
            {showSuggestions && suggestions.length > 0 && (
              <div
                ref={suggestionsRef}
                className="absolute left-0 top-full mt-0.5 z-20 min-w-[8rem] rounded-md border bg-white dark:bg-zinc-900 shadow-lg"
              >
                {suggestions
                  .filter((s) => !existingNames.has(s.name))
                  .map((s) => (
                    <button
                      key={s.name}
                      type="button"
                      onMouseDown={(e) => { e.preventDefault(); commit(s.name); }}
                      className="flex w-full items-center justify-between px-2.5 py-1 text-xs hover:bg-muted transition-colors"
                    >
                      <span>{s.name}</span>
                      <span className="text-muted-foreground tabular-nums">{s.usage_count}</span>
                    </button>
                  ))}
              </div>
            )}
          </>
        ) : (
          <button
            type="button"
            onClick={openInput}
            className="inline-flex items-center gap-0.5 rounded-full border border-dashed px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground hover:border-foreground transition-colors"
          >
            <span className="text-sm leading-none">+</span>
            <span>Add label</span>
          </button>
        )}
      </div>
    </div>
  );
}
