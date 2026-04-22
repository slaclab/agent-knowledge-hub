import { cn } from "@/lib/utils";

const PLATFORM_COLORS: Record<string, { selected: string; unselected: string }> = {
  "claude-code": { selected: "bg-purple-100 text-purple-800 border-purple-300", unselected: "bg-background text-purple-300 border-purple-200 hover:text-purple-500" },
  openai:        { selected: "bg-green-100 text-green-800 border-green-300",    unselected: "bg-background text-green-300 border-green-200 hover:text-green-500" },
  langchain:     { selected: "bg-blue-100 text-blue-800 border-blue-300",       unselected: "bg-background text-blue-300 border-blue-200 hover:text-blue-500" },
  crewai:        { selected: "bg-orange-100 text-orange-800 border-orange-300", unselected: "bg-background text-orange-300 border-orange-200 hover:text-orange-500" },
  autogen:       { selected: "bg-pink-100 text-pink-800 border-pink-300",       unselected: "bg-background text-pink-300 border-pink-200 hover:text-pink-500" },
  mcp:           { selected: "bg-gray-100 text-gray-800 border-gray-300",       unselected: "bg-background text-gray-300 border-gray-200 hover:text-gray-500" },
  codex:         { selected: "bg-sky-100 text-sky-800 border-sky-300",          unselected: "bg-background text-sky-300 border-sky-200 hover:text-sky-500" },
  other:         { selected: "bg-zinc-100 text-zinc-800 border-zinc-300",       unselected: "bg-background text-zinc-300 border-zinc-200 hover:text-zinc-500" },
};

const PLATFORM_FALLBACK = {
  selected: "bg-gray-100 text-gray-800 border-gray-300",
  unselected: "bg-background text-gray-300 border-gray-200 hover:text-gray-500",
};

export function platformPillClass(platform: string, selected: boolean): string {
  const colors = PLATFORM_COLORS[platform] ?? PLATFORM_FALLBACK;
  return selected ? colors.selected : colors.unselected;
}

interface PlatformBadgesProps {
  platforms: string[];
  className?: string;
}

export function PlatformBadges({ platforms, className }: PlatformBadgesProps) {
  return (
    <div className={cn("flex flex-wrap gap-1", className)}>
      {platforms.map((p) => (
        <span
          key={p}
          className={cn(
            "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
            PLATFORM_COLORS[p]?.selected ?? PLATFORM_FALLBACK.selected,
          )}
        >
          {p}
        </span>
      ))}
    </div>
  );
}
