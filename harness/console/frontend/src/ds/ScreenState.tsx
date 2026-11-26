/* The state of a screen snapshot before its data arrives: loading, or a failure that names what
   was not received and offers a retry. Shown before any empty-state copy, so "still loading",
   "really empty" and "the server failed" never look alike (UX review of #1296). */
import { useI18n } from "../i18n";
import type { Screen } from "../screens/useScreen";

export function ScreenState<T>({ screen, noun }: { screen: Screen<T>; noun: string }) {
  const { t } = useI18n();
  if (screen.data !== null) return null;
  if (screen.error) {
    return (
      <div className="ds-alert ds-alert-err" role="alert" data-code={screen.error.code}>
        <div>
          <b>
            {t(noun)}: {screen.error.message || screen.error.code}
          </b>
          <p>{t("Повторите запрос; если ошибка повторяется, откройте Диагностику.")}</p>
        </div>
        <button type="button" className="ds-btn" onClick={() => screen.refresh(true)}>
          {t("Повторить")}
        </button>
      </div>
    );
  }
  if (screen.loading) {
    return (
      <p className="ds-note ds-loading" role="status" aria-live="polite">
        {t("Загрузка…")}
      </p>
    );
  }
  return null;
}

/** A project whose orchestration ledger does not exist yet: a normal first run, not a failure. */
export function LedgerAbsent({ reason }: { reason: string | null | undefined }) {
  const { t } = useI18n();
  if (!reason) return null;
  return (
    <div className="ds-alert" role="status" data-ledger="absent">
      <div>
        <b>{t("Оркестрация в этом проекте ещё не запускалась")}</b>
        <p>{t("Данные появятся после первого batch; как его запустить, описано в Справке.")}</p>
      </div>
      <a className="ds-btn" href="#/help">
        {t("Справка")}
      </a>
    </div>
  );
}
