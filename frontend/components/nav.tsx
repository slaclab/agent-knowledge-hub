"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { BookOpen, Search } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useCallback } from "react";

export function Nav() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [q, setQ] = useState(searchParams.get("q") ?? "");

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const params = new URLSearchParams(searchParams.toString());
      if (q) {
        params.set("q", q);
      } else {
        params.delete("q");
      }
      params.delete("page");
      router.push(`/skills?${params}`);
    },
    [q, router, searchParams],
  );

  return (
    <header className="border-b bg-background sticky top-0 z-50">
      <div className="container flex h-14 items-center gap-4">
        <Link href="/skills" className="flex items-center gap-2 font-semibold text-sm">
          <BookOpen className="h-5 w-5 text-primary" />
          Agent Knowledge Hub
        </Link>

        <form onSubmit={handleSearch} className="flex-1 max-w-md">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground pointer-events-none" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search skills…"
              className="w-full rounded-md border border-input bg-background pl-8 pr-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </form>

        <nav className="ml-auto flex items-center gap-3">
          <Link
            href="/guides"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Guides
          </Link>
          <Link
            href="/labels"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Labels
          </Link>
          {!loading && user && (
            <Link
              href="/skills/submit"
              className="inline-flex items-center rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Submit Skill
            </Link>
          )}
          {!loading && user?.is_admin && (
            <Link
              href="/admin/labels"
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Admin
            </Link>
          )}
          {!loading && user && (
            <span className="text-xs text-muted-foreground">{user.user_id}</span>
          )}
        </nav>
      </div>
    </header>
  );
}
