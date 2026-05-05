"use client";

import { useState } from "react";
import { MarkdownRender } from "@/components/markdown-render";
import { ReadmeRender } from "@/components/readme-render";
import { Lock } from "lucide-react";

interface SkillContentTabsProps {
  readmeRaw: string | null;
  readmeHtml: string | null;
  skillMdRaw: string | null;
  skillMdFilename: string | null;
  isInternal: boolean;
  isAuthenticated: boolean;
}

export function SkillContentTabs({
  readmeRaw,
  readmeHtml,
  skillMdRaw,
  skillMdFilename,
  isInternal,
  isAuthenticated,
}: SkillContentTabsProps) {
  const showSkillTab = !!skillMdRaw;
  const [activeTab, setActiveTab] = useState<"readme" | "skill">("readme");

  const contentGated = isInternal && !isAuthenticated;

  const tabs = [
    { id: "readme" as const, label: "README.md" },
    ...(showSkillTab ? [{ id: "skill" as const, label: skillMdFilename ?? "Skill Instructions" }] : []),
  ];

  return (
    <div className="rounded-lg border">
      {/* Tab bar */}
      <div className="flex border-b">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "border-b-2 border-primary text-foreground -mb-px"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="p-6">
        {contentGated ? (
          <div className="flex flex-col items-center gap-3 py-8 text-muted-foreground text-sm">
            <Lock className="h-5 w-5" />
            <p>Sign in to view content for SLAC-only skills.</p>
          </div>
        ) : activeTab === "readme" ? (
          readmeRaw ? (
            <MarkdownRender content={readmeRaw} />
          ) : readmeHtml ? (
            <ReadmeRender html={readmeHtml} />
          ) : (
            <p className="text-center text-muted-foreground text-sm">No README available.</p>
          )
        ) : (
          skillMdRaw ? (
            <MarkdownRender content={skillMdRaw} />
          ) : (
            <p className="text-center text-muted-foreground text-sm">No skill instructions found.</p>
          )
        )}
      </div>
    </div>
  );
}
