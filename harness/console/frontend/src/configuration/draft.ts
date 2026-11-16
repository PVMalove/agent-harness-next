/* The one configuration draft of «Настройки», shared by the Parameters, JSON and Changes tabs: per
   file the edited JSON text, keyed by the digest the file was read at, so a new snapshot starts
   afresh. A parameter value and a JSON edit change the same text; the change set is the leaf diff
   of every file against its served (masked) document. Nothing here writes: the Changes tab sends
   the draft through the confirmed configuration job. */
import { useState } from "react";
import { CONFIG_NAMES } from "../ws/projectScreens";
import type { ConfigName, ConfigurationFacts, JsonObject } from "../ws/projectScreens";
import { MASK_REFUSAL, holdsMask, leafChanges } from "./changes";
import type { Change } from "./changes";

export const pretty = (document: JsonObject) => JSON.stringify(document, null, 2);

const isObject = (value: unknown): value is JsonObject => value !== null && typeof value === "object" && !Array.isArray(value);

/** The parsed text of a file, or why it is not a JSON object. */
function parse(text: string): { document: JsonObject | null; error: string | null } {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch (error) {
    return { document: null, error: `JSON: ${(error as Error).message}` };
  }
  return isObject(value) ? { document: value, error: null } : { document: null, error: "Файл должен быть JSON-объектом" };
}

/** `document` with `value` at `path`, every object on the way copied. */
function withValue(document: JsonObject, path: readonly string[], value: unknown): JsonObject {
  const [head, ...rest] = path;
  if (head === undefined) return document;
  const child = document[head];
  return { ...document, [head]: rest.length === 0 ? value : withValue(isObject(child) ? child : {}, rest, value) };
}

/** The value at `path`, or undefined when a key on the way is absent. */
export function valueAt(document: JsonObject, path: readonly string[]): unknown {
  let value: unknown = document;
  for (const key of path) {
    if (!isObject(value) || !Object.hasOwn(value, key)) return undefined;
    value = value[key];
  }
  return value;
}

export interface ConfigurationDraft {
  /** The edited text of a file; its served document when untouched. */
  text(file: ConfigName): string;
  /** The edited document of a file; null while its text is not a JSON object. */
  document(file: ConfigName): JsonObject | null;
  /** Why the text of a file cannot be sent: broken JSON or a typed secret mask. */
  error(file: ConfigName): string | null;
  setText(file: ConfigName, text: string): void;
  /** Sets one value; refused (false) while the file's text is broken. */
  setValue(file: ConfigName, path: readonly string[], value: unknown): boolean;
  /** The leaf changes of every file against its served document. */
  changes: Change[];
  /** The first reason no change can be sent, or null. */
  problem: string | null;
  reset(): void;
}

export function useConfigurationDraft(facts: ConfigurationFacts): ConfigurationDraft {
  const [texts, setTexts] = useState<Record<string, string>>({});
  const key = (file: ConfigName) => `${file}:${facts.files[file].digest}`;
  const text = (file: ConfigName) => texts[key(file)] ?? pretty(facts.files[file].document);
  const document = (file: ConfigName) => parse(text(file)).document;
  const fileChanges = (file: ConfigName): Change[] => {
    const edited = document(file);
    return edited === null ? [] : leafChanges(facts.files[file].document, edited, file);
  };
  const error = (file: ConfigName) => {
    const parsed = parse(text(file));
    if (parsed.error) return parsed.error;
    return fileChanges(file).some((change) => "value" in change && holdsMask(change.value)) ? MASK_REFUSAL : null;
  };
  const setText = (file: ConfigName, next: string) => setTexts((old) => ({ ...old, [key(file)]: next }));
  const setValue = (file: ConfigName, path: readonly string[], value: unknown) => {
    const edited = document(file);
    if (edited === null) return false;
    setText(file, pretty(withValue(edited, path, value)));
    return true;
  };
  const changes = CONFIG_NAMES.flatMap(fileChanges);
  const problem = CONFIG_NAMES.map(error).find((reason) => reason !== null) ?? null;
  return { text, document, error, setText, setValue, changes, problem, reset: () => setTexts({}) };
}
