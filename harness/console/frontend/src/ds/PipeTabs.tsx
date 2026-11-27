/* Numbered pipeline tabs: the tabs of a screen read as steps joined by a connector that CSS draws.
   ARIA Tabs and the arrow keys come from the shared TabList. */
import type { ReactNode } from "react";
import { TabList } from "../views/Tabs";

export interface PipeTab {
  id: string;
  label: ReactNode;
  /** A count of the tab's items. It is shown as the badge, never in the marker: the marker is
      always the step number, so a step and a count never read alike (UX review of #1296). */
  count?: ReactNode;
  /** A count shown after the label while the marker keeps the step number, so a step and a count
      never read alike ("3 JSON" next to "3 Изменения"). Decorative: the panel says it too. */
  badge?: ReactNode;
}

export function PipeTabs({ id, label, tabs, value, onChange }: {
  id: string;
  label: string;
  tabs: readonly PipeTab[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <TabList
      id={id}
      label={label}
      className="ds-pipe"
      tabClass={(selected) => (selected ? "ds-pipe-tab ds-on" : "ds-pipe-tab")}
      tabs={tabs.map((tab, index) => [
        tab.id,
        <>
          <span className="ds-pipe-n">{index + 1}</span>
          <span className="ds-pipe-label">{tab.label}</span>
          {(tab.badge ?? tab.count) !== undefined && (
            <span className="ds-pipe-badge" aria-hidden="true">
              {tab.badge ?? tab.count}
            </span>
          )}
        </>,
      ])}
      value={value}
      onChange={onChange}
    />
  );
}
