"use client";

import type { ReactNode } from "react";
import { useAuth } from "@/lib/auth";

interface AuthGuardProps {
  children: ReactNode;
  fallback?: ReactNode;
}

export function AuthGuard({ children, fallback = null }: AuthGuardProps) {
  const { user, loading } = useAuth();
  if (loading || !user) return <>{fallback}</>;
  return <>{children}</>;
}
