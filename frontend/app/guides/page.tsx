import Link from "next/link";

export default function GuidesPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-10">
      <div>
        <h1 className="text-3xl font-bold">Guides</h1>
        <p className="text-muted-foreground mt-2">
          Everything you need to discover, create, and manage agent skills.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {[
          {
            href: "/guides/what-is-a-skill",
            title: "What is an agent skill?",
            description: "SOPs, repeatable workflows, domain hints — why skills matter.",
          },
          {
            href: "/guides/why-agent-knowledge-hub",
            title: "Why use Agent Knowledge Hub?",
            description: "Centralised catalog, labels, provenance, quality signals, and in-agent install.",
          },
          {
            href: "/guides/agent-knowledge-hub",
            title: "Using /agent-knowledge-hub",
            description: "Discover, install, rate, and submit skills without leaving your agent session.",
          },
          {
            href: "/guides/create-a-skill",
            title: "How to create a skill",
            description: "A skill is a Markdown file in a GitHub repo. Creating one takes minutes.",
          },
          {
            href: "/guides/slac-github-access",
            title: "SLAC GitHub access",
            description: "Link your GitHub account via SLAC SSO to access internal repos.",
          },
          {
            href: "/guides/troubleshooting",
            title: "Troubleshooting",
            description: "Common issues with submissions, auth, stale metadata, and installs.",
          },
        ].map(({ href, title, description }) => (
          <Link
            key={href}
            href={href}
            className="rounded-lg border p-4 hover:bg-muted/50 transition-colors space-y-1"
          >
            <p className="font-semibold text-sm">{title} →</p>
            <p className="text-xs text-muted-foreground">{description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
