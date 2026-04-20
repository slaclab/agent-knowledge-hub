import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-4 text-center">
      <h1 className="text-4xl font-bold">404</h1>
      <p className="text-muted-foreground">Page not found.</p>
      <Link href="/skills" className="text-primary underline text-sm">
        Back to skill catalog
      </Link>
    </div>
  );
}
