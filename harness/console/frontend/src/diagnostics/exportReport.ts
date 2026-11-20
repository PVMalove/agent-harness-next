/* The Diagnostics export: the shown report with the active filter and only the visible checks,
   saved as a JSON file through a Blob URL (no inline script or style, the CSP stays as it is). */
import type { HealthCheck, HealthReport } from "../ws/screens";

export interface DiagnosticsExport {
  schema_version: number;
  repo: string;
  online: boolean;
  summary: HealthReport["summary"];
  fixes_applied: string[];
  filter: string;
  query: string;
  checks: HealthCheck[];
}

export function exportPayload(
  report: HealthReport,
  filter: string,
  query: string,
  visible: readonly HealthCheck[],
): DiagnosticsExport {
  return {
    schema_version: report.schema_version,
    repo: report.repo,
    online: report.online,
    summary: report.summary,
    fixes_applied: report.fixes_applied,
    filter,
    query,
    checks: [...visible],
  };
}

/** `harness-diagnostics-YYYY-MM-DD-HH-MM-SS.json` for `when`. */
export const exportName = (when: Date): string =>
  `harness-diagnostics-${when.toISOString().slice(0, 19).replace(/[:T]/g, "-")}.json`;

/** Offer `payload` as a download named `name`; false when the browser cannot make a Blob URL. */
export function downloadJson(name: string, payload: unknown): boolean {
  if (typeof URL.createObjectURL !== "function") return false;
  const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  return true;
}
