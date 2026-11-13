/* A small, safe Markdown renderer for the console guide of help.snapshot: `#`–`###` headings,
   `- ` list items, `|` tables, blank-line paragraphs, `code`, **bold** and [text](target). Every
   piece becomes a React element with text children; no HTML string is injected, and a link shows
   its target as code instead of an anchor, so the page never points to an external URL. */
import type { ReactNode } from "react";

const INLINE = /(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/;

/** The inline pieces of one line. */
export function inline(text: string): ReactNode[] {
  return text
    .split(INLINE)
    .filter((part) => part !== "")
    .map((part, index) => {
      if (part.startsWith("`") && part.endsWith("`") && part.length > 1) return <code key={index}>{part.slice(1, -1)}</code>;
      if (part.startsWith("**") && part.endsWith("**") && part.length > 4) return <b key={index}>{part.slice(2, -2)}</b>;
      const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(part);
      if (link) {
        return (
          <span key={index}>
            {link[1]} (<code>{link[2]}</code>)
          </span>
        );
      }
      return <span key={index}>{part}</span>;
    });
}

type Block =
  | { kind: "heading"; level: number; text: string }
  | { kind: "list"; items: string[] }
  | { kind: "table"; rows: string[][] }
  | { kind: "paragraph"; lines: string[] };

const cells = (line: string) =>
  line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
const isRule = (line: string) => /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$/.test(line.trim());

/** The blocks of a Markdown text. */
export function blocks(markdown: string): Block[] {
  const found: Block[] = [];
  let open: Block | null = null;
  const close = () => {
    if (open) found.push(open);
    open = null;
  };
  for (const raw of markdown.split("\n")) {
    const line = raw.trimEnd();
    const heading = /^(#{1,3}) (.*)$/.exec(line);
    if (!line.trim()) {
      close();
    } else if (heading) {
      close();
      found.push({ kind: "heading", level: heading[1]!.length, text: heading[2]! });
    } else if (line.startsWith("- ")) {
      if (open?.kind !== "list") {
        close();
        open = { kind: "list", items: [] };
      }
      (open as { items: string[] }).items.push(line.slice(2));
    } else if (line.trimStart().startsWith("|")) {
      if (open?.kind !== "table") {
        close();
        open = { kind: "table", rows: [] };
      }
      if (!isRule(line)) (open as { rows: string[][] }).rows.push(cells(line));
    } else if (open?.kind === "list" && raw.startsWith("  ")) {
      const items = (open as { items: string[] }).items;
      items[items.length - 1] += ` ${line.trim()}`;
    } else {
      if (open?.kind !== "paragraph") {
        close();
        open = { kind: "paragraph", lines: [] };
      }
      (open as { lines: string[] }).lines.push(line.trim());
    }
  }
  close();
  return found;
}

const plain = (text: string) => text.replace(/[`*]/g, "").replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1 $2").toLowerCase();

/** The text a block shows, lower-cased and without markup, for the search of the Help page. */
export function blockText(block: Block): string {
  if (block.kind === "heading") return plain(block.text);
  if (block.kind === "list") return plain(block.items.join(" "));
  if (block.kind === "table") return plain(block.rows.map((row) => row.join(" ")).join(" "));
  return plain(block.lines.join(" "));
}

/** The items a Markdown text lists: list entries and table body rows. */
export function countItems(markdown: string): number {
  return blocks(markdown).reduce((n, block) => n + (block.kind === "list" ? block.items.length : block.kind === "table" ? Math.max(block.rows.length - 1, 0) : 0), 0);
}

/** `match` keeps only the blocks that contain the (lower-cased) query. */
export function Markdown({ text, match = "" }: { text: string; match?: string }) {
  return (
    <div className="ds-md">
      {blocks(text).filter((block) => !match || blockText(block).includes(match)).map((block, index) => {
        if (block.kind === "heading") {
          // The page title is the only h1: a guide title and its sections are h2, a subsection h3.
          const Tag = (["h2", "h2", "h3"] as const)[block.level - 1]!;
          return <Tag key={index}>{inline(block.text)}</Tag>;
        }
        if (block.kind === "list") {
          return (
            <ul key={index}>
              {block.items.map((item, at) => (
                <li key={at}>{inline(item)}</li>
              ))}
            </ul>
          );
        }
        if (block.kind === "table") {
          const [head, ...rows] = block.rows;
          return (
            <div className="ds-table-wrap" key={index} role="region" tabIndex={0} aria-label={head ? head.map((cell) => plain(cell)).join(" · ") : "table"}>
              <table>
                {head && (
                  <thead>
                    <tr>
                      {head.map((cell, at) => (
                        <th key={at}>{inline(cell)}</th>
                      ))}
                    </tr>
                  </thead>
                )}
                <tbody>
                  {rows.map((row, at) => (
                    <tr key={at}>
                      {row.map((cell, col) => (
                        <td key={col}>{inline(cell)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        return <p key={index}>{inline(block.lines.join(" "))}</p>;
      })}
    </div>
  );
}
