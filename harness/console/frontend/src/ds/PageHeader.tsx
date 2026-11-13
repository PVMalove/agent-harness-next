/* The common screen header (title, subtitle, actions) and the summary under it: a strip of three or
   four large figures and a row of facts with the snapshot time. */
import type { ReactNode } from "react";

export function PageHeader({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="ds-page-head">
      <div className="ds-page-title">
        <h1 className="ds-h1">{title}</h1>
        {subtitle ? <p className="ds-sub">{subtitle}</p> : null}
      </div>
      {actions ? <div className="ds-head-actions">{actions}</div> : null}
    </div>
  );
}

export interface Stat {
  label: ReactNode;
  value: ReactNode;
  /** A caption under the figure; absent facts say so, never a made-up number. */
  caption?: ReactNode;
}

export function Summary({ stats, facts, snapshot, id, label }: {
  stats: readonly Stat[];
  facts?: ReactNode;
  /** The snapshot time, at the right end of the facts row. */
  snapshot?: ReactNode;
  id?: string;
  label: string;
}) {
  return (
    <section className="ds-summary" id={id} aria-label={label}>
      <div className="ds-stats">
        {stats.map((stat, index) => (
          <div className="ds-stat" key={index}>
            <span className="ds-stat-label">{stat.label}</span>
            <b className="ds-stat-value">{stat.value}</b>
            {stat.caption ? <small className="ds-stat-caption">{stat.caption}</small> : null}
          </div>
        ))}
      </div>
      <div className="ds-facts">
        <div className="ds-facts-main">{facts}</div>
        {snapshot ? <div className="ds-facts-end">{snapshot}</div> : null}
      </div>
    </section>
  );
}
