"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { updateSkill } from "@/lib/api";
import type { Skill } from "@/types/skill";
import { PLATFORM_SUGGESTIONS } from "@/lib/utils";
import { platformPillClass } from "@/components/platform-badges";
import { LabelSection } from "@/components/label-section";

interface EditFormProps {
  skill: Skill;
}

export function EditForm({ skill }: EditFormProps) {
  const router = useRouter();
  const [name, setName] = useState(skill.name);
  const [description, setDescription] = useState(skill.description ?? "");
  const [version, setVersion] = useState(skill.version ?? "");
  const [license, setLicense] = useState(skill.license ?? "");
  const [platforms, setPlatforms] = useState<string[]>(skill.compatible_platforms);
  const [platformInput, setPlatformInput] = useState("");
  const [changelog, setChangelog] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const togglePlatform = (p: string) => {
    setPlatforms((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p],
    );
  };

  const addCustomPlatform = () => {
    const p = platformInput.trim().toLowerCase();
    if (p && !platforms.includes(p)) setPlatforms((prev) => [...prev, p]);
    setPlatformInput("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    const { data, error: err } = await updateSkill(skill.slug, {
      name: name || undefined,
      description: description || undefined,
      compatible_platforms: platforms.length ? platforms : undefined,
      version: version || undefined,
      license: license || undefined,
      changelog_note: changelog || undefined,
    });
    setSubmitting(false);
    if (err) { setError(err); return; }
    if (data) router.push(`/skills/${data.slug}`);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-1">
        <label className="text-sm font-medium">Name</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      <div className="space-y-1">
        <label className="text-sm font-medium">Description</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
        />
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">Compatible Platforms</label>
        <div className="flex flex-wrap gap-2">
          {PLATFORM_SUGGESTIONS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => togglePlatform(p)}
              className={`rounded-full px-3 py-1 text-xs font-medium border transition-colors ${platformPillClass(p, platforms.includes(p))}`}
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
                className={`rounded-full px-3 py-1 text-xs font-medium border transition-colors ${platformPillClass(p, true)}`}
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

      <div className="space-y-2">
        <label className="text-sm font-medium">Labels</label>
        <LabelSection slug={skill.slug} initialLabels={skill.labels ?? []} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <label className="text-sm font-medium">Version</label>
          <input
            value={version}
            onChange={(e) => setVersion(e.target.value)}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">License</label>
          <input
            value={license}
            onChange={(e) => setLicense(e.target.value)}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>

      <div className="space-y-1">
        <label className="text-sm font-medium">Changelog Note</label>
        <textarea
          value={changelog}
          onChange={(e) => setChangelog(e.target.value.slice(0, 280))}
          placeholder="Describe what changed (optional, max 280 chars)"
          rows={2}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
        />
        <p className="text-xs text-muted-foreground text-right">{changelog.length}/280</p>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? "Saving…" : "Save Changes"}
      </button>
    </form>
  );
}
