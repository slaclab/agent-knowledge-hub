import Link from "next/link";

export default function GuidesPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-10">
      <div>
        <h1 className="text-3xl font-bold">Guides & FAQ</h1>
        <p className="text-muted-foreground mt-2">
          Everything you need to create, submit, and manage agent skills.
        </p>
      </div>

      {/* Quick links */}
      <div className="grid gap-3 sm:grid-cols-2">
        {[
          {
            href: "/guides/what-is-a-skill",
            title: "What is an agent skill?",
            description: "SOPs, repeatable workflows, domain hints — why skills matter.",
          },
          {
            href: "/guides/slac-github-access",
            title: "SLAC GitHub access",
            description: "Link your GitHub account via SLAC SSO to access internal repos.",
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

      <hr className="border-border" />

      {/* How to create a skill */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold">How to Create a Skill</h2>

        <div className="rounded-lg border p-5 space-y-3">
          <h3 className="font-semibold text-sm uppercase tracking-wide text-muted-foreground">
            Minimal skill repo structure
          </h3>
          <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">
{`my-skill/
  skill.md          # Main skill definition (required)
  README.md         # What it does, how to use it
  CLAUDE.md         # Optional: Claude Code–specific instructions`}
          </pre>
        </div>

        <ol className="space-y-3 text-sm">
          <li className="flex gap-3">
            <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">1</span>
            <span>
              Create a GitHub repository for your skill — it can be public or under the{" "}
              <a href="https://github.com/slaclab" target="_blank" rel="noopener noreferrer" className="text-primary underline">SLACLAB</a>{" "}
              organisation. The repo should contain a{" "}
              <code className="bg-muted rounded px-1 py-0.5 font-mono text-xs">skill.md</code> or{" "}
              <code className="bg-muted rounded px-1 py-0.5 font-mono text-xs">CLAUDE.md</code> file.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">2</span>
            <span>
              Go to <a href="/skills/submit" className="text-primary underline">Submit a Skill</a> and
              paste your GitHub repo URL. The catalog will auto-fill metadata from GitHub.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">3</span>
            <span>
              Optionally add a description, compatible platforms, and version. Click Submit.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">4</span>
            <span>Your skill will appear in the catalog.</span>
          </li>
          <li className="flex gap-3">
            <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">5</span>
            <span>
              Share your skill with colleagues — paste the skill&apos;s catalog URL into Slack,
              a wiki page, or a team README so others can discover and install it.
            </span>
          </li>
        </ol>

        <div className="rounded-lg border border-green-300 bg-green-50 p-4 space-y-1 text-sm">
          <p className="font-semibold text-green-800">Does it work? Verification checklist</p>
          <ul className="list-disc list-inside text-green-700 space-y-1">
            <li>Your repo is accessible on GitHub (public or SLACLAB org)</li>
            <li>The repo has a README.md (appears on skill detail page)</li>
            <li>Skill appears in search results</li>
            <li>Other users can rate and label your skill</li>
          </ul>
        </div>
      </section>

      <hr className="border-border" />

      {/* Troubleshooting */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Troubleshooting</h2>

        <div className="space-y-4">
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
              Who do I contact if something is broken?
            </summary>
            <div className="mt-3 text-sm text-muted-foreground">
              <p>
                Reach out in the <strong>#comp-sdf</strong> Slack channel on the SLAC workspace,
                or open an issue on the project GitHub repository.
              </p>
            </div>
          </details>
        </div>
      </section>
    </div>
  );
}
