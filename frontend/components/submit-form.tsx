"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getGithubPreview, createSkill } from "@/lib/api";
import type { GitHubPreview } from "@/types/skill";
import { PLATFORM_SUGGESTIONS } from "@/lib/utils";
import { Star } from "lucide-react";

export function SubmitForm() {
  const router = useRouter();
  const [repoUrl, setRepoUrl] = useState("");
  const [preview, setPreview] = useState<GitHubPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [version, setVersion] = useState("");
  const [license, setLicense] = useState("");
  const [platforms, setPlatforms] = useState<string[]>([]);
  const [platformInput, setPlatformInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleRepoBlur = useCallback(async () => {
    if (!repoUrl) return;
    setPreviewLoading(true);
    setPreviewError(null);
    setPreview(null);
    const { data, error } = await getGithubPreview(repoUrl);
    if (error) {
      setPreviewError(error);
    } else if (data) {
      setPreview(data);
      if (!name) setName(data.name);
      if (!description && data.description) setDescription(data.description);
      if (!license && data.license) setLicense(data.license);
    }
    setPreviewLoading(false);
  }, [repoUrl, name, description, license]);

  const togglePlatform = (p: string) => {
    setPlatforms((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p],
    );
  };

  const addCustomPlatform = () => {
    const p = platformInput.trim().toLowerCase();
    if (p && !platforms.includes(p)) {
      setPlatforms((prev) => [...prev, p]);
    }
    setPlatformInput("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    const { data, error } = await createSkill({
      repo_url: repoUrl,
      name: name || undefined,
      description: description || undefined,
      compatible_platforms: platforms.length ? platforms : undefined,
      version: version || undefined,
      license: license || undefined,
    });
    setSubmitting(false);
    if (error) {
      setSubmitError(error);
      return;
    }
    if (data) router.push(`/skills/${data.slug}`);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Repo URL */}
      <div className="space-y-1">
        <label className="text-sm font-medium">
          GitHub Repository URL <span className="text-destructive">*</span>
        </label>
        <input
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          onBlur={handleRepoBlur}
          placeholder="https://github.com/slaclab/my-skill"
          required
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
        {previewLoading && (
          <p className="text-xs text-muted-foreground">Fetching repo info…</p>
        )}
        {previewError && (
          <div className="rounded-md border border-yellow-300 bg-yellow-50 px-3 py-2 text-sm text-yellow-800">
            {previewError}
          </div>
        )}
        {preview && (
          <div className="rounded-md border bg-muted px-3 py-2 space-y-0.5">
            <div className="flex items-center gap-2">
              <span className="font-medium text-sm">{preview.name}</span>
              {preview.stars > 0 && (
                <span className="flex items-center gap-0.5 text-xs text-muted-foreground">
                  <Star className="h-3 w-3" />
                  {preview.stars}
                </span>
              )}
            </div>
            {preview.description && (
              <p className="text-xs text-muted-foreground">{preview.description}</p>
            )}
          </div>
        )}
      </div>

      {/* Name */}
      <div className="space-y-1">
        <label className="text-sm font-medium">Name</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Auto-filled from GitHub"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      {/* Description */}
      <div className="space-y-1">
        <label className="text-sm font-medium">Description</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Auto-filled from GitHub"
          rows={3}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
        />
      </div>

      {/* Compatible Platforms */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Compatible Platforms</label>
        <div className="flex flex-wrap gap-2">
          {PLATFORM_SUGGESTIONS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => togglePlatform(p)}
              className={`rounded-full px-3 py-1 text-xs font-medium border transition-colors ${
                platforms.includes(p)
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-background text-foreground border-input hover:bg-muted"
              }`}
            >
              {p}
            </button>
          ))}
          {platforms
            .filter((p) => !PLATFORM_SUGGESTIONS.includes(p as typeof PLATFORM_SUGGESTIONS[number]))
            .map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => togglePlatform(p)}
                className="rounded-full px-3 py-1 text-xs font-medium border bg-primary text-primary-foreground border-primary"
              >
                {p} ×
              </button>
            ))}
        </div>
        <div className="flex gap-2">
          <input
            value={platformInput}
            onChange={(e) => setPlatformInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustomPlatform())}
            placeholder="Add custom platform…"
            className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <button
            type="button"
            onClick={addCustomPlatform}
            className="rounded-md border border-input bg-background px-3 py-1.5 text-sm hover:bg-muted transition-colors"
          >
            Add
          </button>
        </div>
      </div>

      {/* Version + License */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <label className="text-sm font-medium">Version</label>
          <input
            value={version}
            onChange={(e) => setVersion(e.target.value)}
            placeholder="1.0.0"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">License</label>
          <input
            value={license}
            onChange={(e) => setLicense(e.target.value)}
            placeholder="MIT"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>

      {submitError && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {submitError}
        </div>
      )}

      <button
        type="submit"
        disabled={submitting || !repoUrl}
        className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? "Submitting…" : "Submit Skill"}
      </button>
    </form>
  );
}
