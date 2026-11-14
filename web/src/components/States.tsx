import type { ReactNode } from "react";
import type { DatasetState } from "../app/hooks";

export function Loading({ label = "資料載入中" }: { label?: string }) {
  return (
    <div className="state state-loading" role="status" aria-live="polite">
      <span className="state-loading-label">
        <span className="spinner" aria-hidden="true" />
        {label}…
      </span>
      <span className="skeleton" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
    </div>
  );
}

export function ErrorState({ error }: { error: Error }) {
  return (
    <div className="state state-error" role="alert">
      <span className="state-icon" aria-hidden="true">!</span>
      <strong className="state-title">無法顯示這個頁面</strong>
      <p>{error.message}</p>
      <button className="btn" type="button" onClick={() => window.location.reload()}>重新載入頁面</button>
    </div>
  );
}

/** `asPageTitle` makes the title the page's h1 when the empty state is the whole page. */
export function EmptyState({ title, children, asPageTitle = false }: { title: string; children?: ReactNode; asPageTitle?: boolean }) {
  return (
    <div className="state state-empty">
      <span className="state-icon" aria-hidden="true">∅</span>
      {asPageTitle ? <h1 className="state-title">{title}</h1> : <strong className="state-title">{title}</strong>}
      {children}
    </div>
  );
}

/** Render children only once every dataset is ready; otherwise show state. */
export function Gate<T extends unknown[]>({
  states,
  children,
}: {
  states: { [K in keyof T]: DatasetState<T[K]> };
  children: (...data: T) => ReactNode;
}) {
  const failed = states.find((s) => s.status === "error");
  if (failed && failed.status === "error") return <ErrorState error={failed.error} />;
  if (states.some((s) => s.status === "loading")) return <Loading />;
  const data = states.map((s) => (s.status === "ready" ? s.data : undefined)) as T;
  return <>{children(...data)}</>;
}
