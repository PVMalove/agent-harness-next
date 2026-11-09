/* Update Harness (#/update-harness): the installed and available versions, the drift counters,
   the three update modes with the plan, the seed files and the file diffs of
   update_harness.snapshot. A file's diff is read (update_harness.diff) only once the file is
   clicked. «Обновить» runs only through the CommandPanel of the job section `update`, and every
   run opens the confirmation first: cancelling it starts nothing. */
import { useState } from "react";
import { CommandPanel } from "../commands/CommandPanel";
import type { RunRequest } from "../commands/CommandPanel";
import { useI18n } from "../i18n";
import { Icon } from "../icons";
import { useServedRepo } from "../project/format";
import { useScreen } from "../screens/useScreen";
import {
  ICONS,
  MODES,
  MODE_CONSEQUENCES,
  SEED_MODE,
  diffFiles,
  diffText,
  filesText,
  planReason,
  renderDrift,
  renderVersions,
  seedFiles,
  stopWarning,
  updateCommand,
} from "../update/format";
import type { DiffFile, UpdateMode } from "../update/format";
import { parseUpdateDiff, parseUpdateHarness } from "../ws/projectScreens";

const lineClass = (line: string) =>
  line.startsWith("+") && !line.startsWith("+++") ? "diff-line add" : line.startsWith("-") && !line.startsWith("---") ? "diff-line del" : "diff-line";

/** One file's diff, read when it is mounted (a click on the file). */
function DiffPane({ file }: { file: DiffFile }) {
  const { t, language } = useI18n();
  const screen = useScreen({ type: "update_harness.diff", params: { path: file.path } }, parseUpdateDiff);
  const text = screen.data ? diffText(screen.data.text, language) : "";
  return (
    <div className="diff-detail" id="update-diff-view">
      <div className="diff-detail-head">
        <code>{file.path}</code>
      </div>
      <p className="diff-explain">{t(file.meaning)}</p>
      {screen.error ? (
        <p className="command-refusal err" role="alert">
          {t("diff недоступен:")} {screen.error.message || screen.error.code}
        </p>
      ) : !screen.data ? (
        <p className="harness-note">{t("загружается…")}</p>
      ) : text ? (
        <pre className="diff-code">
          {text.split("\n").map((line, index) => (
            <span key={index} className={lineClass(line)}>
              {line}
              {"\n"}
            </span>
          ))}
        </pre>
      ) : (
        <p className="harness-note ok">{t("Файл уже совпадает с тем, что запишет обновление.")}</p>
      )}
    </div>
  );
}

export function UpdateHarness() {
  const { t, section, language } = useI18n();
  const screen = useScreen({ type: "update_harness.snapshot" }, parseUpdateHarness);
  const facts = screen.data;
  const repo = useServedRepo();
  const [mode, setMode] = useState<UpdateMode>("update");
  const [ticked, setTicked] = useState<string[]>([]);
  const [opened, setOpened] = useState<string | null>(null);
  const [request, setRequest] = useState<RunRequest | null>(null);

  const drift = facts?.drift ?? null;
  const seeds = seedFiles(drift);
  const selected = seeds.filter((path) => ticked.includes(path));
  const files = diffFiles(drift);
  const file = files.find((item) => item.path === opened) ?? null;
  const command = updateCommand(mode, repo ?? "<repo>", mode === SEED_MODE ? selected : []);
  const reason = facts ? planReason(facts, mode, selected) : null;
  const warning = stopWarning(drift, mode, t, language);
  const [consequence, tone] = MODE_CONSEQUENCES[mode];
  const modeName = MODES.find(([key]) => key === mode)?.[1] ?? "";
  const versions = facts ? renderVersions(facts, t) : null;
  const changes = renderDrift(drift, t);

  const run = () => {
    if (!facts || reason !== null) return;
    setRequest({
      command_id: mode,
      values: mode === SEED_MODE ? { paths: selected.join("\n") } : {},
      nonce: Date.now(),
      reason: [command, t(consequence), ...(warning ?? [])].join("\n"),
    });
  };
  const toggle = (path: string) => setTicked(ticked.includes(path) ? ticked.filter((item) => item !== path) : [...ticked, path]);

  return (
    <div className="update-page work-page" data-section="Update Harness">
      <div className="page-title update-title">
        <div>
          <h1>{section("Update Harness")}</h1>
          <p>{t("Обновление управляемых файлов Harness в проекте сервера; перед запуском — подтверждение.")}</p>
          {facts && (
            <div className="home-facts">
              <span id="update-cache">
                {screen.cached ? t("Кэш") : t("Новый снимок")} · {screen.ageSeconds ?? 0} s
              </span>
            </div>
          )}
        </div>
        <div className="actions">
          <button id="update-recheck" className="btn" type="button" onClick={() => screen.refresh(true)}>
            <Icon name="refresh" /> {t("Проверить заново")}
          </button>
        </div>
      </div>

      {screen.error && !facts && (
        <p className="command-refusal err" role="alert" data-code={screen.error.code}>
          {t("Данные не получены")}: {screen.error.message || screen.error.code}
        </p>
      )}

      {facts && versions && (
        <section className="panel update-section versions-card" id="update-versions">
          <div className="update-top-grid">
            <div className="versions-body">
              <div className="panel-head">
                <h2>{t("Версии")}</h2>
              </div>
              {versions.missing.map((line) => (
                <p key={line} className="harness-note">
                  {line}
                </p>
              ))}
              <div className="version-pair">
                {versions.pairs.map(([label, value]) => (
                  <div className="version-block" key={label}>
                    <span>{label}</span>
                    <b className="version">{value}</b>
                  </div>
                ))}
              </div>
              {versions.verdict && <p className={`version-status ${versions.verdict.tone}`}>{versions.verdict.text}</p>}
              <dl className="version-facts">
                {versions.rows.map(([label, value]) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
            </div>
            <div className="versions-changes" id="update-changes">
              <div className="panel-head">
                <h2>{t("Что изменится в управляемых файлах")}</h2>
              </div>
              <div className="update-counts">
                {changes.rows.map((row) => (
                  <div className={`update-count-row ${row.tone}`} key={row.label}>
                    {`${row.count} ${ICONS[row.tone]} ${row.label}`}
                  </div>
                ))}
                {changes.line && <div className={`update-count-row ${changes.line.tone ?? ""}`}>{changes.line.text}</div>}
              </div>
            </div>
          </div>
        </section>
      )}

      {facts && (
        <section className="panel update-section" id="update-plan-block">
          <div className="update-mid-grid">
            <div className="modes-card">
              <div className="panel-head">
                <h2>{t("Режим обновления")}</h2>
                <span className="small muted">{t(modeName)}</span>
              </div>
              <div className="modes" role="radiogroup" aria-label={t("Режим обновления")}>
                {MODES.map(([key, label]) => (
                  <label key={key} className={`mode-card${key === mode ? " on" : ""}`}>
                    <input type="radio" name="update-mode" checked={key === mode} onChange={() => setMode(key)} />
                    <span className="mode-copy">{t(label)}</span>
                  </label>
                ))}
              </div>
              <p className={`modes-foot${tone === "warn" ? " warn" : ""}`} id="update-mode-caption">
                {t(consequence)}
              </p>
            </div>
            <div className="plan-card">
              <div className="panel-head">
                <h2>{t("План")}</h2>
              </div>
              <pre className="plan-command" id="update-plan-command">
                $ {command}
              </pre>
              {warning && (
                <div className="plan-warning" id="update-warning">
                  <p>{warning[0]}</p>
                  <p className="muted">{warning[1]}</p>
                </div>
              )}
              <p className="plan-note">{t("Команда перезаписывает файлы харнесса в проекте (управляемые или seed) — незакоммиченные правки в них пропадут.")}</p>
              <p className="plan-note">{t("Перед запуском будет запрошено подтверждение.")}</p>
              <div className="actions">
                <button id="update-run" className="btn primary" type="button" disabled={reason !== null} title={reason ? t(reason) : undefined} onClick={run}>
                  <Icon name="refresh" /> {t("Обновить")}
                </button>
                {reason && <span className="muted">{t(reason)}</span>}
              </div>
            </div>
          </div>
        </section>
      )}

      {facts && (
        <section className={`panel seed-panel${mode === SEED_MODE ? "" : " seed-off"}`} id="update-seeds">
          <div className="panel-head">
            <h2>{t("Seed-файлы")}</h2>
            <span className="small muted" id="update-seed-count">
              {t("отмечено {ticked} из {total}", { ticked: selected.length, total: seeds.length })}
            </span>
          </div>
          <div className="seed-body">
            {seeds.map((path) => (
              <label key={path} className="seed-file">
                <input type="checkbox" checked={selected.includes(path)} disabled={mode !== SEED_MODE} onChange={() => toggle(path)} />
                <code>{path}</code>
              </label>
            ))}
            <p className={`seed-warning${seeds.length ? " warn" : " ok"}`}>
              {seeds.length
                ? `${ICONS.warn} ${t("Отмечены файлы, которые будут перезаписаны эталоном; их правки пропадут.")}`
                : `${ICONS.ok} ${t("Seed-файлы совпадают с шаблоном — перезаписывать нечего.")}`}
            </p>
            <div className="seed-actions">
              <button className="btn small" type="button" disabled={mode !== SEED_MODE} onClick={() => setTicked(seeds)}>
                {t("Выбрать все")}
              </button>
              <button className="btn small" type="button" disabled={mode !== SEED_MODE} onClick={() => setTicked([])}>
                {t("Снять выбор")}
              </button>
            </div>
          </div>
        </section>
      )}

      {facts && (
        <section className="panel update-diff-panel" id="update-diff">
          <div className="panel-head">
            <h2>{t("Diff — что изменится в файлах")}</h2>
            <span className="small muted">{filesText(files.length, language)}</span>
          </div>
          {files.length === 0 ? (
            <p className="harness-note">{t("Расхождений нет: показывать нечего.")}</p>
          ) : (
            <div className="diff-layout">
              <div className="diff-list" role="listbox" aria-label={t("Файлы")}>
                {files.map((item) => (
                  <button
                    key={item.path}
                    type="button"
                    role="option"
                    aria-selected={item.path === opened}
                    className={`diff-file${item.path === opened ? " on" : ""}`}
                    data-path={item.path}
                    onClick={() => setOpened(item.path)}
                  >
                    <span className="diff-path">{item.path}</span>
                    <span className={`diff-kind ${item.tone}`}>{`${ICONS[item.tone]} ${t(item.tag)}`}</span>
                  </button>
                ))}
              </div>
              <div className="diff-panel">{file ? <DiffPane key={file.path} file={file} /> : <p className="harness-note">{t("Выберите файл, чтобы увидеть его изменения.")}</p>}</div>
            </div>
          )}
        </section>
      )}

      <CommandPanel section="update" confirmAll listed={false} request={request} onJobDone={() => screen.refresh(true)} />
    </div>
  );
}
