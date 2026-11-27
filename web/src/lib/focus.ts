/**
 * Where keyboard focus should land after the next route change.
 *
 * Every route change moves focus to <main> so screen-reader and keyboard users start at the top of the new page.
 * That is wrong when the user changed a control that lives on the page itself (the station switcher): they expect
 * to stay on it. The control asks to keep focus before navigating; once the new page has mounted, that page's own
 * control claims focus. App skips its <main> reset while a request is waiting or has just been claimed.
 *
 * This deliberately does not poll for the element: waiting on animation frames stalls in background tabs, and the
 * page that owns the control already knows when it has mounted.
 */
let pending: string | null = null;
let claimed = false;
let expiry: ReturnType<typeof setTimeout> | undefined;

export function requestFocusAfterRoute(id: string): void {
  pending = id;
  claimed = false;
  clearTimeout(expiry);
  // A request must not outlive a navigation that never happens (for example a failed page load).
  expiry = setTimeout(() => { pending = null; claimed = false; }, 3000);
}

/** Called by the page's control when it mounts; true means it should focus itself now. */
export function claimFocusRequest(id: string): boolean {
  if (pending !== id) return false;
  pending = null;
  claimed = true;
  return true;
}

/**
 * Called by App's route-change effect. True when a control is keeping focus (its request is still waiting for its
 * page, or the page already claimed it); the claim only applies to this one route change.
 */
export function focusRequestHandlesRouteChange(): boolean {
  const handled = pending !== null || claimed;
  claimed = false;
  return handled;
}
