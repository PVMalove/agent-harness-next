/* The ledger lock panel: who holds the lock, for how long and how it may be released, worded as
   the TUI's `lock_text`. The page only reads the lock; releasing it is a TUI command. */
import { StatusIcon } from "../ds";
import { useI18n } from "../i18n";
import type { LockState } from "../ws/ledger";
import { lockLines, lockState } from "./format";

/** The state of the panel as a status tone: free, held, not read. */
const TONES = { ok: "ok", warn: "warn", fail: "err" } as const;

export function LedgerLock({ lock }: { lock: LockState }) {
  const { language } = useI18n();
  const tone = TONES[lockState(lock.lock)];
  return (
    <section className="panel orch-lock" id="ledger-lock">
      <div className="panel-head">
        <h2>Lock ledger</h2>
      </div>
      <div className="orch-lock-body">
        {lockLines(lock.lock, lock.error, language).map((line, index) =>
          index === 0 ? (
            <p key={index} className={`orch-lock-head ${tone}`} data-state={tone}>
              <StatusIcon tone={tone} /> <b>{line}</b>
            </p>
          ) : (
            <p key={index}>{line}</p>
          ),
        )}
      </div>
    </section>
  );
}
