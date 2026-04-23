import Link from "next/link";

export default function TroubleshootingPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-10">
      <div>
        <p className="text-sm text-muted-foreground mb-2">
          <Link href="/guides" className="hover:underline">Guides</Link>
          {" / "}
          Troubleshooting
        </p>
        <h1 className="text-3xl font-bold">Troubleshooting</h1>
        <p className="text-muted-foreground mt-2">
          Common issues and how to fix them.
        </p>
      </div>

      <section className="space-y-4">
        <details className="rounded-lg border p-4 open:pb-4">
          <summary className="font-medium cursor-pointer text-sm">
            My submission failed — GitHub fetch error
          </summary>
          <div className="mt-3 text-sm text-muted-foreground space-y-2">
            <p>
              This usually means the repo is private or the URL is incorrect. Make sure:
            </p>
            <ul className="list-disc list-inside space-y-1">
              <li>The URL format is exactly <code className="bg-muted rounded px-1 font-mono text-xs">https://github.com/owner/repo</code></li>
              <li>The repository is set to Public on GitHub</li>
            </ul>
            <p>
              If GitHub is temporarily unreachable, you can still submit with a manual description
              and re-fetch later from the skill&apos;s edit page.
            </p>
          </div>
        </details>

        <details className="rounded-lg border p-4 open:pb-4">
          <summary className="font-medium cursor-pointer text-sm">
            I can browse but can&apos;t rate or label — auth issue
          </summary>
          <div className="mt-3 text-sm text-muted-foreground space-y-2">
            <p>
              Rating and labeling require a valid SLAC VouchProxy session. If you see{" "}
              <em>&ldquo;Your session has expired&rdquo;</em>, refresh the page to re-authenticate.
            </p>
            <p>
              If the Submit button is not visible, your session may have expired. A page refresh
              should restore your session.
            </p>
          </div>
        </details>

        <details className="rounded-lg border p-4 open:pb-4">
          <summary className="font-medium cursor-pointer text-sm">
            My skill shows stale information — how to re-fetch
          </summary>
          <div className="mt-3 text-sm text-muted-foreground">
            <p>
              Go to your skill&apos;s detail page and click Edit. From the edit page you can
              trigger a re-fetch from GitHub, which will update the name, description, README,
              stars, and last commit date.
            </p>
          </div>
        </details>

        <details className="rounded-lg border p-4 open:pb-4">
          <summary className="font-medium cursor-pointer text-sm">
            Skill not found after installing via /agent-knowledge-hub
          </summary>
          <div className="mt-3 text-sm text-muted-foreground space-y-2">
            <p>
              Check that{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">~/.claude/skills/&lt;slug&gt;/</code>{" "}
              was created and contains a{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">SKILL.md</code> or{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">plugin.json</code> file.
              You may need to restart your Claude Code session for the new skill to be recognised.
            </p>
          </div>
        </details>

        <details className="rounded-lg border p-4 open:pb-4">
          <summary className="font-medium cursor-pointer text-sm">
            GitHub rate limit error during install
          </summary>
          <div className="mt-3 text-sm text-muted-foreground space-y-2">
            <p>
              Unauthenticated requests to the GitHub Contents API are limited to 60/hour per IP.
              Set a <code className="bg-muted rounded px-1 font-mono text-xs">GITHUB_TOKEN</code>{" "}
              environment variable with a personal access token to raise the limit to 5,000/hour.
            </p>
          </div>
        </details>

        <details className="rounded-lg border p-4 open:pb-4">
          <summary className="font-medium cursor-pointer text-sm">
            Who do I contact if something is broken?
          </summary>
          <div className="mt-3 text-sm text-muted-foreground">
            <p>
              Reach out in the <strong>#comp-sdf</strong> Slack channel on the SLAC workspace,
              or open an issue on the project GitHub repository.
            </p>
          </div>
        </details>
      </section>

      <div className="text-sm text-muted-foreground">
        <Link href="/guides" className="text-primary underline">← Back to all guides</Link>
      </div>
    </div>
  );
}
