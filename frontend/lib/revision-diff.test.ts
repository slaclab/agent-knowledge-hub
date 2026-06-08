import { describe, it, expect } from "vitest";
import { computeDiff, computeGenesis } from "./revision-diff";

describe("computeDiff", () => {
  it("F1 — returns empty array when snapshots are identical", () => {
    const snap = { name: "MySkill", description: "Same", compatible_platforms: ["claude"] };
    expect(computeDiff(snap, snap)).toEqual([]);
  });

  it("F2 — detects scalar change", () => {
    const prev = { name: "OldName" };
    const next = { name: "NewName" };
    const diffs = computeDiff(prev, next);
    expect(diffs).toHaveLength(1);
    expect(diffs[0]).toMatchObject({ field: "name", type: "scalar", old: "OldName", new: "NewName" });
  });

  it("F3 — detects array items added", () => {
    const prev = { compatible_platforms: ["claude"] };
    const next = { compatible_platforms: ["claude", "cursor"] };
    const diffs = computeDiff(prev, next);
    expect(diffs).toHaveLength(1);
    expect(diffs[0]).toMatchObject({ field: "compatible_platforms", type: "array", added: ["cursor"], removed: [] });
  });

  it("F4 — detects array items removed", () => {
    const prev = { labels: ["python", "mcp"] };
    const next = { labels: ["python"] };
    const diffs = computeDiff(prev, next);
    expect(diffs[0]).toMatchObject({ field: "labels", type: "array", added: [], removed: ["mcp"] });
  });

  it("F5 — array reorder produces no diff", () => {
    const prev = { compatible_platforms: ["cursor", "claude"] };
    const next = { compatible_platforms: ["claude", "cursor"] };
    expect(computeDiff(prev, next)).toEqual([]);
  });

  it("F6 — null → value transition for scalar", () => {
    const prev = { description: null };
    const next = { description: "new desc" };
    const diffs = computeDiff(prev, next);
    expect(diffs[0]).toMatchObject({ field: "description", type: "scalar", old: null, new: "new desc" });
  });

  it("F7 — value → null transition for scalar", () => {
    const prev = { version: "1.0.0" };
    const next = { version: null };
    const diffs = computeDiff(prev, next);
    expect(diffs[0]).toMatchObject({ field: "version", type: "scalar", old: "1.0.0", new: null });
  });

  it("F8 — null vs [] for array produces no diff", () => {
    const prev = { compatible_platforms: null };
    const next = { compatible_platforms: [] };
    expect(computeDiff(prev, next)).toEqual([]);
  });

  it("F9 — legacy snapshot with no labels key: labels row omitted", () => {
    const prev = { name: "A" }; // no labels key
    const next = { name: "A" }; // no labels key
    const diffs = computeDiff(prev, next);
    expect(diffs.some((d) => d.field === "labels")).toBe(false);
  });

  it("F10 — excluded fields never appear in output", () => {
    const prev = { name: "X", readme_html: "<h1>old</h1>", snapshotted_files: { a: "1" }, skill_md_raw: "old" };
    const next = { name: "X", readme_html: "<h1>new</h1>", snapshotted_files: { b: "2" }, skill_md_raw: "new" };
    const diffs = computeDiff(prev, next);
    const fields = diffs.filter((d) => d.type !== "readme_updated").map((d) => d.field);
    expect(fields).not.toContain("snapshotted_files");
    expect(fields).not.toContain("skill_md_raw");
    expect(fields).not.toContain("readme_html");
    expect(fields).not.toContain("file_manifest");
  });

  it("F11 — readme_updated indicator when readme_html changes", () => {
    const prev = { readme_html: "<p>old</p>" };
    const next = { readme_html: "<p>new</p>" };
    const diffs = computeDiff(prev, next);
    expect(diffs.some((d) => d.type === "readme_updated")).toBe(true);
  });

  it("F12 — no readme_updated when readme_html absent in both", () => {
    const prev = { name: "X" };
    const next = { name: "X" };
    expect(computeDiff(prev, next).some((d) => d.type === "readme_updated")).toBe(false);
  });

  it("F13 — numeric github_stars diff", () => {
    const prev = { github_stars: 10 };
    const next = { github_stars: 15 };
    const diffs = computeDiff(prev, next);
    expect(diffs[0]).toMatchObject({ field: "github_stars", type: "scalar", old: 10, new: 15 });
  });

  it("F14 — labels added in one snapshot not in other (partial key presence)", () => {
    const prev = {};  // legacy: no labels key
    const next = { labels: ["mcp"] };
    const diffs = computeDiff(prev, next);
    // one side present → diff shown
    expect(diffs.some((d) => d.field === "labels")).toBe(true);
  });

  it("F15 — both scalar and array changes in same snapshot pair", () => {
    const prev = { name: "Old", compatible_platforms: ["claude"] };
    const next = { name: "New", compatible_platforms: ["claude", "cursor"] };
    const diffs = computeDiff(prev, next);
    expect(diffs.length).toBe(2);
  });

  it("F16 — empty string vs null treated as a change", () => {
    const prev = { description: "" };
    const next = { description: null };
    const diffs = computeDiff(prev, next);
    expect(diffs).toHaveLength(1);
  });
});

describe("computeGenesis", () => {
  it("G1 — shows added for initial create fields", () => {
    const snap = { name: "Hello", description: "A skill", compatible_platforms: ["claude"] };
    const diffs = computeGenesis(snap);
    expect(diffs.some((d) => d.field === "name")).toBe(true);
    expect(diffs.some((d) => d.field === "compatible_platforms")).toBe(true);
  });

  it("G2 — does not include readme_updated", () => {
    const snap = { name: "X", readme_html: "<p>init</p>" };
    const diffs = computeGenesis(snap);
    expect(diffs.some((d) => d.type === "readme_updated")).toBe(false);
  });
});
