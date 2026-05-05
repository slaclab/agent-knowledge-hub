import Link from "next/link";

export default function SlacGithubAccessPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-10">
      <div>
        <p className="text-sm text-muted-foreground mb-2">
          <Link href="/guides" className="hover:underline">Guides</Link>
          {" / "}
          SLAC GitHub Access
        </p>
        <h1 className="text-3xl font-bold">Accessing SLAC Internal Skills</h1>
        <p className="text-muted-foreground mt-2">
          Skills badged <strong>SLAC Members Only</strong> are hosted in internal repositories
          under the{" "}
          <code className="bg-muted rounded px-1 py-0.5 font-mono text-xs">slaclab</code> GitHub
          organisation. Installing them via the <code className="bg-muted rounded px-1 py-0.5 font-mono text-xs">claude</code> CLI
          requires your local GitHub credentials to have access to that org.
        </p>
      </div>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">What you need</h2>
        <ul className="list-disc list-inside text-sm space-y-1 text-muted-foreground">
          <li>A SLAC computing account</li>
          <li>Membership in the <code className="bg-muted rounded px-1 py-0.5 font-mono text-xs">slaclab</code> GitHub org (request from your team lead or IT)</li>
          <li>A GitHub Personal Access Token (classic) or SSH key authorized for SAML SSO</li>
        </ul>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Authorize your PAT for SLAC SSO</h2>
        <p className="text-sm text-muted-foreground">
          Even if you are a <code className="bg-muted rounded px-1 py-0.5 font-mono text-xs">slaclab</code> org member,
          your PAT must be explicitly authorized for SAML SSO before it can access internal repos.
        </p>
        <ol className="space-y-4 text-sm">
          <li className="flex gap-3">
            <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">1</span>
            <span>
              Go to{" "}
              <a
                href="https://github.com/settings/tokens"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline"
              >
                github.com/settings/tokens
              </a>{" "}
              and create or open an existing <strong>classic</strong> PAT with at least{" "}
              <code className="bg-muted rounded px-1 py-0.5 font-mono text-xs">repo</code> scope.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">2</span>
            <span>
              Next to the token, click <strong>Configure SSO</strong> → <strong>Authorize</strong>{" "}
              next to <code className="bg-muted rounded px-1 py-0.5 font-mono text-xs">slaclab</code>.
              Sign in with your SLAC credentials (Windows/AD) if prompted.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">3</span>
            <span>
              Set the token in your local git config so the CLI can use it:
              <pre className="mt-2 rounded bg-muted px-3 py-2 text-xs font-mono overflow-x-auto">
                {`git config --global credential.helper store\ngit credential approve <<EOF\nprotocol=https\nhost=github.com\nusername=<your-github-username>\npassword=<your-pat>\nEOF`}
              </pre>
              Or use the <code className="bg-muted rounded px-1 py-0.5 font-mono text-xs">gh</code> CLI:{" "}
              <code className="bg-muted rounded px-1 py-0.5 font-mono text-xs">gh auth login</code> and paste your PAT when prompted.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">4</span>
            <span>
              You can now install internal skills via the catalog — e.g.{" "}
              <code className="bg-muted rounded px-1 py-0.5 font-mono text-xs">/agent-knowledge-hub install &lt;slug&gt;</code>.
            </span>
          </li>
        </ol>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Using SSH instead of a PAT</h2>
        <p className="text-sm text-muted-foreground">
          If you prefer SSH, your key must also be authorized for SAML SSO:
        </p>
        <ol className="space-y-2 text-sm list-decimal list-inside text-muted-foreground">
          <li>
            Go to{" "}
            <a
              href="https://github.com/settings/keys"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline"
            >
              github.com/settings/keys
            </a>{" "}
            and open your SSH key.
          </li>
          <li>
            Click <strong>Configure SSO</strong> → <strong>Authorize</strong> next to{" "}
            <code className="bg-muted rounded px-1 py-0.5 font-mono text-xs">slaclab</code>.
          </li>
        </ol>
      </section>

      <div className="rounded-lg border border-yellow-300 bg-yellow-50 p-4 text-sm space-y-1">
        <p className="font-semibold text-yellow-800">SSO session expiry</p>
        <p className="text-yellow-700">
          SAML SSO authorization expires periodically. If you lose access to internal repos,
          revisit your token or SSH key settings and re-authorize for <code>slaclab</code>.
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Troubleshooting</h2>
        <div className="space-y-3 text-sm">
          <details className="rounded-lg border p-4 open:pb-4">
            <summary className="font-medium cursor-pointer">
              git clone fails with 403 or &ldquo;repository not found&rdquo;
            </summary>
            <div className="mt-3 text-muted-foreground space-y-2">
              <p>
                Most likely your PAT is not authorized for SAML SSO. Go to{" "}
                <a href="https://github.com/settings/tokens" className="text-primary underline" target="_blank" rel="noopener noreferrer">
                  github.com/settings/tokens
                </a>{" "}
                → <strong>Configure SSO</strong> → <strong>Authorize</strong> for{" "}
                <code className="bg-muted rounded px-1 py-0.5 font-mono text-xs">slaclab</code>.
              </p>
            </div>
          </details>
          <details className="rounded-lg border p-4 open:pb-4">
            <summary className="font-medium cursor-pointer">
              I&apos;m not a member of the slaclab org
            </summary>
            <div className="mt-3 text-muted-foreground">
              <p>
                Ask your team lead or a <code className="bg-muted rounded px-1 py-0.5 font-mono text-xs">slaclab</code> org owner to invite your GitHub account.
                You also need an active SLAC computing account — request one via the{" "}
                <a
                  href="https://s3df.slac.stanford.edu/#/accounts?id=accounts"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary underline"
                >
                  SLAC Account request form
                </a>.
              </p>
            </div>
          </details>
          <details className="rounded-lg border p-4 open:pb-4">
            <summary className="font-medium cursor-pointer">
              Still stuck?
            </summary>
            <div className="mt-3 text-muted-foreground">
              <p>
                Reach out in <strong>#comp-sdf</strong> on the SLAC Slack workspace, or open an
                issue on the project repository.
              </p>
            </div>
          </details>
        </div>
      </section>
    </div>
  );
}
