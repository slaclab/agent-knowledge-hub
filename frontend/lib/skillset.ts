/** The slug the create form suggests for a skillset name. It follows python-slugify, which the
 * backend uses when no slug is sent, for Latin text. A name with no Latin letters or digits gives
 * "", and the form then sends no slug, so the backend's transliteration picks one. */
export function deriveSlug(name: string): string {
  return name
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+/, "")
    .slice(0, 100)
    .replace(/-+$/, "");
}

/** The FR-2g message for a membership change, or FR-2f's for a reorder, that returned `status`;
 * null when the change stands. A 409 on add or a 404 on remove means another page already made
 * the change. A reorder's 409 or 422 means the page is stale. Status 0 stands for a request that
 * never got a response. */
export function membershipMessage(op: "add" | "remove" | "order", status: number): string | null {
  if ((status >= 200 && status < 300) || (op === "add" && status === 409) || (op === "remove" && status === 404)) {
    return null;
  }
  if (op === "order" && (status === 409 || status === 422)) {
    return "This skillset changed since you loaded it, so your move was not saved. The list below is up to date; try the move again.";
  }
  switch (status) {
    case 401:
      return "Your session has expired. Reload the page to sign in again.";
    case 403:
      return "You are not allowed to change this skillset. Reload the page.";
    case 404:
      return "This skill was deactivated or deleted, or the skillset was deleted. Reload the page.";
    case 429:
      return "Too many additions in the last hour. Try again later.";
    default:
      return "Could not save the change. Try again.";
  }
}

/** The member order after moving the member at `index` one place up (-1) or down (1), or null
 * when the move would leave the list. */
export function moveMember(slugs: string[], index: number, delta: -1 | 1): string[] | null {
  const target = index + delta;
  if (target < 0 || target >= slugs.length) return null;
  const next = [...slugs];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}
