/* The shell of docs/design/web-console-mockups/execution-console-prototype.html: header, the
   collapsible navigation, a mobile drawer and the footer. Pages render into main#content. */
import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useLocation, useNavigate } from "react-router";
import { Icon } from "./icons";
import { useI18n, LANGUAGES } from "./i18n";
import { NAV_GROUPS, SHORTCUTS, href, navItemOf } from "./navigation";

export const COLLAPSED_KEY = "harness-nav-collapsed";
export const VERSION = "2.0.0";

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

export interface AppShellProps {
  /** The connection chip in the header. */
  chip?: ReactNode;
  /** The connection banner above the navigation. */
  banner?: ReactNode;
  children: ReactNode;
}

export function AppShell({ chip, banner, children }: AppShellProps) {
  const { t, section, language, setLanguage } = useI18n();
  const location = useLocation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const current = location.pathname.replace(/^\/+/, "").split("/")[0] ?? "";
  const selected = navItemOf(current);

  useEffect(() => {
    document.body.classList.toggle("nav-open", open);
  }, [open]);

  useEffect(() => {
    document.body.classList.toggle("nav-collapsed", collapsed);
    try {
      localStorage.setItem(COLLAPSED_KEY, collapsed ? "1" : "0");
    } catch {
      /* Storage is optional. */
    }
  }, [collapsed]);

  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    document.title = `Harness Console · ${section(selected.section)}`;
  }, [section, selected]);

  const onKey = useCallback(
    (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest?.("input,textarea,select,[contenteditable=true]")) return;
      if (event.key === "Escape") {
        setOpen(false);
        return;
      }
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      const route = SHORTCUTS[event.key];
      if (route !== undefined) navigate(`/${route}`);
    },
    [navigate],
  );

  useEffect(() => {
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onKey]);

  const collapseLabel = collapsed ? t("Развернуть меню") : t("Свернуть меню");

  return (
    <div className="app" id="app">
      <header className="top">
        <button
          id="menu-toggle"
          className="icon-btn menu-toggle"
          type="button"
          aria-label={open ? t("Закрыть меню") : t("Открыть меню")}
          aria-expanded={open}
          aria-controls="navigation"
          onClick={() => setOpen(!open)}
        >
          <Icon name="menu" />
        </button>
        <button
          id="nav-collapse"
          className="icon-btn nav-collapse"
          type="button"
          aria-label={collapseLabel}
          title={collapseLabel}
          aria-expanded={!collapsed}
          aria-controls="navigation"
          onClick={() => setCollapsed(!collapsed)}
        >
          <Icon name="chevron" />
        </button>
        <a className="brand" href={href("")}>
          <span className="logo" aria-hidden="true">
            H›
          </span>
          <b>Harness Console</b>
          <span className="version">{VERSION}</span>
        </a>
        <div className="top-actions">
          {chip}
          <div className="seg lang-switch" role="group" aria-label={t("Язык интерфейса")}>
            {LANGUAGES.map((option) => (
              <button
                key={option}
                type="button"
                lang={option}
                className={option === language ? "on" : ""}
                aria-pressed={option === language}
                aria-label={option === "ru" ? t("Русский язык") : t("Английский язык")}
                onClick={() => setLanguage(option)}
              >
                {option.toUpperCase()}
              </button>
            ))}
          </div>
          <a className="icon-btn" href={href("help")} aria-label={section("Help")} title={section("Help")}>
            ?
          </a>
        </div>
      </header>

      <div className="layout">
        {banner}
        <nav id="navigation" aria-label={t("Разделы консоли")}>
          {NAV_GROUPS.map((group) => (
            <div className="nav-group" key={group.label}>
              <div className="nav-group-label">{t(group.label)}</div>
              {group.items.map((item) => (
                <a
                  key={item.route}
                  href={href(item.route)}
                  title={section(item.section)}
                  aria-current={item === selected ? "page" : undefined}
                  onClick={() => setOpen(false)}
                >
                  <span className="nav-icon">
                    <Icon name={item.icon} />
                  </span>
                  <span className="nav-label">{section(item.section)}</span>
                </a>
              ))}
            </div>
          ))}
        </nav>
        <div id="nav-scrim" className="nav-scrim" hidden={!open} onClick={() => setOpen(false)} />
        <main id="content">{children}</main>
      </div>

      <footer className="foot">
        <div className="keys">
          <span>
            <b className="k">?</b> {section("Help")}
          </span>
          <span>
            <b className="k">g</b> {section("Home")}
          </span>
          <span>
            <b className="k">d</b> {section("Diagnostics")}
          </span>
          <span>
            <b className="k">o</b> {section("Orchestration")}
          </span>
        </div>
        <span id="foot-status" className="r">
          {VERSION} · {section(selected.section)} · {t("Только чтение")}
        </span>
      </footer>
    </div>
  );
}
