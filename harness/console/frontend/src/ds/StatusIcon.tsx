/* A status as a shape plus hidden text, so colour is never the only carrier of meaning (WCAG
   1.4.1): ok is a check, warn a triangle, err a cross, info an i, wait a clock. */
import { Icon } from "../icons";

export type Tone = "ok" | "warn" | "err" | "info" | "wait";
const SHAPE: Record<Tone, string> = { ok: "check", warn: "warning", err: "x", info: "info", wait: "clock" };

export function StatusIcon({ tone, label }: { tone: Tone; label: string }) {
  return (
    <span className={`ds-status ds-status-${tone}`} data-tone={tone}>
      <Icon name={SHAPE[tone]} className="ds-ic-sm" />
      <span className="ds-sr">{label}</span>
    </span>
  );
}
