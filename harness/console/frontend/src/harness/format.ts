/* Display formatting of the Harness page, mirroring harness/console/kernel/maintenance.py
   `format_size`; the sizes themselves are the server's. */

export function formatSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KiB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MiB`;
}

/** The drift state of harness.overview as the TUI words it (Russian source strings). */
export const DRIFT_LABELS: Readonly<Record<string, string>> = {
  clean: "✔ дрейфа нет",
  drift: "⚠ дрейф есть",
  missing: "○ дрейф: нет lock",
};
export const DRIFT_UNKNOWN = "○ дрейф неизвестен";

export const driftLabel = (drift: string): string => DRIFT_LABELS[drift] ?? DRIFT_UNKNOWN;

/** The last path segment of a worktree path. */
export const baseName = (path: string): string => path.replace(/\/+$/, "").split("/").pop() || path;
