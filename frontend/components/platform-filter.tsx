"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useCallback } from "react";
import { platformPillClass } from "@/components/platform-badges";
import { togglePlatform, buildPlatformsParam } from "@/lib/platform-filter";

export const KNOWN_PLATFORMS = [
  "claude-code", "codex", "opencode", "openai",
  "langchain", "crewai", "autogen", "mcp", "other",
] as const;

interface PlatformFilterProps {
  activePlatforms: string[];
  platformCounts?: Record<string, number>;
}

export function PlatformFilter({ activePlatforms, platformCounts = {} }: PlatformFilterProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();

  const toggle = useCallback(
    (platform: string) => {
      const next = togglePlatform(activePlatforms, platform);
      const params = new URLSearchParams(searchParams.toString());
      const val = buildPlatformsParam(next);
      if (val) params.set("platforms", val);
      else params.delete("platforms");
      params.delete("page");
      params.delete("cursor");
      router.push(`${pathname}?${params}`);
    },
    [activePlatforms, router, searchParams, pathname],
  );

  return (
    <div className="flex items-center gap-1 flex-wrap">
      {activePlatforms.length >= 2 && (
        <span className="text-xs text-muted-foreground mr-0.5">(any of)</span>
      )}
      {KNOWN_PLATFORMS.map((p) => {
        const isActive = activePlatforms.includes(p);
        const count = platformCounts[p];
        return (
          <button
            key={p}
            onClick={() => toggle(p)}
            className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium transition-colors ${platformPillClass(p, isActive)}`}
            aria-pressed={isActive}
          >
            {p}
            {count != null && (
              <span className="opacity-70">{count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
