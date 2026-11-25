import { describe, expect, it, vi } from "vitest";
import { prefetchRoute } from "./prefetch";

const fakeLoader = (impl?: (name: string) => Promise<unknown>) => ({
  load: vi.fn((name: string) => (impl ? impl(name) : Promise.resolve({ name }))) as never,
});

describe("prefetchRoute", () => {
  it("requests exactly the datasets of the opened route", () => {
    const loader = fakeLoader();
    prefetchRoute(loader, "#/");
    expect((loader.load as unknown as ReturnType<typeof vi.fn>).mock.calls.map((c) => c[0])).toEqual(["overview.json", "propagation.json"]);
  });

  it("requests the model file for the model route and nothing for unknown routes", () => {
    const model = fakeLoader();
    prefetchRoute(model, "#/model");
    expect((model.load as unknown as ReturnType<typeof vi.fn>).mock.calls.map((c) => c[0])).toEqual(["model.json"]);

    const unknown = fakeLoader();
    prefetchRoute(unknown, "#/nowhere");
    expect((unknown.load as unknown as ReturnType<typeof vi.fn>).mock.calls).toHaveLength(0);
  });

  it("attaches a rejection handler so a failed load is not reported as unhandled", () => {
    const catchSpy = vi.fn();
    const failing = { catch: catchSpy };
    const loader = { load: vi.fn(() => failing) } as never;
    expect(() => prefetchRoute(loader, "#/")).not.toThrow();
    expect(catchSpy).toHaveBeenCalledTimes(2);
  });
});
