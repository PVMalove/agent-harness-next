/* A status as a shape plus hidden text, so colour is never the only carrier of meaning (WCAG
   1.4.1): ok is a check, warn a triangle, err a cross, info an i, wait a clock, off (a switched
   off feature, muted) a crossed circle. Without `label` the icon is decorative: the visible
   text beside it already says the status, and a hidden copy would be read twice. */
import { Icon } from "../icons";

export type Tone = "ok" | "warn" | "err" | "info" | "wait" | "off";
const SHAPE: Record<Tone, string> = { ok: "check", warn: "warning", err: "x", info: "info", wait: "clock", off: "blocked" };

export function StatusIcon({ tone, label }: { tone: Tone; label?: string }) {
  return (
    <span className={`ds-status ds-status-${tone}`} data-tone={tone} aria-hidden={label ? undefined : true}>
      <Icon name={SHAPE[tone]} className="ds-ic-sm" />
      {label ? <span className="ds-sr">{label}</span> : null}
    </span>
  );
}
