/* WAI-ARIA Tabs pattern shared by every tabbed page (WCAG 2.1 AA, 4.1.2): each tab controls its
   tabpanel, only the selected tab is in the Tab order (roving tabindex) and the arrow keys, Home
   and End move the selection with automatic activation. */
import type { KeyboardEvent, ReactNode } from "react";

export type TabSpec = readonly [id: string, label: ReactNode];

export const tabId = (id: string, tab: string) => `${id}-tab-${tab}-button`;
const panelId = (id: string, tab: string) => `${id}-tab-${tab}`;

export function TabList({
  id,
  label,
  tabs,
  value,
  onChange,
  className = "orch-tabbar",
  tabClass = (selected) => `orch-tab${selected ? " on" : ""}`,
  attrs,
  sharedPanel,
}: {
  id: string;
  label: string;
  tabs: readonly TabSpec[];
  value: string;
  onChange: (id: string) => void;
  className?: string;
  tabClass?: (selected: boolean) => string;
  /** Extra per-tab attributes a page or its tests rely on (`data-*`, `title`). */
  attrs?: (tab: string) => Record<string, string | undefined>;
  /** One panel element whose content swaps with the tab: every tab controls this id. */
  sharedPanel?: string;
}) {
  const move = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const last = tabs.length - 1;
    const next =
      event.key === "ArrowRight"
        ? (index + 1) % tabs.length
        : event.key === "ArrowLeft"
          ? (index - 1 + tabs.length) % tabs.length
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? last
              : -1;
    if (next < 0) return;
    event.preventDefault();
    const target = tabs[next][0];
    onChange(target);
    document.getElementById(tabId(id, target))?.focus();
  };
  return (
    <div id={`${id}-tabs`} className={className} role="tablist" aria-label={label}>
      {tabs.map(([tab, text], index) => (
        <button
          key={tab}
          id={tabId(id, tab)}
          type="button"
          className={tabClass(tab === value) || undefined}
          role="tab"
          aria-selected={tab === value}
          aria-controls={sharedPanel ?? panelId(id, tab)}
          tabIndex={tab === value ? 0 : -1}
          onClick={() => onChange(tab)}
          onKeyDown={(event) => move(event, index)}
          {...attrs?.(tab)}
        >
          {text}
        </button>
      ))}
    </div>
  );
}

/** One tabpanel; its children render only while its tab is selected (or always, hidden, with
 * `keepMounted` for a panel whose state must survive a tab change); the element itself always stays
 * so every tab's `aria-controls` names an existing panel. */
export function TabPanel({
  id,
  tab,
  value,
  className,
  keepMounted = false,
  children,
}: {
  id: string;
  tab: string;
  value: string;
  className?: string;
  keepMounted?: boolean;
  children?: ReactNode;
}) {
  const active = tab === value;
  return (
    <div
      id={panelId(id, tab)}
      className={className}
      role="tabpanel"
      aria-labelledby={tabId(id, tab)}
      hidden={!active}
      tabIndex={active ? 0 : undefined}
    >
      {active || keepMounted ? children : null}
    </div>
  );
}

/** Panels for every tab of a list: the selected one holds `children`, the others stay empty, so a
 * page keeps its own conditional content and every `aria-controls` still resolves. */
export function TabPanels({
  id,
  tabs,
  value,
  className,
  children,
}: {
  id: string;
  tabs: readonly TabSpec[];
  value: string;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <>
      {tabs.map(([tab]) => (
        <TabPanel key={tab} id={id} tab={tab} value={value} className={className}>
          {children}
        </TabPanel>
      ))}
    </>
  );
}
