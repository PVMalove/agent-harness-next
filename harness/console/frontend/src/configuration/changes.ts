/* The change set of a configuration write, ported from harness/console/kernel/configuration.py
   `_changed_paths` and kernel/configuration_writes.py `draft_changes` / `draft_request` /
   `_holds_mask`. The server replays the leaf changes on the current unmasked files after checking
   the digests, so an untouched masked secret is never written back and a stale file is refused. */
import type { ConfigName, JsonObject } from "../ws/projectScreens";

/** The value every secret of a served document is replaced with (harness.configuration). */
export const SECRET_MASK = "••••••";
export const MASK_REFUSAL = "Скрытое значение нельзя записать: введите его заново";

export type Change =
  | { file: ConfigName; path: string[]; value: unknown }
  | { file: ConfigName; path: string[]; remove: true };

const isObject = (value: unknown): value is JsonObject =>
  value !== null && typeof value === "object" && !Array.isArray(value);

/** Python `==` over JSON values: objects regardless of key order, lists in order. */
export function jsonEqual(a: unknown, b: unknown): boolean {
  if (Array.isArray(a) || Array.isArray(b)) {
    return Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((item, index) => jsonEqual(item, b[index]));
  }
  if (isObject(a) || isObject(b)) {
    if (!isObject(a) || !isObject(b)) return false;
    const keys = Object.keys(a);
    return keys.length === Object.keys(b).length && keys.every((key) => Object.hasOwn(b, key) && jsonEqual(a[key], b[key]));
  }
  return a === b;
}

/** Leaf paths whose value differs; objects are compared key by key (`_changed_paths`). */
function changedPaths(old: unknown, next: unknown, prefix: string[] = []): string[][] {
  if (isObject(old) && isObject(next)) {
    const paths: string[][] = [];
    for (const key of new Set([...Object.keys(old), ...Object.keys(next)])) {
      if (!Object.hasOwn(old, key) || !Object.hasOwn(next, key)) paths.push([...prefix, key]);
      else paths.push(...changedPaths(old[key], next[key], [...prefix, key]));
    }
    return paths;
  }
  return jsonEqual(old, next) ? [] : [prefix];
}

const MISSING = Symbol("missing");

function lookup(document: unknown, path: readonly string[]): unknown {
  let value: unknown = document;
  for (const key of path) {
    if (!isObject(value) || !Object.hasOwn(value, key)) return MISSING;
    value = value[key];
  }
  return value;
}

/** The edits of `edited` against `base`, leaf by leaf: a set value or a removed key. */
export function leafChanges(base: JsonObject, edited: JsonObject, file: ConfigName): Change[] {
  return changedPaths(base, edited).map((path) => {
    const value = lookup(edited, path);
    return value === MISSING ? { file, path, remove: true as const } : { file, path, value };
  });
}

/** Whether `value` holds the secret mask anywhere (`_holds_mask`). */
export function holdsMask(value: unknown): boolean {
  if (isObject(value)) return Object.values(value).some(holdsMask);
  if (Array.isArray(value)) return value.some(holdsMask);
  return value === SECRET_MASK;
}

/** The `request` of a draft write: its changes, the digests of the files they touch and the
    description, as compact JSON (`draft_request`). An untouched file is not named, so the write
    never re-encodes it. */
export function draftRequest(changes: readonly Change[], digests: Readonly<Record<string, string>>, description: string): string {
  const expected: Record<string, string> = {};
  for (const change of changes) expected[change.file] = digests[change.file] ?? "";
  return JSON.stringify({ changes, expected, description });
}
