import { afterEach, describe, expect, it, vi } from "vitest";
import { claimFocusRequest, focusRequestHandlesRouteChange, requestFocusAfterRoute } from "./focus";

afterEach(() => {
  vi.useRealTimers();
  // Reset module state between tests.
  claimFocusRequest("station-switch");
  focusRequestHandlesRouteChange();
});

describe("focus request", () => {
  it("is claimed exactly once, and only by the control that asked", () => {
    requestFocusAfterRoute("station-switch");
    expect(claimFocusRequest("something-else")).toBe(false);
    expect(claimFocusRequest("station-switch")).toBe(true);
    expect(claimFocusRequest("station-switch")).toBe(false);
  });

  it("tells App to leave <main> alone while the request waits for its page", () => {
    requestFocusAfterRoute("station-switch");
    expect(focusRequestHandlesRouteChange()).toBe(true);
    expect(focusRequestHandlesRouteChange()).toBe(true); // still waiting: the page has not mounted yet
  });

  it("tells App to leave <main> alone when the page claimed focus before App's effect ran, for one route change only", () => {
    requestFocusAfterRoute("station-switch");
    claimFocusRequest("station-switch"); // child effects run before the parent's
    expect(focusRequestHandlesRouteChange()).toBe(true);
    expect(focusRequestHandlesRouteChange()).toBe(false);
  });

  it("lets App reset focus to <main> when nothing was requested", () => {
    expect(focusRequestHandlesRouteChange()).toBe(false);
  });

  it("expires when the navigation never happens", () => {
    vi.useFakeTimers();
    requestFocusAfterRoute("station-switch");
    vi.advanceTimersByTime(3001);
    expect(claimFocusRequest("station-switch")).toBe(false);
    expect(focusRequestHandlesRouteChange()).toBe(false);
  });
});
