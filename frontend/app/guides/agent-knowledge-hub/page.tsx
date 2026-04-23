import Link from "next/link";

export default function AgentKnowledgeHubGuidePage() {
  return (
    <div className="max-w-3xl mx-auto space-y-10">
      <div>
        <p className="text-sm text-muted-foreground mb-2">
          <Link href="/guides" className="hover:underline">Guides</Link>
          {" / "}
          Using the /agent-knowledge-hub skill
        </p>
        <h1 className="text-3xl font-bold">The <code className="font-mono">/agent-knowledge-hub</code> Skill</h1>
        <p className="text-muted-foreground mt-2">
          Discover, install, rate, and submit catalog skills entirely from within your Claude Code
          session — no browser required.
        </p>
      </div>

      {/* One-time setup */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold">One-time setup</h2>
        <p className="text-sm text-muted-foreground">
          Register the SLAC S3DF marketplace and install the skill. You only need to do this once.
        </p>
        <div className="rounded-lg border p-5 space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            In your Claude Code session
          </p>
          <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">
{`# 1. Register the SLAC S3DF marketplace
/plugin marketplace add https://agent-knowledge-hub.slac.stanford.edu/cli/api/marketplace.json

# 2. Install the discovery skill
/plugin install agent-knowledge-hub`}
          </pre>
        </div>
        <p className="text-sm text-muted-foreground">
          After installation, the <code className="bg-muted rounded px-1 font-mono text-xs">/agent-knowledge-hub</code> slash
          command is available in every Claude Code session.
        </p>
      </section>

      <hr className="border-border" />

      {/* Commands */}
      <section className="space-y-6">
        <h2 className="text-xl font-semibold">Commands</h2>

        {/* Search */}
        <div className="space-y-2">
          <h3 className="font-semibold text-sm">Search the catalog</h3>
          <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">
{`/agent-knowledge-hub I need something to query EPICS
/agent-knowledge-hub find me a skill for analysing NeXus files
/agent-knowledge-hub search --label hdf5`}
          </pre>
          <p className="text-sm text-muted-foreground">
            Claude fetches the catalog and returns a ranked list of matches with a one-sentence
            explanation for each. You can then install any result directly from the same prompt.
          </p>
        </div>

        {/* Install */}
        <div className="space-y-2">
          <h3 className="font-semibold text-sm">Install a skill</h3>
          <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">
{`/agent-knowledge-hub install k8s-troubleshooting`}
          </pre>
          <p className="text-sm text-muted-foreground">
            Downloads the skill files from GitHub into{" "}
            <code className="bg-muted rounded px-1 font-mono text-xs">~/.claude/skills/&lt;slug&gt;/</code>.
            The skill runs a path traversal check on every file before writing — a skill with a
            malicious <code className="bg-muted rounded px-1 font-mono text-xs">skill_path</code> will
            be rejected and no files will be written.
          </p>
        </div>

        {/* List / update / remove */}
        <div className="space-y-2">
          <h3 className="font-semibold text-sm">Manage installed skills</h3>
          <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">
{`/agent-knowledge-hub list                  # show installed skills
/agent-knowledge-hub update k8s-troubleshooting   # pull latest version
/agent-knowledge-hub remove k8s-troubleshooting   # uninstall`}
          </pre>
        </div>

        {/* Rate */}
        <div className="space-y-2">
          <h3 className="font-semibold text-sm">Rate a skill</h3>
          <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">
{`/agent-knowledge-hub rate k8s-troubleshooting 5`}
          </pre>
          <p className="text-sm text-muted-foreground">
            Requires a SLAC token (see <a href="#cli-auth" className="text-primary underline">CLI authentication</a> below).
            Ratings are tied to your SLAC identity and count towards the catalog&apos;s average rating.
          </p>
        </div>

        {/* Create */}
        <div className="space-y-2">
          <h3 className="font-semibold text-sm">Scaffold a new skill</h3>
          <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">
{`/agent-knowledge-hub create`}
          </pre>
          <p className="text-sm text-muted-foreground">
            Walks you through a name and description, then writes a{" "}
            <code className="bg-muted rounded px-1 font-mono text-xs">SKILL.md</code> template to
            a directory you choose. Once your skill is in a GitHub repo, use{" "}
            <code className="bg-muted rounded px-1 font-mono text-xs">/agent-knowledge-hub submit</code> to
            add it to the catalog.
          </p>
        </div>

        {/* Submit */}
        <div className="space-y-2">
          <h3 className="font-semibold text-sm">Submit to the catalog</h3>
          <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">
{`/agent-knowledge-hub submit`}
          </pre>
          <p className="text-sm text-muted-foreground">
            Prints the web submission URL for your skill&apos;s GitHub repo. Direct API submission
            from the CLI is planned for a future version.
          </p>
        </div>
      </section>

      <hr className="border-border" />

      {/* CLI auth */}
      <section className="space-y-4" id="cli-auth">
        <h2 className="text-xl font-semibold">CLI authentication</h2>
        <p className="text-sm text-muted-foreground">
          Read-only commands (search, install, list) work without any authentication.
          Write commands (<code className="bg-muted rounded px-1 font-mono text-xs">rate</code>) require
          a SLAC token.
        </p>
        <div className="rounded-lg border p-5 space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Authenticate once with s3df login
          </p>
          <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">
{`s3df login`}
          </pre>
          <p className="text-xs text-muted-foreground">
            This writes a SLAC-issued JWT to{" "}
            <code className="bg-muted rounded px-1 font-mono text-xs">~/.s3df-access-token</code>.
            The skill reads this file automatically — you never need to paste a token manually.
          </p>
        </div>
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800 space-y-1">
          <p className="font-semibold">Token expiry</p>
          <p>
            If a write command returns <em>&ldquo;Token expired&rdquo;</em>, run{" "}
            <code className="bg-amber-100 rounded px-1 font-mono text-xs">s3df login</code> again
            to refresh your token, then retry the command.
          </p>
        </div>
      </section>

      <hr className="border-border" />

      {/* Troubleshooting */}
      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Troubleshooting</h2>
        <p className="text-sm text-muted-foreground">
          Having issues? See the{" "}
          <Link href="/guides/troubleshooting" className="text-primary underline">Troubleshooting guide</Link>{" "}
          for common problems with install, GitHub rate limits, auth errors, and more.
        </p>
      </section>

      {/* CTA */}
      <div className="rounded-lg border border-primary/30 bg-primary/5 p-5 flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex-1 space-y-1">
          <p className="font-semibold text-sm">Want to add your own skill to the catalog?</p>
          <p className="text-sm text-muted-foreground">
            Use <code className="bg-primary/10 rounded px-1 font-mono text-xs">/agent-knowledge-hub create</code> to
            scaffold a skill, push it to GitHub, then submit it from the web.
          </p>
        </div>
        <div className="flex gap-3 flex-shrink-0">
          <Link
            href="/guides"
            className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
          >
            All guides
          </Link>
          <Link
            href="/skills/submit"
            className="rounded-md bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            Submit a skill
          </Link>
        </div>
      </div>
    </div>
  );
}
