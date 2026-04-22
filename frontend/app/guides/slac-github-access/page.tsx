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
        <h1 className="text-3xl font-bold">Accessing SLAC GitHub Repos</h1>
        <p className="text-muted-foreground mt-2">
          Some skills in this catalog are hosted in private or internal repositories under the{" "}
          <code className="bg-muted rounded px-1 py-0.5 font-mono text-xs">slaclab</code> GitHub
          organisation. To install or view those skills you need to link your GitHub account to
          your SLAC identity via Single Sign-On (SSO).
        </p>
      </div>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">What you need</h2>
        <ul className="list-disc list-inside text-sm space-y-1 text-muted-foreground">
          <li>A GitHub account (personal accounts are fine)</li>
          <li>An active SLAC computing account</li>
        </ul>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Steps</h2>
        <ol className="space-y-4 text-sm">
          <li className="flex gap-3">
            <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">1</span>
            <span>
              Sign in to GitHub at{" "}
              <a
                href="https://github.com/login"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline"
              >
                github.com
              </a>{" "}
              with your personal account.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">2</span>
            <span>
              Visit the SLAC Enterprise SSO authorisation page:{" "}
              <a
                href="https://github.com/enterprises/slaclab/sso"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline"
              >
                github.com/enterprises/slaclab/sso
              </a>
            </span>
          </li>
          <li className="flex gap-3">
            <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">3</span>
            <span>
              Click <strong>Continue</strong> and sign in with your SLAC credentials (Windows/AD
              username and password). You may be prompted for Duo MFA.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">4</span>
            <span>
              Once authorised, your GitHub account is linked. You can now clone or browse
              repositories in the{" "}
              <a
                href="https://github.com/slaclab"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline"
              >
                slaclab
              </a>{" "}
              org that your SLAC role grants access to.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">5</span>
            <span>
              Return to this catalog and install the skill — the{" "}
              <strong>SLAC Members Only</strong> badge should no longer block you.
            </span>
          </li>
        </ol>
      </section>

      <div className="rounded-lg border border-yellow-300 bg-yellow-50 p-4 text-sm space-y-1">
        <p className="font-semibold text-yellow-800">SSO session expiry</p>
        <p className="text-yellow-700">
          GitHub SSO sessions expire periodically. If you suddenly lose access to
          internal repos, repeat steps 2–3 above to re-authorise.
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Troubleshooting</h2>
        <div className="space-y-3 text-sm">
          <details className="rounded-lg border p-4 open:pb-4">
            <summary className="font-medium cursor-pointer">
              I completed SSO but still see &ldquo;SLAC Members Only&rdquo;
            </summary>
            <div className="mt-3 text-muted-foreground space-y-2">
              <p>
                The catalog checks repo visibility when a skill is submitted, not on every page
                load. The badge reflects what the backend saw at submission time. If you believe
                you now have access, try cloning the repo directly from GitHub to confirm your
                SSO is active, then contact the skill owner to re-fetch.
              </p>
            </div>
          </details>
          <details className="rounded-lg border p-4 open:pb-4">
            <summary className="font-medium cursor-pointer">
              I don&apos;t have a SLAC computing account
            </summary>
            <div className="mt-3 text-muted-foreground">
              <p>
                Request one via the{" "}
                <a
                  href="https://s3df.slac.stanford.edu/#/accounts?id=accounts"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary underline"
                >
                  SLAC Account request form
                </a>{" "}
                or ask your SLAC host/sponsor to initiate the request.
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
