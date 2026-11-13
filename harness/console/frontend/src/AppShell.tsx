/* The shell of the design system v3 (docs/rfc/web-console-v3.md): top bar, the collapsible rail,
   a mobile drawer and the footer. Pages render into main#content. */
import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useLocation, useNavigate } from "react-router";
import { Icon } from "./icons";
import { useI18n, LANGUAGES } from "./i18n";
import { DS_ROUTES, HIDDEN_LABELS, NAV_GROUPS, SHORTCUTS, href, navItemOf } from "./navigation";
import type { NavItem } from "./navigation";
import { useConsole } from "./useConsole";
import type { HomeSnapshot } from "./ws/types";

export const COLLAPSED_KEY = "harness-nav-collapsed";

/** A semver pre-release suffix (`2.1.0-rc.1` -> "rc.1"), else null: the badge shows only then. */
export function preRelease(version: string): string | null {
  const match = /^v?\d+\.\d+\.\d+-([0-9A-Za-z.-]+)(?:\+[0-9A-Za-z.-]+)?$/.exec(version.trim());
  return match ? match[1]! : null;
}

interface Counter {
  text: string;
  css: string;
}

/** The menu counters of the mockup, each from the Home snapshot; no counter without data. */
export function menuCounter(route: string, snapshot: HomeSnapshot | null): Counter | null {
  if (snapshot === null) return null;
  if (route === "diagnostics") {
    const { fail, warn } = snapshot.health;
    if (fail) return { text: String(fail), css: "err" };
    return warn ? { text: String(warn), css: "warn" } : null;
  }
  if (route === "update-harness" || route === "harness") {
    const drift = snapshot.drift_counts?.total ?? 0;
    return drift ? { text: String(drift), css: "warn" } : null;
  }
  if (route === "repo-map") {
    const tier = snapshot.repo_map.tier;
    return tier ? { text: tier, css: tier === "full" ? "full" : "warn" } : null;
  }
  return null;
}

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
  /** A connection page (no server, error, empty) is on screen: it keeps the old page style. */
  connectionPage?: boolean;
  children: ReactNode;
}

export function AppShell({ chip, banner, connectionPage = false, children }: AppShellProps) {
  const { t, section, language, setLanguage } = useI18n();
  const { state } = useConsole();
  const snapshot = state.snapshot;
  const version = snapshot?.harness_version ?? "";
  const channel = version ? preRelease(version) : null;
  const project = snapshot?.project ?? null;
  const location = useLocation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const current = location.pathname.replace(/^\/+/, "").split("/")[0] ?? "";
  const selected = navItemOf(current);
  const legacyPage = connectionPage || !DS_ROUTES.has(current);
  const menuLabel = (item: NavItem): string => (item.label ? t(item.label) : section(item.section));
  const pageLabel = HIDDEN_LABELS[current] ? t(HIDDEN_LABELS[current]!) : menuLabel(selected);

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
    document.title = `Harness Console · ${pageLabel}`;
  }, [pageLabel]);

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
    <div className="ds-app" id="app">
      <a
        className="ds-skip"
        href="#content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("content")?.focus();
        }}
      >
        {t("Перейти к содержимому")}
      </a>
      <header className="ds-top">
        <button
          id="menu-toggle"
          className="ds-icon-btn ds-menu-toggle"
          type="button"
          aria-label={open ? t("Закрыть меню") : t("Открыть меню")}
          aria-expanded={open}
          aria-controls="navigation"
          onClick={() => setOpen(!open)}
        >
          <Icon name="menu" className="ds-ic" />
        </button>
        <button
          id="nav-collapse"
          className="ds-icon-btn ds-nav-collapse"
          type="button"
          aria-label={collapseLabel}
          title={collapseLabel}
          aria-expanded={!collapsed}
          aria-controls="navigation"
          onClick={() => setCollapsed(!collapsed)}
        >
          <Icon name="chevron" className="ds-ic-sm" />
        </button>
        <a className="ds-brand" href={href("")}>
          <span className="ds-logo" aria-hidden="true">
            H›
          </span>
          <b>Harness next</b>
          {version ? <span className="ds-version">{version}</span> : null}
          {channel ? <span className="ds-channel">pre-release</span> : null}
        </a>
        {project ? (
          <span id="project" className="ds-where">
            {project.name}
          </span>
        ) : null}
        {project?.branch ? (
          <span id="branch" className="ds-where ds-muted">
            <Icon name="branch" className="ds-ic-sm" />
            {project.branch}
          </span>
        ) : null}
        <div className="ds-top-end">
          {chip}
          <div className="ds-seg" role="group" aria-label={t("Язык интерфейса")}>
            {LANGUAGES.map((option) => (
              <button
                key={option}
                type="button"
                lang={option}
                aria-pressed={option === language}
                aria-label={`${option.toUpperCase()} · ${option === "ru" ? t("Русский язык") : t("Английский язык")}`}
                onClick={() => setLanguage(option)}
              >
                {option.toUpperCase()}
              </button>
            ))}
          </div>
          <a className="ds-icon-btn" href={href("help")} aria-label={section("Help")} title={section("Help")}>
            <Icon name="help" className="ds-ic" />
          </a>
        </div>
      </header>
      {banner}
      {/* A div, not <nav>: the old sheet styles every nav element. */}
      <div id="navigation" className="ds-rail" role="navigation" aria-label={t("Разделы консоли")}>
        {NAV_GROUPS.map((group) => (
          <div className="ds-nav-group" key={group.label}>
            <div className="ds-nav-label">{t(group.label)}</div>
            {group.items.map((item) => {
              const counter = menuCounter(item.route, snapshot);
              return (
                <a
                  key={item.route}
                  className="ds-nav-link"
                  href={href(item.route)}
                  title={counter ? `${menuLabel(item)} · ${counter.text}` : menuLabel(item)}
                  aria-current={item === selected ? "page" : undefined}
                  onClick={() => setOpen(false)}
                >
                  <span className="ds-nav-icon">
                    <Icon name={item.icon} className="ds-ic" />
                  </span>
                  <span className="ds-nav-text">{menuLabel(item)}</span>
                  {counter ? (
                    <span className={`ds-count ds-count-${counter.css}`} aria-hidden="true" data-route={item.route}>
                      {counter.text}
                    </span>
                  ) : null}
                </a>
              );
            })}
          </div>
        ))}
      </div>
      <div id="nav-scrim" className="ds-scrim" hidden={!open} onClick={() => setOpen(false)} />
      <main id="content" tabIndex={-1} className={legacyPage ? "ds-main ds-main--legacy" : "ds-main"}>
        {children}
      </main>

      <footer className="ds-foot">
        <div className="ds-keys">
          <span>
            <b className="ds-kbd">?</b> {section("Help")}
          </span>
          <span>
            <b className="ds-kbd">g</b> {section("Home")}
          </span>
          <span>
            <b className="ds-kbd">d</b> {section("Diagnostics")}
          </span>
          <span>
            <b className="ds-kbd">o</b> {section("Orchestration")}
          </span>
        </div>
        <span id="foot-status">
          {[version || null, snapshot?.store?.authority ?? null, pageLabel].filter(Boolean).join(" · ")}
        </span>
      </footer>
    </div>
  );
}
