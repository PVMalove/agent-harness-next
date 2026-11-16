/* The AI hints of the Parameters tab: the user's own Codex CLI or Claude Code CLI login, used only
   on an explicit press. «Проверить CLI» sends advisor.check (presence, version and login, never a
   model call); «Спросить ИИ» sends advisor.ask with the file and path of the parameter only;
   «Отменить», another parameter or another provider cancel the ask. An accepted advice goes into
   the draft only; a refusal, a timeout or an invalid answer shows the console recommendation and
   leaves the draft as it was. */
import { useEffect, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { useConsole } from "../useConsole";
import type { Advice, AdvisorProvider, CliStatus, FallbackCause } from "../ws/advisor";
import type { WizardParam } from "../ws/projectScreens";
import { shown } from "./Wizard";

type Choice = "none" | AdvisorProvider;
const CHOICES: readonly (readonly [Choice, string])[] = [
  ["none", "Без ИИ"],
  ["codex", "Codex CLI"],
  ["claude", "Claude Code CLI"],
];
const CAUSES: Readonly<Record<FallbackCause, string>> = {
  refused: "CLI отказал в подсказке",
  invalid: "Ответ ИИ не прошёл проверку",
  timeout: "ИИ не ответил за 90 с",
  cancelled: "Запрос отменён",
  closed: "Соединение с сервером прервано",
};

const stage = (value: boolean | null) => (value === null ? "не проверено" : value ? "да" : "нет");

export function AdvisorPanel({ param, onAccept }: { param: WizardParam; onAccept: (value: unknown) => void }) {
  const { t } = useI18n();
  const { client } = useConsole();
  const [choice, setChoice] = useState<Choice>("none");
  const [status, setStatus] = useState<CliStatus | null>(null);
  const [checking, setChecking] = useState(false);
  const [asking, setAsking] = useState<string | null>(null);
  const [advice, setAdvice] = useState<Advice | null>(null);
  const [fallback, setFallback] = useState<{ cause: FallbackCause; reason: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef<string | null>(null);
  const paramKey = `${param.file}:${param.path.join(".")}`;

  useEffect(
    () =>
      client.subscribeAdvisor((event) => {
        if (event.type === "advisor-status") {
          setChecking(false);
          setStatus(event.status);
          return;
        }
        if (event.type === "advisor-error" && event.request === "check") {
          setChecking(false);
          setError(event.message || event.code);
          return;
        }
        if (event.type === "advisor-error" && event.request === "cancel") return;
        if (event.requestId === null || event.requestId !== pending.current) return;
        pending.current = null;
        setAsking(null);
        if (event.type === "advisor-advice") setAdvice(event.advice);
        else if (event.type === "advisor-fallback") setFallback({ cause: event.cause, reason: event.reason });
        else setFallback({ cause: "refused", reason: event.message || event.code });
      }),
    [client],
  );

  const cancel = () => {
    const id = pending.current;
    if (id === null) return;
    pending.current = null;
    setAsking(null);
    client.cancelAdvice(id);
  };
  // Another parameter drops the answer of the previous one and cancels its ask.
  useEffect(() => {
    setAdvice(null);
    setFallback(null);
    return cancel;
    // `cancel` reads the ref only.
  }, [paramKey]);

  const choose = (next: Choice) => {
    cancel();
    setChoice(next);
    setStatus(null);
    setAdvice(null);
    setFallback(null);
    setError(null);
  };
  const check = () => {
    if (choice === "none") return;
    setError(null);
    setChecking(client.checkAdvisor(choice));
  };
  const ask = () => {
    if (choice === "none") return;
    setAdvice(null);
    setFallback(null);
    setError(null);
    const id = client.askAdvisor(choice, param.file, param.path);
    pending.current = id;
    setAsking(id);
    if (id === null) setError(t("Нет соединения с сервером консоли"));
  };
  const recommendation = param.recommendation ?? null;

  return (
    <article className="ds-wz-param ds-advisor" id="configuration-advisor" aria-label={t("ИИ-подсказки")}>
      <div className="ds-wz-head">
        <span>{t("ИИ-подсказки")}</span>
        <span className="ds-wz-muted">{t("только по кнопке; запись — через вкладку «Изменения»")}</span>
      </div>
      <div className="ds-advisor-choices" role="radiogroup" aria-label={t("Источник подсказки")}>
        {CHOICES.map(([value, label]) => (
          <label key={value} className="ds-wz-toggle">
            <input type="radio" name="configuration-advisor" value={value} checked={choice === value} onChange={() => choose(value)} /> {t(label)}
          </label>
        ))}
      </div>
      <div className="ds-wz-actions">
        <button className="ds-btn ds-btn-sm" type="button" disabled={choice === "none" || checking} onClick={check}>
          {t("Проверить CLI")}
        </button>
        <button className="ds-btn ds-btn-sm" type="button" disabled={choice === "none" || asking !== null} onClick={ask}>
          {t("Спросить ИИ")}
        </button>
        {asking !== null && (
          <button className="ds-btn ds-btn-sm" type="button" onClick={cancel}>
            {t("Отменить")}
          </button>
        )}
      </div>
      {status && (
        <dl className="ds-kv ds-advisor-status" id="configuration-advisor-status">
          <div className="ds-kv-row">
            <dt>{t("CLI найден")}</dt>
            <dd data-tone={status.found ? "ok" : "err"}>{t(status.found ? "да" : "нет")}</dd>
          </div>
          <div className="ds-kv-row">
            <dt>{t("Версия CLI")}</dt>
            <dd data-tone={status.version_supported === false ? "err" : status.version_supported ? "ok" : undefined}>{t(stage(status.version_supported))}</dd>
          </div>
          <div className="ds-kv-row">
            <dt>{t("Авторизация")}</dt>
            <dd data-tone={status.authorized === false ? "err" : status.authorized ? "ok" : undefined}>{t(stage(status.authorized))}</dd>
          </div>
          <div className="ds-kv-row">
            <dt>{t("Итог")}</dt>
            <dd>{status.message}</dd>
          </div>
        </dl>
      )}
      {asking !== null && <p className="ds-note" role="status">{t("Жду ответ ИИ, не дольше 90 с…")}</p>}
      {error && (
        <p className="ds-alert ds-alert-err" role="alert">
          {error}
        </p>
      )}
      {advice && (
        <div className="ds-wz-line ds-wz-rec" id="configuration-advice">
          <b>{t("Совет ИИ:")}</b> <code>{shown(advice.value)}</code>
          <p className="ds-wz-desc">{advice.why}</p>
          <p className="ds-wz-desc">{advice.impact}</p>
          {advice.comparison.length > 0 && (
            <ul className="ds-advisor-compare">
              {advice.comparison.map((row) => (
                <li key={row.option}>
                  <code>{row.option}</code> — {row.tradeoff}
                </li>
              ))}
            </ul>
          )}
          <button className="ds-btn ds-btn-sm ds-btn-primary" type="button" onClick={() => onAccept(advice.value)}>
            {t("Принять совет ИИ")}
          </button>
        </div>
      )}
      {fallback && (
        <div className="ds-alert ds-alert-warn" role="status" id="configuration-advice-fallback">
          <div>
            <b>{t(CAUSES[fallback.cause])}</b>
            {fallback.reason && <p>{fallback.reason}</p>}
            <p>
              {t("Рекомендация консоли:")} {recommendation ? <code>{shown(recommendation.value)}</code> : t("нет рекомендации")}
            </p>
          </div>
        </div>
      )}
    </article>
  );
}
