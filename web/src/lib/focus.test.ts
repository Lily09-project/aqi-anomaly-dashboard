import { afterEach, describe, expect, it, vi } from "vitest";
import { focusWhenAvailable, requestFocusAfterRoute, takeFocusRequest } from "./focus";

afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = "";
  takeFocusRequest();
});

describe("focus request", () => {
  it("is handed out exactly once", () => {
    requestFocusAfterRoute("station-switch");
    expect(takeFocusRequest()).toBe("station-switch");
    expect(takeFocusRequest()).toBeNull();
  });

  it("expires when the navigation never happens", () => {
    vi.useFakeTimers();
    requestFocusAfterRoute("station-switch");
    vi.advanceTimersByTime(3001);
    expect(takeFocusRequest()).toBeNull();
  });
});

describe("focusWhenAvailable", () => {
  it("focuses an element that already exists", () => {
    document.body.innerHTML = '<select id="station-switch"></select>';
    const fallback = vi.fn();
    focusWhenAvailable("station-switch", fallback);
    expect(document.activeElement?.id).toBe("station-switch");
    expect(fallback).not.toHaveBeenCalled();
  });

  it("waits for an element that appears a few frames later", async () => {
    const fallback = vi.fn();
    focusWhenAvailable("late", fallback);
    setTimeout(() => { document.body.innerHTML = '<select id="late"></select>'; }, 40);
    await new Promise((resolve) => setTimeout(resolve, 150));
    expect(document.activeElement?.id).toBe("late");
    expect(fallback).not.toHaveBeenCalled();
  });

  it("uses the fallback when the element never appears", () => {
    const fallback = vi.fn();
    focusWhenAvailable("missing", fallback, 0);
    expect(fallback).toHaveBeenCalledTimes(1);
  });
});
