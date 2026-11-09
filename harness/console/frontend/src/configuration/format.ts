/* Wording of the Configuration page, mirroring harness/console/tui/screens/configuration.py
   (`_ADAPTER_STATUS`, the adapter name as the path stem) and its gating texts. The facts are the
   server's configuration.snapshot; tests/web/fixtures/configuration-facts.json pins the texts. */
import type { ConfigurationFacts } from "../ws/projectScreens";

/** An adapter state: its symbol and the TUI's Russian word. */
export const ADAPTER_STATUS: Readonly<Record<string, readonly [string, string]>> = {
  current: ["✔", "актуален"],
  outdated: ["⚠", "требует обновления"],
  missing: ["○", "не установлен"],
};

export const NO_SCHEMA =
  "Сначала установите engineering-suite или backend-orchestration через меню подключения проекта";
export const PENDING = "Незавершённая запись конфигурации: сначала восстановите её";

/** The adapter's name: the file name without its extension (`Path(path).stem`). */
export function adapterName(path: string): string {
  const name = path.split("/").pop() ?? path;
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(0, dot) : name;
}

/** The first 12 characters of a digest; a missing file has none. */
export const shortDigest = (digest: string): string => (digest ? digest.slice(0, 12) : "—");

/** Why no write of a file can start, or null: no schema installed or a pending transaction. */
export function writeBlock(facts: ConfigurationFacts): string | null {
  if (!facts.schema_installed) return NO_SCHEMA;
  if (facts.transaction_pending) return PENDING;
  return null;
}
