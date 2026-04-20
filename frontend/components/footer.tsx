export function Footer() {
  return (
    <footer className="border-t bg-background mt-auto">
      <div className="container flex h-12 items-center justify-between text-xs text-muted-foreground">
        <span>Agent Knowledge Hub — S3DF / SLAC</span>
        <div className="flex items-center gap-4">
          <a
            href="/guides"
            className="hover:text-foreground transition-colors"
          >
            Guides & FAQ
          </a>
          <a
            href="https://s3df.slac.stanford.edu"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-foreground transition-colors"
          >
            S3DF
          </a>
        </div>
      </div>
    </footer>
  );
}
