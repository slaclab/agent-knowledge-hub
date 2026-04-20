import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { Nav } from "@/components/nav";
import { Footer } from "@/components/footer";

export const metadata: Metadata = {
  title: "Agent Knowledge Hub",
  description: "Browse, share, and install agent skills for SLAC/S3DF",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col">
        <AuthProvider>
          <Suspense fallback={<header className="border-b h-14" />}>
            <Nav />
          </Suspense>
          <main className="flex-1 container py-8">{children}</main>
          <Footer />
        </AuthProvider>
      </body>
    </html>
  );
}
