/* The detail of one check: its status, group and message, why it matters (the kernel catalog of
   check rationales; an unknown id says no data), the remedy and the manual command of the report, the source of the report and, for a skipped check, why a skip is not a pass. The
   console never runs a remedy command; "Исправить" runs the server's internal fixers. */
import { useState } from "react";
import { Icon } from "../icons";
import { checkRationale, groupLabel, useI18n } from "../i18n";
import type { HealthCheck } from "../ws/screens";
import { STATUS_META } from "./CheckList";

export function CheckDetail({
  check,
  cli,
  online,
  clock,
  onFix,
}: {
  check: HealthCheck | null;
  cli: string;
  online: boolean;
  clock: string;
  onFix: () => void;
}) {
  const { t, language } = useI18n();
  const [copied, setCopied] = useState<string | null>(null);
  if (!check) {
    return (
      <section className="panel diag-detail-panel">
        <div className="diag-empty">
          <b>{t("Проверка не выбрана")}</b>
          <span>{t("Выберите строку слева.")}</span>
        </div>
      </section>
    );
  }
  const meta = STATUS_META[check.status];
  const rationale = checkRationale(language, check.id);
  const command = check.fix?.command ?? null;
  const copy = () => {
    if (command === null) return;
    void navigator.clipboard?.writeText(command).then(
      () => setCopied(check.id),
      () => setCopied(null),
    );
  };
  return (
    <section className="panel diag-detail-panel" data-check={check.id}>
      <div className="panel-head">
        <h2>{t("Детали проверки")}</h2>
        <div className="diag-detail-head-actions">
          <button
            className="btn primary diag-fix-btn"
            type="button"
            disabled={check.status === "ok"}
            title={t("Применяются только внутренние фиксы. Команды «Как исправить» остаются ручными.")}
            onClick={onFix}
          >
            <Icon name="settings" /> {t("Исправить")}
          </button>
          <span className={`diag-pill ${meta.tone}`}>{meta.short}</span>
        </div>
      </div>
      <div className="diag-detail-body">
        <div className="diag-detail-top">
          <span className="diag-area">{groupLabel(language, check.group)}</span>
          <code>{check.id}</code>
        </div>
        <h3>{check.message}</h3>
        <p className="diag-detail-lead">{groupLabel(language, check.group)} · {meta.short}</p>
        <dl className="diag-facts">
          <div>
            <dt>{t("Что проверено")}</dt>
            <dd>{check.message}</dd>
          </div>
          <div>
            <dt>{t("Почему важно")}</dt>
            {rationale !== null ? (
              <dd className="diag-rationale">{rationale}</dd>
            ) : (
              <dd className="muted no-data" title={t("Описания этой проверки в каталоге нет")}>
                {t("нет данных")}
              </dd>
            )}
          </div>
          <div>
            <dt>{t("Что сделать")}</dt>
            <dd>{check.fix ? check.fix.text : t("Рекомендация отсутствует")}</dd>
          </div>
          <div>
            <dt>{t("Команда")}</dt>
            <dd>{command !== null ? <code>{command}</code> : t("Команда отсутствует — проверьте настройки вручную")}</dd>
          </div>
        </dl>
        {command !== null && (
          <div className="diag-action">
            <button className="btn" type="button" onClick={copy}>
              {t("Копировать команду")}
            </button>
            {copied === check.id && (
              <span className="small muted diag-copied" role="status">
                {t("Команда скопирована")}
              </span>
            )}
          </div>
        )}
        <div className="diag-source">
          <span>{t("Источник")}</span>
          <code>{cli}</code>
          <span>
            {online ? t("онлайн") : t("офлайн")} · {clock}
          </span>
        </div>
        {check.status === "skipped" && (
          <p className="diag-callout">{t("Пропуск не считается успехом. Онлайн-проверки требуют сети и прав.")}</p>
        )}
      </div>
    </section>
  );
}
