import Link from "next/link";

export default function WhyAgentKnowledgeHubPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-10">
      <div>
        <p className="text-sm text-muted-foreground mb-2">
          <Link href="/guides" className="hover:underline">Guides</Link>
          {" / "}
          Why use Agent Knowledge Hub?
        </p>
        <h1 className="text-3xl font-bold">Why use Agent Knowledge Hub?</h1>
        <p className="text-muted-foreground mt-2">
          A shared catalog for AI skills at SLAC — so the work of building great agent
          workflows compounds across the lab instead of staying in one person&apos;s dotfiles.
        </p>
      </div>

      {/* The problem */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold">The problem it solves</h2>
        <p className="text-sm text-muted-foreground">
          Claude Code skills are just Markdown files in GitHub repos. Without a shared
          registry, finding useful ones means knowing the right people, searching Slack, or
          re-building what a colleague already spent hours on. The same skill gets written
          three times across three groups, each version diverges, and none is documented
          well enough for anyone else to trust.
        </p>
        <p className="text-sm text-muted-foreground">
          Agent Knowledge Hub gives teams a single place to publish, discover, and evaluate
          AI productivity tools — with enough metadata to make an informed decision before
          installing anything.
        </p>
      </section>

      <hr className="border-border" />

      {/* Benefits grid */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Key benefits</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {[
            {
              title: "Centralised catalog",
              description:
                "One URL for every published skill at SLAC. Full-text search across name, description, README, and labels. No more Slack messages or asking around to find what already exists.",
            },
            {
              title: "Organisation through labels",
              description:
                "Skills are tagged with labels like mcp, multi-agent, slurm, and python — applied automatically from plugin.json and manually by the community. Filter by multiple labels at once to narrow results precisely.",
            },
            {
              title: "Provenance and trust",
              description:
                "Every skill shows who submitted it, when, from which GitHub repo and path. A full revision history records every edit and rescan with the actor. You can audit the source before installing anything.",
            },
            {
              title: "Quality signals",
              description:
                "Community star ratings, rating counts, GitHub stars, and last commit date surface at a glance. Ratings are per-user and authenticated — real humans at SLAC tried the skill, not bots.",
            },
            {
              title: "SLAC-internal skills",
              description:
                "Skills wrapping internal APIs or systems can be published with internal visibility. Metadata is public, but README and instruction content is shown only to authenticated SLAC users.",
            },
            {
              title: "Automatic metadata",
              description:
                "Submitting requires only a GitHub URL. The catalog fetches SKILL.md, README.md, and plugin.json automatically — extracting version, author, agent count, MCP server presence, and keywords without any manual entry.",
            },
            {
              title: "Fork lineage",
              description:
                "When a team customises an upstream skill for local infrastructure, the fork relationship is recorded. Both the original and the variant are discoverable, and their lineage is clear.",
            },
            {
              title: "In-agent installation",
              description:
                "Install skills directly from a Claude Code session with /agent-knowledge-hub install <slug>. Files land in the right place, MCP servers are registered — no git clone, no copying files by hand.",
            },
          ].map(({ title, description }) => (
            <div key={title} className="rounded-lg border p-4 space-y-1">
              <p className="font-semibold text-sm">{title}</p>
              <p className="text-sm text-muted-foreground">{description}</p>
            </div>
          ))}
        </div>
      </section>

      <hr className="border-border" />

      {/* Quality signals detail */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Evaluating a skill before you install it</h2>
        <p className="text-sm text-muted-foreground">
          The detail page for each skill surfaces everything you need to make an informed
          decision:
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b text-left">
                <th className="pb-2 pr-6 font-semibold">Signal</th>
                <th className="pb-2 font-semibold text-muted-foreground">What it tells you</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {[
                ["Average rating (1–5★)", "Community experience with the skill in practice"],
                ["Rating count", "How widely the skill has been tried at SLAC"],
                ["GitHub stars", "Broader upstream adoption beyond the catalog"],
                ["Last commit", "Whether the skill is actively maintained"],
                ["Revision history", "Who changed what, and when — full audit trail"],
                ["License", "Surfaced automatically from the repo; compliance at a glance"],
                ["Agent count", "How many sub-agents the skill orchestrates"],
                ["MCP server", "Whether the skill exposes tool endpoints to Claude"],
              ].map(([signal, detail]) => (
                <tr key={signal}>
                  <td className="py-2 pr-6 font-mono text-xs">{signal}</td>
                  <td className="py-2 text-muted-foreground">{detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <hr className="border-border" />

      {/* Reduced duplication */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Compounding effort across the lab</h2>
        <ul className="space-y-3 text-sm">
          {[
            {
              heading: "Avoid reinventing the wheel",
              body: "If another team already wrote a skill for a tool you both use, you get working, tested instructions for free.",
            },
            {
              heading: "Encode institutional knowledge",
              body: "Tacit knowledge that lives in one person's head — or in a wiki page nobody reads — becomes an executable, searchable skill.",
            },
            {
              heading: "Update once, benefit everyone",
              body: "When a process changes, update the skill in one place. Every agent that loads it picks up the change automatically.",
            },
            {
              heading: "Raise the floor for new starters",
              body: "A new team member loads the same vetted skills as a ten-year veteran. Consistent, up-to-date answers from day one.",
            },
          ].map(({ heading, body }) => (
            <li key={heading} className="flex gap-3">
              <span className="mt-0.5 flex-shrink-0 h-2 w-2 rounded-full bg-primary" />
              <span>
                <strong>{heading}.</strong>{" "}{body}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <hr className="border-border" />

      {/* Who should publish */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Who should publish here?</h2>
        <div className="space-y-3 text-sm text-muted-foreground">
          <p>
            <strong className="text-foreground">Platform teams</strong> building reusable
            infrastructure skills — HPC job submission, storage management, experiment
            control — that multiple groups across SLAC will rely on.
          </p>
          <p>
            <strong className="text-foreground">Research groups</strong> that have invested
            in a well-tested agent workflow and want others to benefit from it without
            having to reproduce the effort.
          </p>
          <p>
            <strong className="text-foreground">Anyone</strong> who has built something that
            took non-trivial effort to get right. Publishing is low-friction: paste a GitHub
            URL, confirm the metadata, submit. The catalog handles the rest.
          </p>
        </div>
      </section>

      {/* CTA */}
      <div className="rounded-lg border border-primary/30 bg-primary/5 p-5 flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex-1 space-y-1">
          <p className="font-semibold text-sm">Ready to explore the catalog?</p>
          <p className="text-sm text-muted-foreground">
            Browse published skills, or submit your own — it takes minutes.
          </p>
        </div>
        <div className="flex gap-3 flex-shrink-0">
          <Link
            href="/skills"
            className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
          >
            Browse Skills
          </Link>
          <Link
            href="/skills/submit"
            className="rounded-md bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            Submit a Skill
          </Link>
        </div>
      </div>
    </div>
  );
}
