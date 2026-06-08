"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { getUserSkills, getUserEdits, getUserInstalls } from "@/lib/api";
import type { PaginatedSkills, PaginatedInstalls, Skill } from "@/types/skill";
import { SkillCard } from "@/components/skill-card";
import { formatDate } from "@/lib/utils";

type Tab = "submitted" | "edited" | "installed";

interface UserActivityTabsProps {
  userId: string;
  canViewInstalls: boolean;
  isOwnProfile: boolean;
}

export function UserActivityTabs({ userId, canViewInstalls, isOwnProfile }: UserActivityTabsProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const rawTab = searchParams.get("tab");
  const activeTab: Tab =
    rawTab === "edited" || rawTab === "installed" ? rawTab : "submitted";

  const [submittedData, setSubmittedData] = useState<PaginatedSkills | null>(null);
  const [editedData, setEditedData] = useState<PaginatedSkills | null>(null);
  const [installsData, setInstallsData] = useState<PaginatedInstalls | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    if (activeTab === "submitted") {
      getUserSkills(userId).then((d) => { setSubmittedData(d); setLoading(false); });
    } else if (activeTab === "edited") {
      getUserEdits(userId).then((d) => { setEditedData(d); setLoading(false); });
    } else if (activeTab === "installed" && canViewInstalls) {
      getUserInstalls(userId).then((d) => { setInstallsData(d); setLoading(false); });
    } else {
      setLoading(false);
    }
  }, [activeTab, userId, canViewInstalls]);

  function setTab(tab: Tab) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", tab);
    router.push(`?${params}`, { scroll: false });
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "submitted", label: "Submitted" },
    { key: "edited", label: "Edited" },
    { key: "installed", label: "Installed" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex gap-1 border-b">
        {tabs.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === key
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {loading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {!loading && activeTab === "submitted" && (
        <>
          {submittedData && submittedData.total > 0 ? (
            <SkillGrid skills={submittedData.items} />
          ) : (
            <p className="text-sm text-muted-foreground py-4">No skills submitted yet.</p>
          )}
        </>
      )}

      {!loading && activeTab === "edited" && (
        <>
          {editedData && editedData.total > 0 ? (
            <SkillGrid skills={editedData.items} />
          ) : (
            <p className="text-sm text-muted-foreground py-4">No skills edited yet.</p>
          )}
        </>
      )}

      {!loading && activeTab === "installed" && (
        <>
          {!canViewInstalls ? (
            <div className="rounded-md border p-4 text-sm text-muted-foreground">
              {isOwnProfile
                ? "Sign in to view your install history."
                : `Install history is private to ${userId}.`}
            </div>
          ) : installsData && installsData.total > 0 ? (
            <InstallList items={installsData.items} />
          ) : (
            <p className="text-sm text-muted-foreground py-4">
              No skills installed yet. Run{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">install &lt;slug&gt;</code>{" "}
              in your AKH session to track installs here.
            </p>
          )}
        </>
      )}
    </div>
  );
}

function SkillGrid({ skills }: { skills: Skill[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {skills.map((s) => (
        <SkillCard key={s.id} skill={s} />
      ))}
    </div>
  );
}

function InstallList({ items }: { items: PaginatedInstalls["items"] }) {
  return (
    <ul className="space-y-2">
      {items.map((ev) => (
        <li key={ev.skill_slug} className="flex items-center justify-between rounded-md border px-4 py-3 text-sm gap-4">
          <div className="flex items-center gap-2 min-w-0">
            {ev.is_deleted ? (
              <span className="font-mono text-muted-foreground truncate">{ev.skill_slug}</span>
            ) : (
              <Link href={`/skills/${ev.skill_slug}`} className="font-medium hover:underline truncate">
                {ev.skill_name ?? ev.skill_slug}
              </Link>
            )}
            {ev.is_deleted && (
              <span className="shrink-0 text-xs text-muted-foreground">(no longer in catalog)</span>
            )}
            {ev.update_available && (
              <span className="shrink-0 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                Update available
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 shrink-0">
            {!ev.is_deleted && (
              <Link
                href={`/skills/${ev.skill_slug}`}
                className="text-xs text-muted-foreground hover:text-foreground hover:underline"
              >
                Re-install
              </Link>
            )}
            <time className="text-xs text-muted-foreground">Installed {formatDate(ev.installed_at)}</time>
          </div>
        </li>
      ))}
    </ul>
  );
}
