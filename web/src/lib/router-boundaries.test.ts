import { describe, expect, it } from "vitest";
import { parseRoute } from "./router";

describe("malformed station route", () => {
  it.each(["#/station/%", "#/station/%E0%A4%A", "#/%zz", "#/station/%FF"])(
    "keeps an invalid encoded path from crashing the app: %s", (hash) => {
      expect(() => parseRoute(hash)).not.toThrow();
      expect(parseRoute(hash).name).toBe("not-found");
    },
  );
  it("decodes a valid Unicode grid identifier", () => {
    expect(parseRoute("#/station/%E5%8F%B0%E5%8C%97")).toMatchObject({ name: "station", station: "台北" });
  });
});
