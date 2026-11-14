import { describe, expect, it } from "vitest";
import { parseRoute, routeDatasets } from "./router";

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

describe("route data prefetch", () => {
  it("requests only the files the opened route renders", () => {
    expect(routeDatasets(parseRoute("#/"))).toEqual(["overview.json", "propagation.json"]);
    expect(routeDatasets(parseRoute("#/station/臺北網格?for=general"))).toEqual(["overview.json", "model.json"]);
    expect(routeDatasets(parseRoute("#/anomalies?id=x"))).toEqual(["anomalies.json"]);
    expect(routeDatasets(parseRoute("#/model"))).toEqual(["model.json"]);
    expect(routeDatasets(parseRoute("#/whatif"))).toEqual(["whatif.json", "overview.json"]);
    expect(routeDatasets(parseRoute("#/nowhere"))).toEqual([]);
  });
});
