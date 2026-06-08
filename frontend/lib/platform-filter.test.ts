import { describe, it, expect } from "vitest";
import { togglePlatform, buildPlatformsParam } from "./platform-filter";

describe("togglePlatform", () => {
  it("adds a platform when not active", () => {
    expect(togglePlatform(["claude-code"], "opencode")).toEqual(["claude-code", "opencode"]);
  });

  it("removes a platform when already active", () => {
    expect(togglePlatform(["claude-code", "opencode"], "opencode")).toEqual(["claude-code"]);
  });

  it("returns empty array when removing the only active platform", () => {
    expect(togglePlatform(["claude-code"], "claude-code")).toEqual([]);
  });

  it("adds first platform to empty list", () => {
    expect(togglePlatform([], "mcp")).toEqual(["mcp"]);
  });
});

describe("buildPlatformsParam", () => {
  it("joins platforms with comma", () => {
    expect(buildPlatformsParam(["claude-code", "opencode"])).toBe("claude-code,opencode");
  });

  it("returns single platform without comma", () => {
    expect(buildPlatformsParam(["mcp"])).toBe("mcp");
  });

  it("returns null for empty array", () => {
    expect(buildPlatformsParam([])).toBeNull();
  });
});
