import { useId, type ReactNode } from "react";

/**
 * One section of an analysis page, read in a fixed order:
 * the numbered title, a one-sentence takeaway computed from the data,
 * the chart or controls, then a "how to read" margin note.
 */
export function Chapter({
  no,
  title,
  takeaway,
  howTo,
  children,
  className,
  testId,
  liveTakeaway = false,
  level = 2,
}: {
  no: string;
  title: string;
  /** One sentence, computed from the data shown below it. */
  takeaway?: ReactNode;
  /** Method and reading notes; sits in the margin on wide screens. */
  howTo?: ReactNode;
  children: ReactNode;
  className?: string;
  testId?: string;
  /** Announce takeaway changes (the sentence recomputes when controls change). */
  liveTakeaway?: boolean;
  /** Heading level; 3 when the chapter sits inside another titled block. */
  level?: 2 | 3;
}) {
  const Heading = level === 3 ? "h3" : "h2";
  const id = useId();
  return (
    <section className={["chapter", howTo ? "has-note" : "", className ?? ""].filter(Boolean).join(" ")} aria-labelledby={`${id}-title`} data-testid={testId}>
      <header className="chapter-head">
        <span className="chapter-no" aria-hidden="true">
          {no}
        </span>
        <Heading id={`${id}-title`}>{title}</Heading>
        {takeaway && (
          <p className="chapter-takeaway" aria-live={liveTakeaway ? "polite" : undefined}>
            {takeaway}
          </p>
        )}
      </header>
      <div className="chapter-body">{children}</div>
      {howTo && (
        <div className="how-to" role="note" aria-label={`怎麼讀：${title}`}>
          <span className="how-to-title" aria-hidden="true">
            怎麼讀
          </span>
          {howTo}
        </div>
      )}
    </section>
  );
}

/** Shared header for the analysis pages. */
export function PageHead({ kicker, title, children }: { kicker: ReactNode; title: string; children?: ReactNode }) {
  return (
    <header className="page-head">
      <span className="eyebrow">{kicker}</span>
      <h1>{title}</h1>
      {children}
    </header>
  );
}
