import Link from "next/link";

export default function WhatIsASkillPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-10">
      <div>
        <p className="text-sm text-muted-foreground mb-2">
          <Link href="/guides" className="hover:underline">Guides</Link>
          {" / "}
          What is an Agent Skill?
        </p>
        <h1 className="text-3xl font-bold">What is an Agent Skill?</h1>
        <p className="text-muted-foreground mt-2">
          A skill is a reusable set of instructions you give to an AI agent — like Claude — so it
          consistently follows a specific workflow, applies domain knowledge, or enforces a process
          every time it is invoked.
        </p>
      </div>

      {/* Core concept */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold">The core idea</h2>
        <p className="text-sm text-muted-foreground">
          When you work with an AI assistant, you often find yourself repeating the same
          context: <em>&ldquo;Always format output as a table,&rdquo;</em>{" "}
          <em>&ldquo;Check safety constraints before running this,&rdquo;</em>{" "}
          <em>&ldquo;Here is how we deploy at SLAC…&rdquo;</em> A skill captures that repeated
          context once, in a plain-text file, and makes it instantly available to any agent that
          loads it.
        </p>
        <p className="text-sm text-muted-foreground">
          Think of a skill the way you think of a Standard Operating Procedure (SOP): it records
          the right way to do something so that anyone — or any AI — can follow it without needing
          to be re-taught every time.
        </p>
      </section>

      <hr className="border-border" />

      {/* What skills are good for */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold">What skills are good for</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {[
            {
              title: "Runbooks & incident response",
              description:
                "Convert an existing runbook into a skill so the agent can walk an on-call engineer through diagnosis and remediation steps without them having to find the right wiki page under pressure.",
            },
            {
              title: "Standard operating procedures",
              description:
                "Capture multi-step processes (e.g. how to submit a beam-time request, how to archive an experiment run) so the agent always follows the same sequence.",
            },
            {
              title: "Repeatable analysis workflows",
              description:
                "Define how to load, clean, and plot data from a specific instrument or data store so every analysis starts from the same baseline.",
            },
            {
              title: "Coding & review standards",
              description:
                "Encode your team's naming conventions, testing rules, or security checklist so the agent applies them automatically when reviewing or writing code.",
            },
            {
              title: "Domain hints & baseline methods",
              description:
                "Embed domain knowledge — preferred physical constants, unit conventions, simulation parameters — that the agent would otherwise have to guess.",
            },
            {
              title: "Onboarding & documentation",
              description:
                "Write a skill that walks new collaborators through the cluster, data systems, or codebase so they get consistent, up-to-date answers.",
            },
            {
              title: "Safety & compliance guardrails",
              description:
                "Add rules the agent must check before taking an action — e.g. never delete raw data, always confirm before writing to a shared path.",
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

      {/* Concrete examples */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Concrete examples</h2>
        <div className="space-y-3 text-sm">
          <div className="rounded-lg border p-4 space-y-2">
            <p className="font-semibold">On-call runbook</p>
            <p className="text-muted-foreground">
              A skill built from an existing runbook that guides the agent — and the on-call
              engineer — through diagnosing a service outage: check the right dashboards, run the
              right queries, escalate in the right order. No more hunting for the correct wiki page
              at 2 am.
            </p>
          </div>
          <div className="rounded-lg border p-4 space-y-2">
            <p className="font-semibold">Kubernetes deployment helper</p>
            <p className="text-muted-foreground">
              A skill that knows the SLAC cluster layout, approved Helm chart patterns, and the
              steps for promoting a workload from dev → staging → prod. Instead of explaining the
              process each session, you load the skill and ask <em>&ldquo;deploy my app&rdquo;</em>.
            </p>
          </div>
          <div className="rounded-lg border p-4 space-y-2">
            <p className="font-semibold">Experiment log reviewer</p>
            <p className="text-muted-foreground">
              A skill that reads a standard LCLS log format, flags anomalous readings, and
              generates a summary in the group&apos;s preferred template — same output every run,
              no prompt engineering required.
            </p>
          </div>
          <div className="rounded-lg border p-4 space-y-2">
            <p className="font-semibold">Code review checklist</p>
            <p className="text-muted-foreground">
              A skill that instructs the agent to check for security issues, test coverage, and
              style violations according to your team&apos;s written standards — acting like a
              senior reviewer who never forgets a step.
            </p>
          </div>
        </div>
      </section>

      <hr className="border-border" />

      {/* Why share them */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Why share skills in a catalog?</h2>
        <ul className="space-y-3 text-sm">
          {[
            {
              heading: "Avoid reinventing the wheel",
              body: "If someone on another team already wrote a skill for a tool you both use, you get working, tested instructions for free.",
            },
            {
              heading: "Encode institutional knowledge",
              body: "Tacit knowledge that lives in one person's head — or in a wiki page nobody reads — becomes an executable, searchable skill.",
            },
            {
              heading: "Raise the floor for everyone",
              body: "A shared baseline skill means every agent at SLAC using that workflow starts from the same vetted approach, not a blank slate.",
            },
            {
              heading: "Iterate in one place",
              body: "When the process changes, update the skill once. Every agent that loads it picks up the change automatically.",
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

      {/* How to use */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold">How to use a skill</h2>
        <ol className="space-y-4 text-sm">
          <li className="flex gap-3">
            <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">1</span>
            <span>
              Find a skill in the{" "}
              <Link href="/skills" className="text-primary underline">catalog</Link>{" "}
              that matches your task.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">2</span>
            <span>
              Click <strong>Install</strong> on the skill page — this gives you the one-line
              command to add it to your Claude Code setup.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">3</span>
            <span>
              Invoke the skill in your agent session using{" "}
              <code className="bg-muted rounded px-1 py-0.5 font-mono text-xs">/<em>skill-name</em></code>{" "}
              — the agent loads the instructions and follows them for that task.
            </span>
          </li>
        </ol>
      </section>

      {/* CTA */}
      <div className="rounded-lg border border-primary/30 bg-primary/5 p-5 flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex-1 space-y-1">
          <p className="font-semibold text-sm">Ready to share your own process?</p>
          <p className="text-sm text-muted-foreground">
            If you have a workflow that works well, turning it into a skill takes minutes —
            it&apos;s just a Markdown file in a GitHub repo.
          </p>
        </div>
        <div className="flex gap-3 flex-shrink-0">
          <Link
            href="/guides"
            className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
          >
            How to create a skill
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
