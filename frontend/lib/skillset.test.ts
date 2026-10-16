import { describe, expect, it } from "vitest";
import { deriveSlug, membershipMessage, moveMember } from "./skillset";

describe("deriveSlug", () => {
  it("lowercases the name and joins its words with hyphens", () => {
    expect(deriveSlug("LCLS Starter Kit")).toBe("lcls-starter-kit");
  });

  it("drops accents and turns punctuation into hyphens, as the backend's python-slugify does", () => {
    expect(deriveSlug("Café's  tools: v2!")).toBe("cafe-s-tools-v2");
  });

  it("never starts or ends with a hyphen", () => {
    expect(deriveSlug("  --Data / Analysis--  ")).toBe("data-analysis");
  });

  it("stays within the backend's 100-character limit without a trailing hyphen", () => {
    const slug = deriveSlug(`${"a".repeat(99)} b`);
    expect(slug).toBe("a".repeat(99));
    expect(deriveSlug("x".repeat(150))).toHaveLength(100);
  });

  it("returns an empty string for a name with no Latin letters or digits, which the backend derives instead", () => {
    expect(deriveSlug("日本語")).toBe("");
  });
});

describe("membershipMessage", () => {
  it("returns null for a change that was saved", () => {
    expect(membershipMessage("add", 204)).toBeNull();
    expect(membershipMessage("remove", 204)).toBeNull();
  });

  it("treats an add that is already a member, or a remove that is already gone, as saved", () => {
    expect(membershipMessage("add", 409)).toBeNull();
    expect(membershipMessage("remove", 404)).toBeNull();
  });

  it("explains each failure in the words FR-2g sets", () => {
    expect(membershipMessage("add", 401)).toBe("Your session has expired. Reload the page to sign in again.");
    expect(membershipMessage("remove", 403)).toBe("You are not allowed to change this skillset. Reload the page.");
    expect(membershipMessage("add", 404)).toBe(
      "This skill was deactivated or deleted, or the skillset was deleted. Reload the page.",
    );
    expect(membershipMessage("add", 429)).toBe("Too many additions in the last hour. Try again later.");
  });

  it("falls back to a generic message for any other failure, including a network error", () => {
    expect(membershipMessage("add", 500)).toBe("Could not save the change. Try again.");
    expect(membershipMessage("remove", 409)).toBe("Could not save the change. Try again.");
    expect(membershipMessage("add", 0)).toBe("Could not save the change. Try again.");
  });
});

describe("membershipMessage for a reorder", () => {
  const stale =
    "This skillset changed since you loaded it, so your move was not saved. The list below is up to date; try the move again.";

  it("returns null for a saved order", () => {
    expect(membershipMessage("order", 200)).toBeNull();
  });

  it("explains a stale version or a changed member set with FR-2f's message", () => {
    expect(membershipMessage("order", 409)).toBe(stale);
    expect(membershipMessage("order", 422)).toBe(stale);
  });

  it("does not treat a 404 as already done, as a remove does", () => {
    expect(membershipMessage("order", 404)).toBe(
      "This skill was deactivated or deleted, or the skillset was deleted. Reload the page.",
    );
    expect(membershipMessage("order", 403)).toBe("You are not allowed to change this skillset. Reload the page.");
  });
});

describe("moveMember", () => {
  const slugs = ["a", "b", "c"];

  it("swaps a member with its neighbour", () => {
    expect(moveMember(slugs, 1, -1)).toEqual(["b", "a", "c"]);
    expect(moveMember(slugs, 1, 1)).toEqual(["a", "c", "b"]);
  });

  it("leaves the input list unchanged", () => {
    moveMember(slugs, 0, 1);
    expect(slugs).toEqual(["a", "b", "c"]);
  });

  it("returns null for a move past either end", () => {
    expect(moveMember(slugs, 0, -1)).toBeNull();
    expect(moveMember(slugs, 2, 1)).toBeNull();
  });
});
