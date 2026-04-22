"use client";

import { useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { getGithubScan, getGithubDiscover, createSkill, addLabel, removeLabel, listSkillLabels } from "@/lib/api";
import type { SkillScanSnapshot, DiscoverResult, LabelOut } from "@/types/skill";
import { PLATFORM_SUGGESTIONS } from "@/lib/utils";
import { labelColor } from "@/lib/label-color";
import { Star, AlertTriangle, AlertCircle, Loader2, ChevronDown, ChevronRight, X } from "lucide-react";
import Link from "next/link";

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
}

type BulkResult = { path: string; slug?: string; error?: string };

export function SubmitForm({
  accessInstructionsUrl = "/guides/slac-github-access",
}: {
  accessInstructionsUrl?: string;
}) {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [scanState, setScanState] = useState<ScanState>({ status: "idle" });
  const [discoverState, setDiscoverState] = useState<DiscoverState>({ status: "idle" });
  const [drafts, setDrafts] = useState<SkillDraft[]>([]);
  const [bulkResults, setBulkResults] = useState<BulkResult[]>([]);

  // Single-skill form fields
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [version, setVersion] = useState("");
  const [license, setLicense] = useState("");
  const [platforms, setPlatforms] = useState<string[]>([]);
  const [platformInput, setPlatformInput] = useState("");
  const [skillPath, setSkillPath] = useState("/");

  const [pendingLabels, setPendingLabels] = useState<LabelOut[]>([]);
  const [labelInput, setLabelInput] = useState("");
  const [labelSuggestions, setLabelSuggestions] = useState<LabelOut[]>([]);
  const [showLabelSuggestions, setShowLabelSuggestions] = useState(false);
  const labelInputRef = useRef<HTMLInputElement>(null);
  const labelSuggestionsRef = useRef<HTMLDivElement>(null);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [duplicateSlug, setDuplicateSlug] = useState<string | null>(null);
  const [createdSlug, setCreatedSlug] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  const runDiscover = useCallback(async (scanUrl: string) => {
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    setDiscoverState({ status: "discovering" });
    setBulkResults([]);

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
    setBulkResults([]);
    setSubmitError(null);
    setDuplicateSlug(null);

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

    const isSubdir = data.ref.path && data.ref.path !== "/" && data.ref.path !== "";
    if (isSubdir) {
      runDiscover(scanUrl);
      return;
    }

    if (!name && data.name) setName(data.name);
    if (!description && data.description) setDescription(data.description);
    if (!version && data.version) setVersion(data.version);
    if (!license && data.license) setLicense(data.license);
    if (platforms.length === 0 && data.compatible_platforms.length)
      setPlatforms(data.compatible_platforms);
    setSkillPath(data.ref.path === "" ? "/" : data.ref.path);
    if (data.existing_slug) setDuplicateSlug(data.existing_slug);
  }, [name, description, version, license, platforms, runDiscover]);

  const handleBlur = () => {
    if (scanState.status === "idle") runScan(url);
  };

  const togglePlatform = (p: string) =>
    setPlatforms((prev) => (prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]));

  const addCustomPlatform = () => {
    const p = platformInput.trim().toLowerCase();
    if (p && !platforms.includes(p)) setPlatforms((prev) => [...prev, p]);
    setPlatformInput("");
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

  const allNewSelected = drafts.filter((d) => !d.snapshot.existing_slug).every((d) => d.selected);

  const toggleSelectAll = () => {
    const next = !allNewSelected;
    setDrafts((prev) => prev.map((d) => (d.snapshot.existing_slug ? d : { ...d, selected: next })));
  };

  const selectedCount = drafts.filter((d) => d.selected).length;
  const totalCount = drafts.filter((d) => !d.snapshot.existing_slug).length;

  const handleBulkSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setBulkResults([]);
    const selected = drafts.filter((d) => d.selected);
    const results: BulkResult[] = [];
    for (const draft of selected) {
      const snap = draft.snapshot;
      const { data, error } = await createSkill({
        repo_url: `https://github.com/${snap.ref.owner}/${snap.ref.repo}`,
        skill_path: snap.ref.path || "/",
        name: draft.name || undefined,
        description: draft.description || undefined,
        compatible_platforms: draft.platforms.length ? draft.platforms : undefined,
        version: draft.version || undefined,
        license: draft.license || undefined,
      });
      results.push({ path: snap.ref.path || "/", slug: data?.slug, error: error ?? undefined });
      if (data?.slug && draft.labels.length > 0) {
        await Promise.all(draft.labels.map((l) => addLabel(data.slug, l)));
      }
    }
    setBulkResults(results);
    setSubmitting(false);
  };

  const handleSingleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    setDuplicateSlug(null);

    const snapshot = scanState.status === "done" ? scanState.snapshot : null;
    const { data, error } = await createSkill({
      repo_url: snapshot
        ? `https://github.com/${snapshot.ref.owner}/${snapshot.ref.repo}`
        : url,
      skill_path: skillPath,
      name: name || undefined,
      description: description || undefined,
      compatible_platforms: platforms.length ? platforms : undefined,
      version: version || undefined,
      license: license || undefined,
    });

    setSubmitting(false);
    if (error) {
      if (error.includes("already exists") || error.includes("409")) {
        const match = error.match(/\/skills\/([a-z0-9-]+)/);
        if (match) setDuplicateSlug(match[1]);
      }
      setSubmitError(error);
      return;
    }
    if (data) {
      // Apply any labels added before submission
      await Promise.all(pendingLabels.map((l) => addLabel(data.slug, l.name)));
      setCreatedSlug(data.slug);
    }
  };

  const snapshot = scanState.status === "done" ? scanState.snapshot : null;
  const scanning = scanState.status === "scanning";
  const discovering = discoverState.status === "discovering";
  const inDiscoveryMode = discoverState.status === "done" && drafts.length > 0;
  const isRootScan = snapshot?.ref.path === "/" || snapshot?.ref.path === "";

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

        {duplicateSlug && !inDiscoveryMode && (
          <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            This skill is already in the catalog.{" "}
            <Link href={`/skills/${duplicateSlug}`} className="underline font-medium">View existing entry →</Link>
          </div>
        )}

        {snapshot?.no_skill_files && !inDiscoveryMode && (
          <div className="rounded-md border border-yellow-300 bg-yellow-50 px-3 py-2 text-sm text-yellow-800 flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
            <span>No skill files found in this directory. You can still submit with manual metadata below.</span>
          </div>
        )}

        {snapshot && !inDiscoveryMode && (
          <div className="rounded-md border bg-muted px-3 py-2 space-y-0.5">
            <div className="flex items-center gap-2">
              <span className="font-medium text-sm">{snapshot.ref.owner}/{snapshot.ref.repo}</span>
              {snapshot.stars > 0 && (
                <span className="flex items-center gap-0.5 text-xs text-muted-foreground">
                  <Star className="h-3 w-3" />{snapshot.stars}
                </span>
              )}
            </div>
            {snapshot.ref.path && snapshot.ref.path !== "/" && (
              <p className="text-xs text-muted-foreground font-mono">{snapshot.ref.path}</p>
            )}
          </div>
        )}

        {snapshot?.visibility === "internal" && !inDiscoveryMode && (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            This repo requires SLAC GitHub access.
            {accessInstructionsUrl?.startsWith("http") && (
              <>{" "}<a href={accessInstructionsUrl} className="underline" target="_blank">Learn more</a></>
            )}
          </div>
        )}

        {/* Discover button — shown after a root-level scan */}
        {snapshot && discoverState.status === "idle" && (
          <button
            type="button"
            disabled={discovering}
            onClick={() => runDiscover(url)}
            className="text-sm text-primary underline hover:no-underline disabled:opacity-50"
          >
            {isRootScan ? "Scan entire repo for skills" : "Scan directory for more skills"}
          </button>
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
            More than 20 skill directories found — showing the first 20.
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

          <div className="space-y-2">
            {drafts.map((draft, i) => (
              <DiscoveryCard
                key={draft.snapshot.ref.path}
                draft={draft}
                onToggleSelect={() => updateDraft(i, { selected: !draft.selected })}
                onToggleExpand={() => updateDraft(i, { expanded: !draft.expanded })}
                onUpdate={(patch) => updateDraft(i, patch)}
                onTogglePlatform={(p) => toggleDraftPlatform(i, p)}
              />
            ))}
          </div>

          {bulkResults.length > 0 && (
            <div className="space-y-1">
              {bulkResults.map((r) => (
                <div
                  key={r.path}
                  className={`rounded-md px-3 py-2 text-sm flex items-center justify-between ${
                    r.error
                      ? "border border-destructive/30 bg-destructive/5 text-destructive"
                      : "border border-green-300 bg-green-50 text-green-800"
                  }`}
                >
                  <span className="font-mono text-xs">{r.path}</span>
                  {r.slug ? (
                    <Link href={`/skills/${r.slug}`} className="underline text-xs">View →</Link>
                  ) : (
                    <span className="text-xs">{r.error}</span>
                  )}
                </div>
              ))}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || selectedCount === 0}
            className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? "Submitting…" : `Submit ${selectedCount} of ${drafts.length} skill${drafts.length !== 1 ? "s" : ""}`}
          </button>
        </form>
      )}

      {/* Success: label tagging step */}
      {createdSlug && (
        <SuccessPanel slug={createdSlug} onDone={() => router.push(`/skills/${createdSlug}`)} />
      )}

      {/* Single-skill form — shown only after a successful scan (non-discovery mode) */}
      {!inDiscoveryMode && !createdSlug && scanState.status === "done" && (
        <form onSubmit={handleSingleSubmit} className="space-y-6">
          <div className="space-y-1">
            <label className="text-sm font-medium">Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Auto-filled from scan"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium">Description</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Auto-filled from scan" rows={3}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none" />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Compatible Platforms</label>
            <div className="flex flex-wrap gap-2">
              {PLATFORM_SUGGESTIONS.map((p) => (
                <button key={p} type="button" onClick={() => togglePlatform(p)}
                  className={`rounded-full px-3 py-1 text-xs font-medium border transition-colors ${
                    platforms.includes(p) ? "bg-primary text-primary-foreground border-primary" : "bg-background text-foreground border-input hover:bg-muted"
                  }`}>{p}</button>
              ))}
              {platforms.filter((p) => !PLATFORM_SUGGESTIONS.includes(p as (typeof PLATFORM_SUGGESTIONS)[number])).map((p) => (
                <button key={p} type="button" onClick={() => togglePlatform(p)}
                  className="rounded-full px-3 py-1 text-xs font-medium border bg-primary text-primary-foreground border-primary">{p} ×</button>
              ))}
            </div>
            <div className="flex gap-2">
              <input value={platformInput} onChange={(e) => setPlatformInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustomPlatform())}
                placeholder="Add custom platform…"
                className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
              <button type="button" onClick={addCustomPlatform}
                className="rounded-md border border-input bg-background px-3 py-1.5 text-sm hover:bg-muted transition-colors">Add</button>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Labels</label>
            <div className="flex flex-wrap gap-1.5">
              {pendingLabels.map((l) => (
                <span key={l.name} className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${labelColor(l.name)}`}>
                  {l.name}
                  <button type="button" onClick={() => setPendingLabels((prev) => prev.filter((x) => x.name !== l.name))}
                    className="ml-0.5 text-muted-foreground hover:text-foreground transition-colors" aria-label={`Remove ${l.name}`}>
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
            <div className="relative">
              <input
                ref={labelInputRef}
                value={labelInput}
                onChange={(e) => {
                  setLabelInput(e.target.value);
                  setShowLabelSuggestions(true);
                  if (e.target.value.trim()) {
                    fetch(`/api/labels?q=${encodeURIComponent(e.target.value.trim())}&limit=10`)
                      .then((r) => r.json()).then((d: LabelOut[]) => setLabelSuggestions(d)).catch(() => {});
                  } else {
                    setLabelSuggestions([]);
                  }
                }}
                onFocus={() => setShowLabelSuggestions(true)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    const trimmed = labelInput.trim().toLowerCase();
                    if (trimmed && !pendingLabels.find((l) => l.name === trimmed)) {
                      setPendingLabels((prev) => [...prev, { name: trimmed, usage_count: 0, applied_by_me: true }]);
                    }
                    setLabelInput("");
                    setShowLabelSuggestions(false);
                  }
                }}
                onBlur={() => setTimeout(() => setShowLabelSuggestions(false), 150)}
                placeholder="Add a label…"
                className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              {showLabelSuggestions && labelSuggestions.length > 0 && (
                <div ref={labelSuggestionsRef} className="absolute left-0 top-full mt-0.5 z-20 w-full rounded-md border bg-white dark:bg-zinc-900 shadow-lg">
                  {labelSuggestions.filter((s) => !pendingLabels.find((l) => l.name === s.name)).map((s) => (
                    <button key={s.name} type="button"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        setPendingLabels((prev) => [...prev, { name: s.name, usage_count: s.usage_count, applied_by_me: true }]);
                        setLabelInput("");
                        setShowLabelSuggestions(false);
                      }}
                      className="flex w-full items-center justify-between px-2.5 py-1 text-xs hover:bg-muted transition-colors"
                    >
                      <span>{s.name}</span>
                      <span className="text-muted-foreground tabular-nums">{s.usage_count}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-sm font-medium">Version</label>
              <input value={version} onChange={(e) => setVersion(e.target.value)} placeholder="1.0.0"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">License</label>
              <input value={license} onChange={(e) => setLicense(e.target.value)} placeholder="MIT"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
            </div>
          </div>

          {submitError && (
            <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
              {submitError}
            </div>
          )}

          <button type="submit" disabled={submitting || !url.trim() || scanning}
            className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
            {submitting ? "Submitting…" : "Submit Skill"}
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
  const [labelInput, setLabelInput] = useState("");
  const [labelSuggestions, setLabelSuggestions] = useState<LabelOut[]>([]);
  const [showLabelSuggestions, setShowLabelSuggestions] = useState(false);

  const addDraftLabel = (name: string) => {
    const trimmed = name.trim().toLowerCase();
    if (trimmed && !draft.labels.includes(trimmed)) {
      onUpdate({ labels: [...draft.labels, trimmed] });
    }
    setLabelInput("");
    setShowLabelSuggestions(false);
  };

  const removeDraftLabel = (name: string) =>
    onUpdate({ labels: draft.labels.filter((l) => l !== name) });

  return (
    <div className={`rounded-md border ${isRegistered ? "opacity-60 bg-muted" : "bg-background"}`}>
      {/* Header row */}
      <div className="flex items-center gap-2 px-3 py-2">
        <input
          type="checkbox"
          checked={draft.selected}
          disabled={isRegistered}
          onChange={onToggleSelect}
          className="h-4 w-4 rounded border-input accent-primary"
        />
        <button type="button" onClick={onToggleExpand} className="flex-1 flex items-center gap-1.5 text-left min-w-0">
          {draft.expanded ? <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />}
          <span className="font-mono text-xs text-muted-foreground truncate">{draft.snapshot.ref.path || "/"}</span>
          {draft.name && <span className="text-sm font-medium truncate">{draft.name}</span>}
        </button>
        {isRegistered && (
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
                  className={`rounded-full px-2 py-0.5 text-xs font-medium border transition-colors ${
                    draft.platforms.includes(p) ? "bg-primary text-primary-foreground border-primary" : "bg-background text-foreground border-input hover:bg-muted"
                  }`}>{p}</button>
              ))}
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Labels</label>
            <div className="flex flex-wrap gap-1">
              {draft.labels.map((l) => (
                <span key={l} className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${labelColor(l)}`}>
                  {l}
                  <button type="button" onClick={() => removeDraftLabel(l)} className="ml-0.5 text-muted-foreground hover:text-foreground transition-colors" aria-label={`Remove ${l}`}>
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
            <div className="relative">
              <input
                value={labelInput}
                onChange={(e) => {
                  setLabelInput(e.target.value);
                  setShowLabelSuggestions(true);
                  if (e.target.value.trim()) {
                    fetch(`/api/labels?q=${encodeURIComponent(e.target.value.trim())}&limit=8`)
                      .then((r) => r.json()).then((d: LabelOut[]) => setLabelSuggestions(d)).catch(() => {});
                  } else {
                    setLabelSuggestions([]);
                  }
                }}
                onFocus={() => setShowLabelSuggestions(true)}
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addDraftLabel(labelInput); } }}
                onBlur={() => setTimeout(() => setShowLabelSuggestions(false), 150)}
                placeholder="Add a label…"
                className="w-full rounded border border-input bg-background px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
              />
              {showLabelSuggestions && labelSuggestions.length > 0 && (
                <div className="absolute left-0 top-full mt-0.5 z-20 w-full rounded-md border bg-white dark:bg-zinc-900 shadow-lg">
                  {labelSuggestions.filter((s) => !draft.labels.includes(s.name)).map((s) => (
                    <button key={s.name} type="button"
                      onMouseDown={(e) => { e.preventDefault(); addDraftLabel(s.name); }}
                      className="flex w-full items-center justify-between px-2 py-1 text-xs hover:bg-muted transition-colors"
                    >
                      <span>{s.name}</span>
                      <span className="text-muted-foreground tabular-nums">{s.usage_count}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
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

function SuccessPanel({ slug, onDone }: { slug: string; onDone: () => void }) {
  const [labels, setLabels] = useState<LabelOut[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [suggestions, setSuggestions] = useState<LabelOut[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  const handleAdd = useCallback(async (name: string) => {
    const trimmed = name.trim().toLowerCase();
    if (!trimmed) return;
    setError(null);
    setInputValue("");
    setShowSuggestions(false);
    setPending(trimmed);
    const optimistic: LabelOut = { name: trimmed, usage_count: 0, applied_by_me: true };
    setLabels((prev) => (prev.find((l) => l.name === trimmed) ? prev : [...prev, optimistic]));
    const { data, error: err, status } = await addLabel(slug, trimmed);
    setPending(null);
    if (err || !data) {
      setLabels((prev) => prev.filter((l) => l !== optimistic));
      if (status === 409) setError("Already applied.");
      else if (status === 429) setError("Max 5 labels reached.");
      else setError(err ?? "Failed to add label.");
      return;
    }
    const fresh = await listSkillLabels(slug);
    setLabels(fresh);
  }, [slug]);

  const handleRemove = useCallback(async (name: string) => {
    setLabels((prev) => prev.filter((l) => l.name !== name));
    await removeLabel(slug, name);
    const fresh = await listSkillLabels(slug);
    setLabels(fresh);
  }, [slug]);

  return (
    <div className="rounded-lg border border-green-300 bg-green-50 p-5 space-y-4">
      <div className="space-y-1">
        <p className="font-semibold text-green-800">Skill submitted!</p>
        <p className="text-sm text-green-700">Add labels to help others discover it, or skip and go straight to the skill page.</p>
      </div>

      <div className="space-y-2">
        {labels.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {labels.map((label) => (
              <span
                key={label.name}
                className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${labelColor(label.name)}`}
              >
                {label.name}
                <button
                  type="button"
                  onClick={() => handleRemove(label.name)}
                  className="ml-0.5 opacity-60 hover:opacity-100 transition-opacity"
                  aria-label={`Remove ${label.name}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}

        <div className="relative">
          <input
            ref={inputRef}
            value={inputValue}
            disabled={pending !== null}
            onChange={(e) => { setInputValue(e.target.value); setShowSuggestions(true); setError(null);
              fetch(`/api/labels?q=${encodeURIComponent(e.target.value.trim())}&limit=8`)
                .then((r) => r.json()).then((d: LabelOut[]) => setSuggestions(d)).catch(() => {});
            }}
            onFocus={() => setShowSuggestions(true)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleAdd(inputValue); } }}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
            placeholder="Type a label and press Enter…"
            className="w-full rounded-md border border-input bg-white px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
          />
          {showSuggestions && suggestions.length > 0 && (
            <div ref={suggestionsRef} className="absolute left-0 top-full mt-0.5 z-20 w-full rounded-md border bg-white dark:bg-zinc-900 shadow-lg">
              {suggestions.map((s) => (
                <button key={s.name} type="button"
                  onMouseDown={(e) => { e.preventDefault(); handleAdd(s.name); }}
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
      </div>

      <div className="flex items-center gap-3 pt-1">
        <button
          type="button"
          onClick={onDone}
          className="rounded-md bg-green-700 text-white px-4 py-1.5 text-sm font-medium hover:bg-green-800 transition-colors"
        >
          Go to skill →
        </button>
        {labels.length === 0 && (
          <button type="button" onClick={onDone} className="text-sm text-green-700 underline hover:no-underline">
            Skip
          </button>
        )}
      </div>
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
        <span>Repository or path not found. Check the URL and try again.</span>
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
