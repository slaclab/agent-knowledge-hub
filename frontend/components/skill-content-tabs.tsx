"use client";

import { useState } from "react";
import { MarkdownRender } from "@/components/markdown-render";
import { ReadmeRender } from "@/components/readme-render";
import { Lock, File, Folder, ExternalLink, Loader2, AlertCircle } from "lucide-react";
import type { FileManifestEntry } from "@/types/skill";

interface SkillContentTabsProps {
  readmeRaw: string | null;
  readmeHtml: string | null;
  skillMdRaw: string | null;
  skillMdFilename: string | null;
  isInternal: boolean;
  isAuthenticated: boolean;
  fileManifest?: FileManifestEntry[];
  manifestTruncated?: boolean;
  slug?: string;
}

export function SkillContentTabs({
  readmeRaw,
  readmeHtml,
  skillMdRaw,
  skillMdFilename,
  isInternal,
  isAuthenticated,
  fileManifest = [],
  manifestTruncated = false,
  slug,
}: SkillContentTabsProps) {
  const showSkillTab = !!skillMdRaw;
  const [activeTab, setActiveTab] = useState<"readme" | "skill" | "files">("readme");

  const contentGated = isInternal && !isAuthenticated && !readmeRaw && !skillMdRaw;

  const tabs = [
    { id: "readme" as const, label: "README.md" },
    ...(showSkillTab ? [{ id: "skill" as const, label: skillMdFilename ?? "Skill Instructions" }] : []),
    { id: "files" as const, label: fileManifest.length > 0 ? `Files (${fileManifest.filter(e => !e.is_dir).length})` : "Files" },
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
        {activeTab === "files" ? (
          <FilesTabContent
            entries={fileManifest}
            truncated={manifestTruncated}
            slug={slug}
            isAuthenticated={isAuthenticated}
          />
        ) : contentGated ? (
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

function formatBytes(bytes: number): string {
  if (bytes === 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function FilesTabContent({
  entries,
  truncated,
  slug,
  isAuthenticated,
}: {
  entries: FileManifestEntry[];
  truncated: boolean;
  slug?: string;
  isAuthenticated: boolean;
}) {
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<Record<string, string>>({});
  const [loadingFile, setLoadingFile] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  if (entries.length === 0) {
    return (
      <div className="text-center text-muted-foreground text-sm py-8 space-y-2">
        <p>File listing is not available for this skill.</p>
        <p className="text-xs">It may pre-date file indexing, or the repository was unavailable during scanning.</p>
      </div>
    );
  }

  const handleFileClick = async (entry: FileManifestEntry) => {
    if (entry.is_dir || !entry.is_text || !slug) return;
    if (activeFile === entry.path) {
      setActiveFile(null);
      return;
    }
    setActiveFile(entry.path);
    setFileError(null);

    if (fileContent[entry.path] !== undefined) return; // already fetched

    setLoadingFile(entry.path);
    try {
      const res = await fetch(`/api/skills/${slug}/files/${entry.path}`, {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setFileContent((prev) => ({ ...prev, [entry.path]: data.content }));
      } else if (res.status === 400) {
        setFileContent((prev) => ({ ...prev, [entry.path]: "__binary__" }));
      } else {
        setFileError(`Failed to load ${entry.path}`);
      }
    } catch {
      setFileError(`Failed to load ${entry.path}`);
    } finally {
      setLoadingFile(null);
    }
  };

  return (
    <div className="space-y-1">
      {entries.map((entry) => (
        <div key={entry.path}>
          <div
            className={`flex items-center gap-2 px-2 py-1.5 rounded text-sm ${
              entry.is_dir
                ? "text-muted-foreground/70 cursor-default"
                : entry.is_text
                ? "hover:bg-muted cursor-pointer"
                : "text-muted-foreground cursor-default"
            }`}
            onClick={() => handleFileClick(entry)}
            title={entry.is_dir ? "Subdirectory — contents not indexed in this version" : undefined}
          >
            {entry.is_dir ? (
              <Folder className="h-4 w-4 shrink-0 text-muted-foreground/60" />
            ) : (
              <File className="h-4 w-4 shrink-0 text-muted-foreground" />
            )}
            <span className={`flex-1 font-mono text-xs truncate ${entry.is_dir ? "italic text-muted-foreground/60" : ""}`}>
              {entry.path}
            </span>
            {entry.is_dir ? (
              <span className="text-[10px] text-muted-foreground/50 shrink-0">dir</span>
            ) : !entry.is_text ? (
              <ExternalLink className="h-3 w-3 shrink-0 text-muted-foreground" />
            ) : (
              <span className="text-[10px] text-muted-foreground shrink-0">{formatBytes(entry.size_bytes)}</span>
            )}
          </div>

          {/* Inline viewer */}
          {activeFile === entry.path && (
            <div className="mt-1 mb-2 rounded border bg-muted/30 overflow-hidden">
              {loadingFile === entry.path ? (
                <div className="flex items-center gap-2 px-4 py-3 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Loading…</span>
                </div>
              ) : fileError ? (
                <div className="flex items-center gap-2 px-4 py-3 text-sm text-destructive">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{fileError}</span>
                </div>
              ) : fileContent[entry.path] === "__binary__" ? (
                <p className="px-4 py-3 text-sm text-muted-foreground">Binary file — cannot preview inline.</p>
              ) : fileContent[entry.path] !== undefined ? (
                <pre className="text-xs p-4 overflow-x-auto max-h-96 whitespace-pre-wrap break-words">
                  {fileContent[entry.path]}
                </pre>
              ) : null}
            </div>
          )}
        </div>
      ))}

      {truncated && (
        <p className="text-xs text-muted-foreground px-2 pt-2">
          Showing first 200 files. Visit the repository on GitHub to see all files.
        </p>
      )}
    </div>
  );
}
