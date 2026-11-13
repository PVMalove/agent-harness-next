/* The block of tiles that closes the free height of a screen ("Связанные разделы", "Читать дальше"):
   three per row, each with an icon, a title, an optional count, a description and a chevron. */
import type { ReactNode } from "react";
import { Icon } from "../icons";
import { Panel } from "./Panel";

export interface Tile {
  key: string;
  icon: string;
  title: ReactNode;
  count?: ReactNode;
  text: ReactNode;
  /** A link target; without it the tile is a button that calls `onSelect`. */
  href?: string;
}

export function RelatedTiles({ title, tiles, onSelect, id }: {
  title: ReactNode;
  tiles: readonly Tile[];
  onSelect?: (key: string) => void;
  id?: string;
}) {
  const body = (tile: Tile) => (
    <>
      <span className="ds-tile-icon">
        <Icon name={tile.icon} className="ds-ic" />
      </span>
      <span className="ds-tile-text">
        <b className="ds-tile-title">
          {tile.title}
          {tile.count !== undefined && tile.count !== null ? <span className="ds-tile-count">{tile.count}</span> : null}
        </b>
        <small className="ds-tile-desc">{tile.text}</small>
      </span>
      <Icon name="chevron" className="ds-ic-sm ds-tile-go" />
    </>
  );
  return (
    <Panel title={title} count={tiles.length} id={id} className="ds-tiles-panel">
      <div className="ds-tiles">
        {tiles.map((tile) =>
          tile.href !== undefined ? (
            <a key={tile.key} className="ds-tile" href={tile.href}>
              {body(tile)}
            </a>
          ) : (
            <button key={tile.key} type="button" className="ds-tile" onClick={() => onSelect?.(tile.key)}>
              {body(tile)}
            </button>
          ),
        )}
      </div>
    </Panel>
  );
}
