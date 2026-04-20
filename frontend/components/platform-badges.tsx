import { cn } from "@/lib/utils";

const PLATFORM_COLORS: Record<string, string> = {
  "claude-code": "bg-purple-100 text-purple-800",
  openai: "bg-green-100 text-green-800",
  langchain: "bg-blue-100 text-blue-800",
  crewai: "bg-orange-100 text-orange-800",
  autogen: "bg-pink-100 text-pink-800",
  mcp: "bg-gray-100 text-gray-800",
};

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
            PLATFORM_COLORS[p] ?? "bg-gray-100 text-gray-800",
          )}
        >
          {p}
        </span>
      ))}
    </div>
  );
}
