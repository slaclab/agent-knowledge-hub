import Link from "next/link";

export default function CreateASkillPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-10">
      <div>
        <p className="text-sm text-muted-foreground mb-2">
          <Link href="/guides" className="hover:underline">Guides</Link>
          {" / "}
          How to Create a Skill
        </p>
        <h1 className="text-3xl font-bold">How to Create a Skill</h1>
        <p className="text-muted-foreground mt-2">
          A skill is a Markdown file in a GitHub repo. Creating and publishing one takes minutes.
        </p>
      </div>

      <section className="space-y-4">
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
              Go to <Link href="/skills/submit" className="text-primary underline">Submit a Skill</Link> and
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
            <span>Your skill will appear in the catalog immediately.</span>
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

        <div className="rounded-lg border p-5 space-y-3 text-sm">
          <h3 className="font-semibold text-sm uppercase tracking-wide text-muted-foreground">
            Agents and MCP servers
          </h3>
          <p className="text-muted-foreground">
            <code className="bg-muted rounded px-1 font-mono text-xs">/agent-knowledge-hub install</code>{" "}
            writes your skill&apos;s agents only within these rules, and never adds its MCP servers:
            it shows each server&apos;s configuration and the command that adds it, and the user
            decides.
          </p>
          <ul className="list-disc list-inside text-muted-foreground space-y-1">
            <li>
              <code className="bg-muted rounded px-1 font-mono text-xs">agents</code> in{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">plugin.json</code> lists paths to
              agent files, or to folders whose <code className="bg-muted rounded px-1 font-mono text-xs">.md</code>{" "}
              files are the agents.
            </li>
            <li>
              An agent&apos;s frontmatter declares only{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">name</code>,{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">description</code>,{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">tools</code>,{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">disallowedTools</code>,{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">model</code> and{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">color</code>. An agent with any
              other key, such as <code className="bg-muted rounded px-1 font-mono text-xs">hooks</code>, is
              not installed.
            </li>
            <li>
              An agent&apos;s <code className="bg-muted rounded px-1 font-mono text-xs">name</code> sits on
              the <code className="bg-muted rounded px-1 font-mono text-xs">name:</code> line itself and holds
              only ASCII letters, digits, <code className="bg-muted rounded px-1 font-mono text-xs">-</code> and{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">_</code>. Ignoring case, it is none of
              the built-in agent names <code className="bg-muted rounded px-1 font-mono text-xs">Explore</code>,{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">Plan</code>,{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">general-purpose</code>,{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">claude</code>,{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">statusline-setup</code>,{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">claude-code-guide</code> and{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">fork</code>.
            </li>
            <li>
              An <code className="bg-muted rounded px-1 font-mono text-xs">mcp-servers</code> entry gets a
              command only when its <code className="bg-muted rounded px-1 font-mono text-xs">name</code>{" "}
              matches <code className="bg-muted rounded px-1 font-mono text-xs">^[A-Za-z0-9][A-Za-z0-9_-]*$</code>{" "}
              and no other entry of the skill uses it, its{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">transport</code> is{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">stdio</code>,{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">http</code> or{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">sse</code>, its{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">args</code>,{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">env</code> and{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">headers</code> values are text, and its
              configuration is at most 4,096 bytes as JSON.
            </li>
            <li>
              Name a script in the installed folder as{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">${"{HOME}"}/.claude/skills/&lt;slug&gt;/…</code>,
              never <code className="bg-muted rounded px-1 font-mono text-xs">~/…</code> or{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">$HOME/…</code>.
            </li>
            <li>
              The install leaves out every symbolic link, whether a listed agent or command file or an
              entry in the skill folder, and never copies the skill folder&apos;s{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">.claude-plugin/</code>,{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">.installed-manifest.json</code> or{" "}
              <code className="bg-muted rounded px-1 font-mono text-xs">.akh-mcp/</code>.
            </li>
          </ul>
        </div>
      </section>

      <hr className="border-border" />

      <div className="rounded-lg border border-primary/30 bg-primary/5 p-5 flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex-1 space-y-1">
          <p className="font-semibold text-sm">Want to scaffold a skill from within your agent session?</p>
          <p className="text-sm text-muted-foreground">
            Use <code className="bg-primary/10 rounded px-1 font-mono text-xs">/agent-knowledge-hub create</code> to
            generate a <code className="bg-primary/10 rounded px-1 font-mono text-xs">SKILL.md</code> template without
            leaving Claude Code.
          </p>
        </div>
        <div className="flex gap-3 flex-shrink-0">
          <Link
            href="/guides/agent-knowledge-hub"
            className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
          >
            /agent-knowledge-hub guide
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
