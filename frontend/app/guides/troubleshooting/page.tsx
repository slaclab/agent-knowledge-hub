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
            /agent-knowledge-hub says it found no S3DF sign-in, or that the catalog did not accept it
          </summary>
          <div className="mt-3 text-sm text-muted-foreground space-y-2">
            <p>
              Every catalog command sends your S3DF sign-in. When the token file is missing, holds
              something that is not a token, or holds a token the catalog refuses, the client shows
              these steps:
            </p>
            <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">
{`To sign in again:
  - In Cogito: open Cogito in a new private browser window and sign in.
  - On an S3DF node outside Cogito: run  s3df login
    (if the shell cannot find s3df: /sdf/sw/s3df-cli/bin/s3df login)
  - On a computer outside S3DF: use this client from Cogito or from an S3DF node.
Then ask again here; this session does not need to restart.
If the same message comes back right after you sign in, the problem is probably
on the catalog's side: report it at https://agent-knowledge-hub.slac.stanford.edu`}
            </pre>
            <p>
              See 
              <Link href="/guides/agent-knowledge-hub#cli-auth" className="text-primary underline">CLI authentication</Link> 
              for where the client looks for the token.
            </p>
          </div>
        </details>

        <details className="rounded-lg border p-4 open:pb-4">
          <summary className="font-medium cursor-pointer text-sm">
            /agent-knowledge-hub says the catalog&apos;s certificate could not be checked (curl exit 60)
          </summary>
          <div className="mt-3 text-sm text-muted-foreground space-y-2">
            <p>
              The client sends your sign-in only over a connection it can check against the
              computer&apos;s own certificates, so it does not work through a proxy that decrypts
              HTTPS. If this session runs behind such a proxy, for example Claude Code&apos;s sandbox
              with <code className="bg-muted rounded px-1 font-mono text-xs">network.tlsTerminate</code> set, use the client from a session without it.
            </p>
          </div>
        </details>

        <details className="rounded-lg border p-4 open:pb-4">
          <summary className="font-medium cursor-pointer text-sm">
            Claude Code asks before every catalog request again after a client update
          </summary>
          <div className="mt-3 text-sm text-muted-foreground space-y-2">
            <p>
              For a plugin install, the path of the client&apos;s request script holds the
              plugin&apos;s version, so a saved rule stops matching after each update. Add the rule
              for the new path, which the client prints the first time it contacts the catalog in a
              conversation. See 
              <Link href="/guides/agent-knowledge-hub#cli-auth" className="text-primary underline">CLI authentication</Link>.
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
