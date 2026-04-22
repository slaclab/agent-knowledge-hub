"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export function BfcacheRefresh() {
  const router = useRouter();
  useEffect(() => {
    function onPageShow(e: PageTransitionEvent) {
      if (e.persisted) router.refresh();
    }
    window.addEventListener("pageshow", onPageShow);
    return () => window.removeEventListener("pageshow", onPageShow);
  }, [router]);
  return null;
}
