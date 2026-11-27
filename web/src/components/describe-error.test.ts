import { describe, expect, it } from "vitest";
import { describeError } from "./States";

describe("describeError", () => {
  it.each([
    "Failed to fetch dynamically imported module: https://example.test/assets/Model-abc.js",
    "error loading dynamically imported module: https://example.test/assets/Model-abc.js",
    "Importing a module script failed.",
  ])("replaces the stale-deployment browser message %#", (message) => {
    const text = describeError(new Error(message));
    expect(text).toContain("網站剛更新過");
    expect(text).not.toMatch(/https?:|\.js/);
  });

  it("leaves every other message untouched", () => {
    expect(describeError(new Error("無法載入 model.json（HTTP 500）"))).toBe("無法載入 model.json（HTTP 500）");
  });
});
