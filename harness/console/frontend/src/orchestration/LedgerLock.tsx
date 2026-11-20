/* The ledger lock panel: who holds the lock, for how long and how it may be released, worded as
   the TUI's `lock_text`. The page only reads the lock; releasing it is a TUI command. */
import { useI18n } from "../i18n";
import type { LockState } from "../ws/ledger";
import { lockLines } from "./format";

export function LedgerLock({ lock }: { lock: LockState }) {
  const { language } = useI18n();
  return (
    <section className="panel orch-lock" id="ledger-lock">
      <div className="panel-head">
        <h2>Lock ledger</h2>
      </div>
      <div className="orch-lock-body">
        {lockLines(lock.lock, lock.error, language).map((line, index) => (
          <p key={index}>{line}</p>
        ))}
      </div>
    </section>
  );
}
