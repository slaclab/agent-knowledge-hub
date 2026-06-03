"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { X } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { addPlatform, removePlatform } from "@/lib/api";
import { platformPillClass } from "@/components/platform-badges";

const KNOWN_PLATFORMS = ["claude-code", "codex", "opencode", "openai", "langchain", "crewai", "autogen", "mcp", "other"];

interface PlatformSectionProps {
  slug: string;
  initialPlatforms: string[];
}

export function PlatformSection({ slug, initialPlatforms }: PlatformSectionProps) {
  const { user } = useAuth();
  const [platforms, setPlatforms] = useState<string[]>(initialPlatforms);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const available = KNOWN_PLATFORMS.filter((p) => !platforms.includes(p));

  useEffect(() => {
    if (!adding) return;
    function onMouseDown(e: MouseEvent) {
      if (!dropdownRef.current?.contains(e.target as Node)) setAdding(false);
    }
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [adding]);

  const handleAdd = useCallback(async (platform: string) => {
    setAdding(false);
    setError(null);
    setPlatforms((prev) => (prev.includes(platform) ? prev : [...prev, platform]));
    const { data, error: err } = await addPlatform(slug, platform);
    if (err || !data) {
      setPlatforms((prev) => prev.filter((p) => p !== platform));
      setError("Failed to add platform.");
      return;
    }
    setPlatforms(data.compatible_platforms);
  }, [slug]);

  const handleRemove = useCallback(async (platform: string) => {
    setError(null);
    setPlatforms((prev) => prev.filter((p) => p !== platform));
    const { error: err } = await removePlatform(slug, platform);
    if (err) {
      setPlatforms((prev) => (prev.includes(platform) ? prev : [...prev, platform]));
      setError("Failed to remove platform.");
    }
  }, [slug]);

  if (!user) {
    return platforms.length > 0 ? (
      <div className="flex flex-wrap gap-1">
        {platforms.map((p) => (
          <span key={p} className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${platformPillClass(p, true)}`}>
            {p}
          </span>
        ))}
      </div>
    ) : null;
  }

  return (
    <div className="space-y-1">
      {error && <p className="text-xs text-destructive">{error}</p>}
      <div className="flex flex-wrap gap-1.5">
        {platforms.map((p) => (
          <span key={p} className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${platformPillClass(p, true)}`}>
            {p}
            <button
              type="button"
              onClick={() => handleRemove(p)}
              className="ml-0.5 text-current opacity-60 hover:opacity-100 transition-opacity"
              aria-label={`Remove ${p}`}
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}

        <div className="relative" ref={dropdownRef}>
          {adding && available.length > 0 ? (
            <div className="absolute left-0 top-full mt-0.5 z-20 min-w-[9rem] rounded-md border bg-white dark:bg-zinc-900 shadow-lg">
              {available.map((p) => (
                <button
                  key={p}
                  type="button"
                  onMouseDown={(e) => { e.preventDefault(); handleAdd(p); }}
                  className={`flex w-full items-center px-2.5 py-1.5 text-xs hover:bg-muted transition-colors rounded-full m-1 border ${platformPillClass(p, false)}`}
                >
                  {p}
                </button>
              ))}
            </div>
          ) : null}
          {available.length > 0 && (
            <button
              type="button"
              onClick={() => setAdding((v) => !v)}
              className="inline-flex items-center gap-0.5 rounded-full border border-dashed px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground hover:border-foreground transition-colors"
            >
              <span className="text-sm leading-none">+</span>
              <span>Add platform</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
