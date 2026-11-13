/* A panel with one header for every screen: title on the left, a count, then the actions and the
   meta text on the right (design system v3). `fill` makes it take the free height of a flex column
   and scroll inside its body. */
import type { ReactNode } from "react";

export interface PanelProps {
  title: ReactNode;
  /** A count chip next to the title. */
  count?: ReactNode;
  /** A short caption on the right of the header. */
  meta?: ReactNode;
  /** Buttons on the right of the header. */
  actions?: ReactNode;
  id?: string;
  className?: string;
  /** Take the free height of the parent column; the body scrolls. */
  fill?: boolean;
  children?: ReactNode;
}

export function Panel({ title, count, meta, actions, id, className, fill = false, children }: PanelProps) {
  const classes = ["ds-panel", fill ? "ds-panel-fill" : "", className ?? ""].filter(Boolean).join(" ");
  return (
    <section id={id} className={classes}>
      <div className="ds-panel-head">
        <h2 className="ds-panel-title">{title}</h2>
        {count !== undefined && count !== null ? <span className="ds-chip">{count}</span> : null}
        <div className="ds-panel-end">
          {meta ? <span className="ds-panel-meta">{meta}</span> : null}
          {actions}
        </div>
      </div>
      <div className="ds-panel-body">{children}</div>
    </section>
  );
}
