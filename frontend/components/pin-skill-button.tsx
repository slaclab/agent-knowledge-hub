"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { pinSkill } from "@/lib/api";

interface PinSkillButtonProps {
  slug: string;
}

export function PinSkillButton({ slug }: PinSkillButtonProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const handlePin = async () => {
    setLoading(true);
    setError(null);
    const { error: err } = await pinSkill(slug);
    setLoading(false);
    if (err) {
      setError(err);
    } else {
      router.refresh();
    }
  };

  return (
    <div className="space-y-1">
      <button
        onClick={handlePin}
        disabled={loading}
        className="inline-flex items-center gap-1.5 rounded-md border border-sky-300 bg-sky-50 px-3 py-1.5 text-sm text-sky-800 hover:bg-sky-100 transition-colors disabled:opacity-50"
      >
        {loading ? "Updating…" : "Update to latest"}
      </button>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
