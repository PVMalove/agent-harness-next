/* The KPI row and the four analytics tabs of the Orchestration page. The figures are the
   server's (`pipeline_kpi`, `pipeline_analytics`); a tab only chooses which rows are drawn. */
import { useState } from "react";
import { useI18n } from "../i18n";
import type { Tile } from "../reports/format";
import type { Analytics as AnalyticsFigures, AnalyticsSection } from "../ws/ledger";
import { ANALYTICS_TABS, analyticsRows } from "./format";

export function KpiRow({ tiles, id, className }: { tiles: readonly Tile[]; id: string; className: string }) {
  return (
    <div className={className} id={id}>
      {tiles.map((tile) => (
        <div key={tile.label} data-tone={tile.tone || undefined}>
          <span>{tile.label}</span>
          <b className={tile.tone === "warning" ? "warn" : undefined}>{tile.figure}</b>
          {tile.hint && <small>{tile.hint}</small>}
        </div>
      ))}
    </div>
  );
}

export function Analytics({ analytics }: { analytics: AnalyticsFigures }) {
  const { t, language } = useI18n();
  const [section, setSection] = useState<AnalyticsSection>("flow");
  return (
    <section className="panel orch-analytics" id="orch-analytics">
      <div className="panel-head orch-analytics-head">
        <h2>{t("Аналитика")}</h2>
        <div className="orch-tabbar" role="tablist" aria-label={t("Аналитика")}>
          {ANALYTICS_TABS.map(([key, title]) => (
            <button
              key={key}
              type="button"
              role="tab"
              className={`orch-tab${key === section ? " on" : ""}`}
              aria-selected={key === section}
              onClick={() => setSection(key)}
            >
              {t(title)}
            </button>
          ))}
        </div>
      </div>
      {ANALYTICS_TABS.map(([key]) => (
        <dl key={key} className="orch-analytics-rows" data-tab={key} hidden={key !== section}>
          {analyticsRows(key, analytics, t, language).map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      ))}
    </section>
  );
}
