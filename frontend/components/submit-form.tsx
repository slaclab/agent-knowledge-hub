"use client";

import { useState, useCallback, useRef } from "react";
import { getGithubScan, getGithubDiscover, createSkill, addLabel } from "@/lib/api";
import type { SkillScanSnapshot, DiscoverResult, LabelOut } from "@/types/skill";
import { PLATFORM_SUGGESTIONS } from "@/lib/utils";
import { AlertTriangle, AlertCircle, Loader2, ChevronDown, ChevronRight } from "lucide-react";
import Link from "next/link";
import { LabelPicker } from "@/components/label-picker";
import { platformPillClass } from "@/components/platform-badges";

const SCAN_TIMEOUT_MS = 10_000;
const DISCOVER_TIMEOUT_MS = 30_000;

type ScanState =
  | { status: "idle" }
  | { status: "scanning" }
  | { status: "done"; snapshot: SkillScanSnapshot }
  | { status: "error"; kind: "not_found" | "rate_limit" | "timeout" | "generic"; message: string };

type DiscoverState =
  | { status: "idle" }
  | { status: "discovering" }
  | { status: "done"; result: DiscoverResult }
  | { status: "error"; message: string };

interface SkillDraft {
  snapshot: SkillScanSnapshot;
  selected: boolean;
  expanded: boolean;
  name: string;
  description: string;
  version: string;
  license: string;
  platforms: string[];
  labels: string[];
  result?: { slug?: string; error?: string };
}

export function SubmitForm({
  accessInstructionsUrl = "/guides/slac-github-access",
}: {
  accessInstructionsUrl?: string;
}) {
  const [url, setUrl] = useState("");
  const [scanState, setScanState] = useState<ScanState>({ status: "idle" });
  const [discoverState, setDiscoverState] = useState<DiscoverState>({ status: "idle" });
  const [drafts, setDrafts] = useState<SkillDraft[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [filterText, setFilterText] = useState("");

  const abortRef = useRef<AbortController | null>(null);

  const runDiscover = useCallback(async (scanUrl: string) => {
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    setDiscoverState({ status: "discovering" });

    const timer = setTimeout(() => {
      ac.abort();
      setDiscoverState({ status: "error", message: "Discovery timed out. Try a specific directory URL instead." });
    }, DISCOVER_TIMEOUT_MS);

    const { data, error } = await getGithubDiscover(scanUrl);
    clearTimeout(timer);
    if (ac.signal.aborted) return;

    if (error || !data) {
      setDiscoverState({ status: "error", message: error ?? "Discovery failed." });
      return;
    }

    setDiscoverState({ status: "done", result: data });
    setDrafts(
      data.skills.map((snap) => ({
        snapshot: snap,
        selected: !snap.existing_slug,
        expanded: false,
        name: snap.name ?? "",
        description: snap.description ?? "",
        version: snap.version ?? "",
        license: snap.license ?? "",
        platforms: snap.compatible_platforms,
        labels: [],
      }))
    );
  }, []);

  const runScan = useCallback(async (scanUrl: string) => {
    if (!scanUrl.trim()) return;
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    setScanState({ status: "scanning" });
    setDiscoverState({ status: "idle" });
    setDrafts([]);
    setFilterText("");

    const timer = setTimeout(() => {
      ac.abort();
      setScanState({ status: "error", kind: "timeout", message: "Scan timed out." });
    }, SCAN_TIMEOUT_MS);

    const { data, error, status } = await getGithubScan(scanUrl);
    clearTimeout(timer);
    if (ac.signal.aborted) return;

    if (error || !data) {
      let kind: "not_found" | "rate_limit" | "timeout" | "generic" = "generic";
      if (status === 404) kind = "not_found";
      else if (status === 429 || (status === 403 && error?.toLowerCase().includes("rate")))
        kind = "rate_limit";
      setScanState({ status: "error", kind, message: error ?? "Scan failed." });
      return;
    }

    setScanState({ status: "done", snapshot: data });
    runDiscover(scanUrl);
  }, [runDiscover]);

  const handleBlur = () => {
    if (scanState.status === "idle") runScan(url);
  };

  const updateDraft = (i: number, patch: Partial<SkillDraft>) =>
    setDrafts((prev) => prev.map((d, idx) => (idx === i ? { ...d, ...patch } : d)));

  const toggleDraftPlatform = (i: number, p: string) =>
    setDrafts((prev) =>
      prev.map((d, idx) =>
        idx === i
          ? { ...d, platforms: d.platforms.includes(p) ? d.platforms.filter((x) => x !== p) : [...d.platforms, p] }
          : d
      )
    );

  const filterLower = filterText.toLowerCase();
  const visibleDrafts = filterText
    ? drafts.filter((d) =>
        (d.snapshot.ref.path || "/").toLowerCase().includes(filterLower) ||
        d.name.toLowerCase().includes(filterLower) ||
        d.description.toLowerCase().includes(filterLower)
      )
    : drafts;

  const allNewSelected = visibleDrafts.filter((d) => !d.snapshot.existing_slug).every((d) => d.selected);

  const toggleSelectAll = () => {
    const next = !allNewSelected;
    const visiblePaths = new Set(visibleDrafts.map((d) => d.snapshot.ref.path));
    setDrafts((prev) => prev.map((d) =>
      d.snapshot.existing_slug || !visiblePaths.has(d.snapshot.ref.path) ? d : { ...d, selected: next }
    ));
  };

  const selectedCount = visibleDrafts.filter((d) => d.selected).length;
  const totalCount = drafts.filter((d) => !d.snapshot.existing_slug).length;

  const handleBulkSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setDrafts((prev) => prev.map((d) => ({ ...d, result: undefined })));
    const visiblePaths = new Set(visibleDrafts.map((d) => d.snapshot.ref.path));
    const selected = drafts.filter((d) => d.selected && visiblePaths.has(d.snapshot.ref.path));
    for (const draft of selected) {
      const snap = draft.snapshot;
      const { data, error } = await createSkill({
        repo_url: `https://github.com/${snap.ref.owner}/${snap.ref.repo}`,
        skill_path: snap.ref.path || "/",
        name: draft.name || undefined,
        description: draft.description || undefined,
        compatible_platforms: draft.platforms.length ? draft.platforms : undefined,
        keywords: draft.labels.length ? draft.labels : [],
        version: draft.version || undefined,
        license: draft.license || undefined,
      });
      if (data?.slug && draft.labels.length > 0) {
        await Promise.all(draft.labels.map((l) => addLabel(data.slug, l)));
      }
      const result = { slug: data?.slug, error: error ?? undefined };
      setDrafts((prev) =>
        prev.map((d) => (d.snapshot.ref.path === snap.ref.path ? { ...d, result } : d))
      );
    }
    setSubmitting(false);
  };

  const snapshot = scanState.status === "done" ? scanState.snapshot : null;
  const scanning = scanState.status === "scanning";
  const discovering = discoverState.status === "discovering";
  const inDiscoveryMode = discoverState.status === "done" && drafts.length > 0;

  return (
    <div className="space-y-6">
      {/* URL input — always visible */}
      <div className="space-y-2">
        <label className="text-sm font-medium">
          GitHub URL <span className="text-destructive">*</span>
        </label>
        <p className="text-xs text-muted-foreground">
          Paste a bare repo URL or a directory URL:{" "}
          <code className="font-mono text-xs">https://github.com/org/repo</code> or{" "}
          <code className="font-mono text-xs">.../tree/branch/path/to/skill</code>
        </p>
        <div className="flex gap-2">
          <input
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              setScanState({ status: "idle" });
              setDiscoverState({ status: "idle" });
              setDrafts([]);
            }}
            onBlur={handleBlur}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); runScan(url); } }}
            placeholder="https://github.com/org/repo  or  .../tree/branch/path/to/skill"
            required
            className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <button
            type="button"
            disabled={!url.trim() || scanning || discovering}
            onClick={() => runScan(url)}
            className="flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-2 text-sm hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {scanning ? <><Loader2 className="h-3.5 w-3.5 animate-spin" />Scanning…</> : "Scan"}
          </button>
        </div>

        {scanState.status === "error" && (
          <ScanErrorBanner kind={scanState.kind} message={scanState.message} onRetry={() => runScan(url)} />
        )}

        {snapshot?.visibility === "internal" && (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            This repo requires SLAC GitHub access.
            {accessInstructionsUrl?.startsWith("http") && (
              <>{" "}<a href={accessInstructionsUrl} className="underline" target="_blank">Learn more</a></>
            )}
          </div>
        )}

        {discovering && (
          <p className="text-xs text-muted-foreground flex items-center gap-1.5">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Scanning repo for skill directories…
          </p>
        )}

        {discoverState.status === "error" && (
          <div className="rounded-md border border-yellow-300 bg-yellow-50 px-3 py-2 text-sm text-yellow-800 flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
            <span>{discoverState.message}</span>
          </div>
        )}

        {discoverState.status === "done" && discoverState.result.tree_truncated && (
          <div className="rounded-md border border-yellow-300 bg-yellow-50 px-3 py-2 text-sm text-yellow-800">
            This repo is very large — not all skill directories may have been found. Paste a specific directory URL to register a skill directly.
          </div>
        )}

        {discoverState.status === "done" && discoverState.result.capped && (
          <div className="rounded-md border border-yellow-300 bg-yellow-50 px-3 py-2 text-sm text-yellow-800">
            More than 20 skill directories found — only the first 20 were scanned. Paste a specific directory URL to register skills outside this set.
          </div>
        )}
      </div>

      {/* Discovery mode */}
      {inDiscoveryMode && (
        <form onSubmit={handleBulkSubmit} className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">{drafts.length} skill{drafts.length !== 1 ? "s" : ""} found</span>
            {totalCount > 0 && (
              <button type="button" onClick={toggleSelectAll} className="text-xs text-primary underline hover:no-underline">
                {allNewSelected ? "Deselect all" : "Select all new"}
              </button>
            )}
          </div>

          {drafts.length > 8 && (
            <input
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              placeholder="Filter skills by path or name…"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          )}

          <div className="space-y-2">
            {visibleDrafts.map((draft) => {
              const globalIdx = drafts.indexOf(draft);
              return (
                <DiscoveryCard
                  key={draft.snapshot.ref.path}
                  draft={draft}
                  onToggleSelect={() => updateDraft(globalIdx, { selected: !draft.selected })}
                  onToggleExpand={() => updateDraft(globalIdx, { expanded: !draft.expanded })}
                  onUpdate={(patch) => updateDraft(globalIdx, patch)}
                  onTogglePlatform={(p) => toggleDraftPlatform(globalIdx, p)}
                />
              );
            })}
          </div>

          <button
            type="submit"
            disabled={submitting || selectedCount === 0}
            className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? "Submitting…" : `Submit ${selectedCount} skill${selectedCount !== 1 ? "s" : ""}`}
          </button>
        </form>
      )}
    </div>
  );
}

function DiscoveryCard({
  draft, onToggleSelect, onToggleExpand, onUpdate, onTogglePlatform,
}: {
  draft: SkillDraft;
  onToggleSelect: () => void;
  onToggleExpand: () => void;
  onUpdate: (patch: Partial<SkillDraft>) => void;
  onTogglePlatform: (p: string) => void;
}) {
  const isRegistered = !!draft.snapshot.existing_slug;
  const succeeded = draft.result && !draft.result.error;
  const failed = draft.result && !!draft.result.error;

  const addDraftLabel = (name: string) => {
    if (!draft.labels.includes(name)) onUpdate({ labels: [...draft.labels, name] });
  };
  const removeDraftLabel = (name: string) =>
    onUpdate({ labels: draft.labels.filter((l) => l !== name) });

  return (
    <div className={`rounded-md border ${
      succeeded ? "border-green-300 bg-green-50" :
      failed ? "border-destructive/30 bg-destructive/5" :
      isRegistered ? "opacity-60 bg-muted" : "bg-background"
    }`}>
      {/* Header row */}
      <div className="flex items-center gap-2 px-3 py-2">
        <input
          type="checkbox"
          checked={draft.selected}
          disabled={isRegistered || !!draft.result}
          onChange={onToggleSelect}
          className="h-4 w-4 rounded border-input accent-primary"
        />
        <button type="button" onClick={onToggleExpand} className="flex-1 flex items-center gap-1.5 text-left min-w-0">
          {draft.expanded ? <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />}
          <span className={`font-mono text-xs truncate ${succeeded ? "text-green-700" : failed ? "text-destructive" : "text-muted-foreground"}`}>{draft.snapshot.ref.path || "/"}</span>
          {draft.name && <span className={`text-sm font-medium truncate ${succeeded ? "text-green-800" : failed ? "text-destructive" : ""}`}>{draft.name}</span>}
        </button>
        {succeeded && draft.result?.slug && (
          <Link href={`/skills/${draft.result.slug}`} className="text-xs text-green-700 underline shrink-0">View →</Link>
        )}
        {failed && (
          <span className="text-xs text-destructive shrink-0">{draft.result?.error}</span>
        )}
        {!draft.result && isRegistered && (
          <span className="text-xs text-muted-foreground shrink-0">
            Already in catalog —{" "}
            <Link href={`/skills/${draft.snapshot.existing_slug}`} className="underline">view →</Link>
          </span>
        )}
      </div>

      {/* Expanded editor */}
      {draft.expanded && !isRegistered && (
        <div className="border-t px-3 py-3 space-y-3">
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Name</label>
            <input value={draft.name} onChange={(e) => onUpdate({ name: e.target.value })}
              placeholder="Auto-filled"
              className="w-full rounded border border-input bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Description</label>
            <textarea value={draft.description} onChange={(e) => onUpdate({ description: e.target.value })}
              placeholder="Auto-filled" rows={2}
              className="w-full rounded border border-input bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none" />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Platforms</label>
            <div className="flex flex-wrap gap-1.5">
              {PLATFORM_SUGGESTIONS.map((p) => (
                <button key={p} type="button" onClick={() => onTogglePlatform(p)}
                  className={`rounded-full px-2 py-0.5 text-xs font-medium border transition-colors ${platformPillClass(p, draft.platforms.includes(p))}`}>{p}</button>
              ))}
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Labels</label>
            <LabelPicker
              labels={draft.labels}
              onAdd={addDraftLabel}
              onRemove={removeDraftLabel}
              canRemoveAll
              suggestionLimit={8}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">Version</label>
              <input value={draft.version} onChange={(e) => onUpdate({ version: e.target.value })} placeholder="1.0.0"
                className="w-full rounded border border-input bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">License</label>
              <input value={draft.license} onChange={(e) => onUpdate({ license: e.target.value })} placeholder="MIT"
                className="w-full rounded border border-input bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ScanErrorBanner({
  kind, message, onRetry,
}: {
  kind: "not_found" | "rate_limit" | "timeout" | "generic";
  message: string;
  onRetry: () => void;
}) {
  if (kind === "not_found") {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive flex items-start gap-2">
        <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
        <span>{message || "Repository or path not found. Check the URL and try again."}</span>
      </div>
    );
  }
  if (kind === "rate_limit") {
    return (
      <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800 flex items-start gap-2">
        <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
        <span>GitHub rate limit reached. Wait a moment then <button type="button" onClick={onRetry} className="underline font-medium">retry</button>.</span>
      </div>
    );
  }
  if (kind === "timeout") {
    return (
      <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800 flex items-start gap-2">
        <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
        <span>Scan timed out. <button type="button" onClick={onRetry} className="underline font-medium">Retry</button></span>
      </div>
    );
  }
  return (
    <div className="rounded-md border border-yellow-300 bg-yellow-50 px-3 py-2 text-sm text-yellow-800 flex items-start gap-2">
      <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
      <span>{message}</span>
    </div>
  );
}
