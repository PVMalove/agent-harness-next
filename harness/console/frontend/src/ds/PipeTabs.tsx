/* Numbered pipeline tabs: the tabs of a screen read as steps joined by a connector that CSS draws.
   ARIA Tabs and the arrow keys come from the shared TabList. */
import type { ReactNode } from "react";
import { TabList } from "../views/Tabs";

export interface PipeTab {
  id: string;
  label: ReactNode;
  /** The number in the marker; the step number when absent. */
  count?: ReactNode;
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
          <span className="ds-pipe-n">{tab.count ?? index + 1}</span>
          <span className="ds-pipe-label">{tab.label}</span>
        </>,
      ])}
      value={value}
      onChange={onChange}
    />
  );
}
