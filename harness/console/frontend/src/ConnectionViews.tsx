/* The connection chip, the reconnecting banner and the no server / error / empty pages of the
   mockup's connectionPage, driven by the real client state. */
import { Icon } from "./icons";
import { useI18n } from "./i18n";
import { href } from "./navigation";
import type { ConnectionStatus } from "./connection";
import { useConsole } from "./useConsole";

type Translate = (text: string) => string;

const CHIP: Record<ConnectionStatus, { css: string; label: (t: Translate) => string }> = {
  connected: { css: "connected", label: () => "online" },
  reconnecting: { css: "reconnecting", label: () => "reconnect" },
  no_server: { css: "offline", label: (t) => t("нет сервера") },
  error: { css: "error", label: (t) => t("ошибка") },
  empty: { css: "empty", label: (t) => t("пусто") },
};

/** Statuses that replace the page content with a connection page. */
export const PAGE_STATUSES: readonly ConnectionStatus[] = ["no_server", "error", "empty"];

/** Routes whose own data is the Home health snapshot: only they show the shared empty page;
    every other page shows the empty state of its own data (H3). */
export const EMPTY_PAGE_ROUTES: readonly string[] = ["", "diagnostics"];

/** Whether the connection page replaces the content of `route`. */
export const showsConnectionPage = (status: ConnectionStatus, route: string): boolean =>
  status === "empty" ? EMPTY_PAGE_ROUTES.includes(route) : PAGE_STATUSES.includes(status);

export function ConnectionChip() {
  const { t } = useI18n();
  const { state } = useConsole();
  const chip = CHIP[state.status];
  const label = chip.label(t);
  return (
    <span
      id="connection-state"
      className={`conn-chip ${chip.css}`}
      role="status"
      aria-label={t("Состояние соединения: {state}", { state: label })}
      data-status={state.status}
    >
      <i />
      <span>{label}</span>
    </span>
  );
}

export function ConnectionBanner() {
  const { t } = useI18n();
  const { state, client } = useConsole();
  if (state.status !== "reconnecting") return null;
  const waiting = state.attempt === 0 && state.snapshot === null;
  return (
    <div id="connection-banner" className="connection-banner" role="status" aria-live="polite">
      <span className="conn-spinner" />
      <div>
        <b>{waiting ? t("Ожидание снимка") : t("Переподключение к серверу консоли")}</b>
        {waiting ? null : (
          <small>
            {t("Попытка {attempt} · следующая через {delay} с", {
              attempt: state.attempt,
              delay: state.nextDelayMs / 1000,
            })}
            {state.stale ? ` · ${t("Последний снимок устарел")}` : ""}
          </small>
        )}
      </div>
      <button className="btn" type="button" onClick={() => client.retryNow()}>
        {t("Повторить сейчас")}
      </button>
    </div>
  );
}

export function ConnectionPage() {
  const { t, section, language } = useI18n();
  const { state, client, snapshotAt } = useConsole();
  const retry = () => client.retryNow();
  const last = snapshotAt
    ? new Intl.DateTimeFormat(language, { timeStyle: "medium" }).format(snapshotAt)
    : t("нет");
  let page: {
    css: string;
    icon: string;
    eyebrow: string;
    title: string;
    text: string;
    facts: [string, string][];
    action: string;
    onAction: () => void;
  };
  if (state.status === "no_server") {
    page = {
      css: "offline",
      icon: "pulse",
      eyebrow: t("СОЕДИНЕНИЕ · НЕТ СЕРВЕРА"),
      title: t("Нет связи с сервером консоли"),
      text: t("Сервер консоли не отвечает. Запустите harness console --web и откройте выданную ссылку."),
      facts: [
        ["endpoint", client.url],
        [t("последний снимок"), last],
        [t("Попытка"), String(state.attempt)],
      ],
      action: t("Повторить подключение"),
      onAction: retry,
    };
  } else if (state.status === "error") {
    page = {
      css: "error",
      icon: "warning",
      eyebrow: t("ЗАГРУЗКА · ОШИБКА"),
      title: t("Не удалось загрузить данные"),
      text:
        state.errorCode === "session_rejected"
          ? t("Сервер отклонил сессию. Откройте новую ссылку из harness console --web.")
          : state.errorCode === "invalid_snapshot"
            ? t("Ответ получен, но снимок не прошёл проверку. Показывать старые данные как актуальные нельзя.")
            : t("Сервер ответил ошибкой."),
      facts: [
        ["endpoint", client.url],
        [t("Код"), state.errorCode ?? "—"],
        [t("последний снимок"), last],
      ],
      action: t("Загрузить заново"),
      onAction: retry,
    };
  } else {
    page = {
      css: "empty",
      icon: "reports",
      eyebrow: t("ДАННЫЕ · ПУСТО"),
      title: t("Данных пока нет"),
      text: t("Соединение установлено, но снимок не содержит ни одной проверки. Это не ошибка загрузки."),
      facts: [
        [t("соединение"), "online"],
        [t("Проверки"), "0"],
        [t("последний снимок"), last],
      ],
      action: t("Обновить"),
      onAction: () => client.requestHome({ force: true }),
    };
  }
  return (
    <section className={`panel connection-page ${page.css}`} data-status={state.status}>
      <div className="connection-page-icon">
        <Icon name={page.icon} />
      </div>
      <span className="eyebrow">{page.eyebrow}</span>
      <h1>{page.title}</h1>
      <p>{page.text}</p>
      <div className="connection-facts">
        {page.facts.map(([key, value]) => (
          <div key={key}>
            <span>{key}</span>
            <b>{value}</b>
          </div>
        ))}
      </div>
      <div className="connection-page-actions">
        <button className="btn primary" type="button" onClick={page.onAction}>
          {page.action}
        </button>
        <a className="btn" href={href("help")}>
          <Icon name="help" /> {section("Help")}
        </a>
      </div>
    </section>
  );
}
