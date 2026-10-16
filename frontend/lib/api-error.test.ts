import { describe, expect, it } from "vitest";
import { errorMessage } from "./api-error";

describe("errorMessage", () => {
  it("returns a string detail as is", () => {
    expect(errorMessage({ detail: "A skill with this repo URL and path already exists." }, 409)).toBe(
      "A skill with this repo URL and path already exists.",
    );
  });

  it("joins the messages of a FastAPI validation error", () => {
    const body = {
      detail: [
        { type: "value_error", loc: ["body"], msg: "Value error, skill_path may contain only letters, digits, '.', '_', '-' and '/'" },
        { type: "missing", loc: ["body", "repo_url"], msg: "Field required" },
      ],
    };
    expect(errorMessage(body, 422)).toBe(
      "skill_path may contain only letters, digits, '.', '_', '-' and '/'; Field required",
    );
  });

  it("falls back to the status when there is no usable detail", () => {
    expect(errorMessage(null, 502)).toBe("HTTP 502");
    expect(errorMessage({ detail: [] }, 422)).toBe("HTTP 422");
    expect(errorMessage({ detail: { code: "x" } }, 400)).toBe("HTTP 400");
  });
});
