import Link from "next/link";

const APP_URL = "https://agent-knowledge-hub.slac.stanford.edu";
const PLUGIN_SLUG = "agent-knowledge-hub";

export default function AgentKnowledgeHubGuidePage() {
  return (
    <div className="max-w-3xl mx-auto space-y-10">
      <div>
        <p className="text-sm text-muted-foreground mb-2">
          <Link href="/guides" className="hover:underline">Guides</Link>
          {" / "}
          Using the /{PLUGIN_SLUG} skill
        </p>
        <h1 className="text-3xl font-bold">The <code className="font-mono">/{PLUGIN_SLUG}</code> Skill</h1>
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
/plugin marketplace add ${APP_URL}/marketplace.json

# 2. Install the discovery skill
/plugin install ${PLUGIN_SLUG}

# 3. Activate the skill
/reload-plugins`}
          </pre>
        </div>
        <p className="text-sm text-muted-foreground">
          After installation, the <code className="bg-muted rounded px-1 font-mono text-xs">/{PLUGIN_SLUG}</code> slash
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
{`/${PLUGIN_SLUG} I need something to query EPICS
/${PLUGIN_SLUG} find me a skill for analysing NeXus files
/${PLUGIN_SLUG} search --label hdf5`}
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
{`/${PLUGIN_SLUG} install k8s-troubleshooting`}
          </pre>
          <p className="text-sm text-muted-foreground">
            Downloads the skill files from GitHub into{" "}
            <code className="bg-muted rounded px-1 font-mono text-xs">~/.claude/skills/&lt;slug&gt;/</code>.
            The skill runs a path traversal check on every file before writing — a skill with a
            malicious <code className="bg-muted rounded px-1 font-mono text-xs">skill_path</code> will
            be rejected and no files will be written.
          </p>
          <p className="text-sm text-muted-foreground">
            The install does not add a skill&apos;s MCP servers. It shows each server&apos;s
            configuration and the command that adds it, and leaves adding it to you. Until you add
            them, the skill works only in part. Add a server by running its printed command in a
            terminal or after typing <code className="bg-muted rounded px-1 font-mono text-xs">!</code> in Claude Code, or ask Claude to add it by name.
          </p>
          <p className="text-sm text-muted-foreground">
            An agent is not installed when it declares a setting outside{" "}
            <code className="bg-muted rounded px-1 font-mono text-xs">name</code>, <code className="bg-muted rounded px-1 font-mono text-xs">description</code>,{" "}
            <code className="bg-muted rounded px-1 font-mono text-xs">tools</code>, <code className="bg-muted rounded px-1 font-mono text-xs">disallowedTools</code>,{" "}
            <code className="bg-muted rounded px-1 font-mono text-xs">model</code> and <code className="bg-muted rounded px-1 font-mono text-xs">color</code>, or when its name is
            that of a built-in agent or of another agent in{" "}
            <code className="bg-muted rounded px-1 font-mono text-xs">~/.claude/agents/</code>. The closing message links it instead. An agent,
            command or skill folder you already have is left unchanged.
          </p>
        </div>

        {/* Install a skillset */}
        <div className="space-y-2">
          <h3 className="font-semibold text-sm">Install a skillset</h3>
          <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">
{`/${PLUGIN_SLUG} install skillset lcls-starter`}
          </pre>
          <p className="text-sm text-muted-foreground">
            Installs every skill in a curated skillset, in the order its curator chose. Before it
            installs anything, it lists the skills it will install, with each one&apos;s repository and
            whether it brings an MCP server or scripts, and asks once. A skill already installed is
            skipped, and a skill that fails is reported while the others still install, so running the
            command again retries only the failures. Like every catalog command, it needs your S3DF
            sign-in (see <a href="#cli-auth" className="text-primary underline">CLI authentication</a>).
          </p>
        </div>

        {/* List / update / remove */}
        <div className="space-y-2">
          <h3 className="font-semibold text-sm">Manage installed skills</h3>
          <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">
{`/${PLUGIN_SLUG} list                  # show installed skills
/${PLUGIN_SLUG} update k8s-troubleshooting   # pull latest version
/${PLUGIN_SLUG} remove k8s-troubleshooting   # uninstall`}
          </pre>
          <p className="text-sm text-muted-foreground">
            <code className="bg-muted rounded px-1 font-mono text-xs">remove</code> leaves any MCP server you added and prints the command
            that removes it. <code className="bg-muted rounded px-1 font-mono text-xs">install</code> of a skill that is already installed
            writes nothing and says to run <code className="bg-muted rounded px-1 font-mono text-xs">update</code>, which is the command
            that replaces an installed skill.
          </p>
        </div>

        {/* Rate */}
        <div className="space-y-2">
          <h3 className="font-semibold text-sm">Rate a skill</h3>
          <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">
{`/${PLUGIN_SLUG} rate k8s-troubleshooting 5`}
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
{`/${PLUGIN_SLUG} create`}
          </pre>
          <p className="text-sm text-muted-foreground">
            Walks you through a name and description, then writes a{" "}
            <code className="bg-muted rounded px-1 font-mono text-xs">SKILL.md</code> template to
            a directory you choose. Once your skill is in a GitHub repo, use{" "}
            <code className="bg-muted rounded px-1 font-mono text-xs">/{PLUGIN_SLUG} submit</code> to
            add it to the catalog.
          </p>
        </div>

        {/* Submit */}
        <div className="space-y-2">
          <h3 className="font-semibold text-sm">Submit to the catalog</h3>
          <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">
{`/${PLUGIN_SLUG} submit`}
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
          Every command that contacts the catalog (search, install, update, rate, validate, and 
          <code className="bg-muted rounded px-1 font-mono text-xs">submit &lt;path&gt;</code>) sends your S3DF sign-in. Catalog commands are
          supported in Cogito and on S3DF nodes only.
        </p>
        <div className="rounded-lg border p-5 space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Where the client finds your sign-in
          </p>
          <p className="text-xs text-muted-foreground">
            The client reads a SLAC-issued JWT from 
            <code className="bg-muted rounded px-1 font-mono text-xs">.s3df-access-token</code> in your account&apos;s home directory, the one 
            <code className="bg-muted rounded px-1 font-mono text-xs">getent passwd</code> reports, or from 
            <code className="bg-muted rounded px-1 font-mono text-xs">~/.s3df-access-token</code> when that file is absent. In a Cogito session it
            finds the token there with no setup. On an S3DF node outside Cogito, write it once with:
          </p>
          <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">
{`s3df login`}
          </pre>
          <p className="text-xs text-muted-foreground">
            The skill reads this file automatically — you never need to paste a token manually. The
            token goes only to the catalog, through <code className="bg-muted rounded px-1 font-mono text-xs">hub-request.sh</code>, a script that
            ships with the client.
          </p>
        </div>
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800 space-y-2">
          <p className="font-semibold">Token expiry</p>
          <p>
            If any catalog command says 
            <em>&ldquo;The catalog did not accept your S3DF sign-in. It has most likely expired.&rdquo;</em>,
            the client shows these steps:
          </p>
          <pre className="bg-amber-100 rounded-md p-3 text-xs overflow-x-auto">
{`To sign in again:
  - In Cogito: open Cogito in a new private browser window and sign in.
  - On an S3DF node outside Cogito: run  s3df login
    (if the shell cannot find s3df: /sdf/sw/s3df-cli/bin/s3df login)
  - On a computer outside S3DF: use this client from Cogito or from an S3DF node.
Then ask again here; this session does not need to restart.
If the same message comes back right after you sign in, the problem is probably
on the catalog's side: report it at https://agent-knowledge-hub.slac.stanford.edu`}
          </pre>
        </div>
        <div className="rounded-lg border p-5 space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Permission prompts
          </p>
          <p className="text-xs text-muted-foreground">
            A session that asks before each Bash command asks before each catalog request. The first
            time the client contacts the catalog in a conversation, it tells you, with 
            <code className="bg-muted rounded px-1 font-mono text-xs">&lt;script&gt;</code> replaced by the script&apos;s full path:
          </p>
          <pre className="bg-muted rounded-md p-3 text-xs whitespace-pre-wrap">
{`Catalog requests run through <script>, a script in this skill that reads your S3DF token and sends it only to https://agent-knowledge-hub.slac.stanford.edu. If Claude Code asks before running it, you can stop the questions: choose "don't ask again" only if the rule it offers starts with sh <script>, or add the rule Bash(sh <script> *) with /permissions. A rule for all of sh would let any shell command run without asking. After a client update the script's path can change, and Claude Code then asks again until you add the rule for the new path.`}
          </pre>
          <p className="text-xs text-muted-foreground">
            To stop the prompts, accept the rule <code className="bg-muted rounded px-1 font-mono text-xs">Bash(sh &lt;script&gt; *)</code>. A rule
            accepted in the dialog applies in the current repository only. A rule added with 
            <code className="bg-muted rounded px-1 font-mono text-xs">/permissions</code> to your user settings applies in every project. For a
            plugin install, the script&apos;s path holds the plugin&apos;s version, so the prompts
            return after each client update until you add the rule for the new path.
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
            Use <code className="bg-primary/10 rounded px-1 font-mono text-xs">/{PLUGIN_SLUG} create</code> to
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
