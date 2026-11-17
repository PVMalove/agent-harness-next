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
  /** Accessible name of a scrolling body; defaults to a text title. */
  label?: string;
  /** Take the free height of the parent column; the body scrolls. */
  fill?: boolean;
  /** Marks a body that may scroll by design: a long list or running text. Any other panel must
      show all its content, which tests/web/console-fit.spec.ts checks. */
  scroll?: "list" | "text";
  children?: ReactNode;
}

export function Panel({ title, count, meta, actions, id, className, fill = false, scroll, label, children }: PanelProps) {
  const name = label ?? (typeof title === "string" ? title : undefined);
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
      {/* A body that can scroll is a focusable region, so the keyboard reaches its overflow (WCAG 2.1.1). */}
      <div className="ds-panel-body" data-scroll={scroll} {...(fill && name ? { role: "region", tabIndex: 0, "aria-label": name } : {})}>
        {children}
      </div>
    </section>
  );
}
