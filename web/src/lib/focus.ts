/**
 * Where keyboard focus should land after the next route change.
 *
 * Every route change moves focus to <main> so screen-reader and keyboard users start at the top of the new page.
 * That is wrong when the user changed a control that lives on the page itself (the station switcher): they
 * expect to stay on it. The control asks for its own focus before navigating; App honours the request once the
 * new page has rendered, and falls back to <main> if the element never appears.
 */
let pending: string | null = null;
let expiry: ReturnType<typeof setTimeout> | undefined;

export function requestFocusAfterRoute(id: string): void {
  pending = id;
  clearTimeout(expiry);
  // A request must not outlive a navigation that never happens (for example a failed page load).
  expiry = setTimeout(() => { pending = null; }, 3000);
}

export function takeFocusRequest(): string | null {
  const id = pending;
  pending = null;
  clearTimeout(expiry);
  return id;
}

/** Focus `id` as soon as it exists (checked every frame for about a second); otherwise call `fallback`. */
export function focusWhenAvailable(id: string, fallback: () => void, frames = 60): void {
  const attempt = (left: number) => {
    const target = document.getElementById(id);
    if (target) {
      target.focus({ preventScroll: true });
      return;
    }
    if (left <= 0) {
      fallback();
      return;
    }
    requestAnimationFrame(() => attempt(left - 1));
  };
  attempt(frames);
}
