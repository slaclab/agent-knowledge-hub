"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createSkillset } from "@/lib/api";
import { deriveSlug } from "@/lib/skillset";

const inputClass =
  "w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring";

export function SkillsetCreateForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestedSlug, setSuggestedSlug] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuggestedSlug(null);
    // An empty slug is left out, so the backend derives one from the name.
    const { data, error: err, suggestedSlug: suggested } = await createSkillset({
      name: name.trim(),
      slug: slug || undefined,
      description,
    }).catch(() => ({ data: null, error: "Could not create the skillset. Try again.", suggestedSlug: null }));
    if (data) {
      router.push(`/skillsets/${data.slug}`);
      return;
    }
    setSubmitting(false);
    if (suggested) setSuggestedSlug(suggested);
    else setError(err);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1">
        <label htmlFor="skillset-name" className="text-sm font-medium">
          Name <span className="text-destructive">*</span>
        </label>
        <input
          id="skillset-name"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            if (!slugEdited) setSlug(deriveSlug(e.target.value));
          }}
          required
          maxLength={200}
          className={inputClass}
        />
      </div>

      <div className="space-y-1">
        <label htmlFor="skillset-slug" className="text-sm font-medium">
          Slug
        </label>
        <p className="text-xs text-muted-foreground">
          The skillset&apos;s address and install name. It cannot be changed later.
        </p>
        <input
          id="skillset-slug"
          value={slug}
          onChange={(e) => {
            setSlug(e.target.value);
            setSlugEdited(true);
            setSuggestedSlug(null);
          }}
          pattern="[a-z0-9]([a-z0-9\-]*[a-z0-9])?"
          title="Lowercase letters, digits and hyphens, starting and ending with a letter or digit"
          maxLength={100}
          className={`${inputClass} font-mono`}
        />
        {suggestedSlug && (
          <p className="text-xs text-destructive">
            Slug already taken. Try:{" "}
            <button
              type="button"
              onClick={() => {
                setSlug(suggestedSlug);
                setSlugEdited(true);
                setSuggestedSlug(null);
              }}
              className="font-mono underline hover:no-underline"
            >
              {suggestedSlug}
            </button>
          </p>
        )}
      </div>

      <div className="space-y-1">
        <label htmlFor="skillset-description" className="text-sm font-medium">
          Description
        </label>
        <textarea
          id="skillset-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={2000}
          rows={4}
          className={inputClass}
        />
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <button
        type="submit"
        disabled={submitting || !name.trim()}
        className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? "Creating…" : "Create skillset"}
      </button>
    </form>
  );
}
