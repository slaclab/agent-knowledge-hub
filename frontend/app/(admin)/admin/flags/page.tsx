"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, ShieldOff } from "lucide-react";
import type { FlaggedSkillItem } from "@/types/skill";

async function fetchFlaggedSkills(): Promise<FlaggedSkillItem[]> {
  const r = await fetch("/api/admin/flags?page_size=100");
  if (!r.ok) return [];
  const data = await r.json();
  return data.items ?? [];
}

async function deactivate(slug: string, reason: string): Promise<{ ok: boolean; error?: string }> {
  const r = await fetch(`/api/admin/skills/${encodeURIComponent(slug)}/deactivate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  if (!r.ok) {
    const j = await r.json().catch(() => ({}));
    return { ok: false, error: (j as { detail?: string }).detail ?? "Failed" };
  }
  return { ok: true };
}

export default function AdminFlagsPage() {
  const [items, setItems] = useState<FlaggedSkillItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [deactivating, setDeactivating] = useState<string | null>(null);
  const [deactivateReason, setDeactivateReason] = useState<Record<string, string>>({});
  const [deactivated, setDeactivated] = useState<Set<string>>(new Set());
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    fetchFlaggedSkills().then((data) => {
      setItems(data);
      setLoading(false);
    });
  }, []);

  async function handleDeactivate(slug: string) {
    const reason = deactivateReason[slug]?.trim();
    if (!reason) return;
    setDeactivating(slug);
    setErrors((prev) => ({ ...prev, [slug]: "" }));
    const result = await deactivate(slug, reason);
    setDeactivating(null);
    if (result.ok) {
      setDeactivated((prev) => new Set([...prev, slug]));
    } else {
      setErrors((prev) => ({ ...prev, [slug]: result.error ?? "Failed" }));
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-5 w-5 text-yellow-600" />
        <h1 className="text-2xl font-bold">Flagged Skills</h1>
      </div>

      {loading && <p className="text-muted-foreground">Loading…</p>}

      {!loading && items.length === 0 && (
        <p className="text-muted-foreground">No flagged skills. Queue is clean.</p>
      )}

      {!loading && items.length > 0 && (
        <div className="space-y-4">
          {items.map((item) => (
            <div key={item.skill_slug} className="rounded-lg border p-4 space-y-3">
              <div className="flex items-center justify-between gap-4">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <Link
                      href={`/skills/${item.skill_slug}`}
                      className="font-semibold hover:underline"
                    >
                      {item.skill_name}
                    </Link>
                    <span className="rounded-full bg-yellow-100 text-yellow-800 px-2 py-0.5 text-xs font-medium">
                      {item.flag_count} flag{item.flag_count !== 1 ? "s" : ""}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground font-mono">{item.skill_slug}</p>
                </div>

                {deactivated.has(item.skill_slug) ? (
                  <span className="inline-flex items-center gap-1 rounded-md bg-destructive/10 text-destructive px-3 py-1.5 text-sm font-medium">
                    <ShieldOff className="h-4 w-4" />
                    Deactivated
                  </span>
                ) : (
                  <div className="flex items-end gap-2">
                    <div className="space-y-1">
                      <input
                        type="text"
                        placeholder="Deactivation reason (required)"
                        value={deactivateReason[item.skill_slug] ?? ""}
                        onChange={(e) =>
                          setDeactivateReason((prev) => ({ ...prev, [item.skill_slug]: e.target.value }))
                        }
                        className="rounded-md border bg-background px-3 py-1.5 text-sm w-64"
                      />
                      {errors[item.skill_slug] && (
                        <p className="text-xs text-destructive">{errors[item.skill_slug]}</p>
                      )}
                    </div>
                    <button
                      className="inline-flex items-center gap-1.5 rounded-md border border-destructive/50 bg-destructive/5 px-3 py-1.5 text-sm text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
                      onClick={() => handleDeactivate(item.skill_slug)}
                      disabled={deactivating === item.skill_slug || !deactivateReason[item.skill_slug]?.trim()}
                    >
                      <ShieldOff className="h-4 w-4" />
                      {deactivating === item.skill_slug ? "Deactivating…" : "Deactivate"}
                    </button>
                  </div>
                )}
              </div>

              {/* Flag list */}
              {item.flags.length > 0 && (
                <div className="rounded-md bg-muted/40 p-3 space-y-2">
                  {item.flags.map((flag, i) => (
                    <div key={i} className="text-sm space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{flag.reporter_id}</span>
                        <span className="rounded-full bg-yellow-100 text-yellow-700 px-1.5 py-0.5 text-xs">
                          {flag.reason}
                        </span>
                        <span className="text-xs text-muted-foreground ml-auto">
                          {new Date(flag.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      {flag.note && (
                        <p className="text-muted-foreground text-xs pl-1">{flag.note}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
