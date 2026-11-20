// Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
// SPDX-License-Identifier: BUSL-1.1
// Licensed under the Business Source License 1.1 (BSL-1.1).
// Commercial use, sale, or use in commercial application development is strictly
// prohibited without prior written permission from the copyright holder.
// Removing or altering this header is prohibited and voids all license rights.

//! `worktree.create` and `worktree.remove`: the managed issue worktrees of the repository
//! (issue #1180); `worktree.commit`: a commit in one of them (issue #1246).
//!
//! The coordinator runs inside an agent sandbox that mounts the repository's `.git/worktrees`
//! read-only, so `git worktree add` and `git worktree remove` fail there, and so do `git add` and
//! `git commit` of an in-process writer in a worktree the session did not create. The runtime runs
//! outside the sandbox, so it creates and removes these worktrees and commits in them when the
//! coordinator or its writer asks.
//!
//! The requester is sandboxed and the runtime is not, so an operation must not let the requester
//! run code or touch a path outside the managed roots. A path is a strict descendant of a managed
//! root and crosses no symbolic link below the repository root; a branch or a base never reads as
//! an option; every Git call disables the hooks and the fsmonitor and gets its arguments as
//! separate items, never through a shell. A Git call in a worktree names the administrative
//! directory of the main repository, never the gitfile the requester can rewrite, and a change
//! never lands on the base branch or an `integration/*` branch.

use std::collections::BTreeMap;
use std::fs;
use std::path::{Component, Path, PathBuf};
use std::process::{Command, Output, Stdio};

use contracts::{ErrorBody, ErrorCode, FailureDomain};
use serde_json::{Value, json};

use crate::paths::canonical;

/// The managed root `worktree.create` creates in, relative to the repository root.
const SANDBOX_ROOT: &str = ".harness/.sandboxes/worktrees";
/// The managed root of the worktrees the coding application creates; `worktree.remove` removes
/// from it too, and `worktree.create` refuses it.
const APPLICATION_ROOT: &str = ".claude/worktrees";
/// The longest `git_stderr` fact, in characters.
const MAX_STDERR_CHARS: usize = 2000;

/// The repository of this runtime.
struct Repository {
    /// The root as the state directory spells it; a requester may spell a path with it.
    named: PathBuf,
    /// The canonical root: Git prints the worktrees below it.
    root: PathBuf,
}

/// The repository whose state directory this runtime serves: `state_dir` is its root joined with
/// `state::migrate::STATE_REL`.
fn repository(state_dir: Option<&Path>) -> Result<Repository, ErrorBody> {
    let depth = Path::new(state::migrate::STATE_REL).components().count();
    let Some(named) = state_dir.and_then(|dir| dir.ancestors().nth(depth)) else {
        return Err(ErrorBody::new(
            ErrorCode::InvariantViolation,
            FailureDomain::EnvironmentPreparation,
            false,
            "this runtime serves no state directory, so it knows no repository root",
            "start the runtime with `harness-runtime serve --repo <repo>` of the repository",
        ));
    };
    match canonical(named) {
        Ok(root) => Ok(Repository {
            named: named.to_path_buf(),
            root,
        }),
        Err(err) => Err(ErrorBody::new(
            ErrorCode::InvariantViolation,
            FailureDomain::EnvironmentPreparation,
            false,
            format!(
                "the repository root {} cannot be resolved: {err}",
                named.display()
            ),
            "start the runtime with `harness-runtime serve --repo <repo>` of an existing repository",
        )),
    }
}

/// The values of a payload that is an object with exactly the string fields `fields`.
fn string_fields<'a, const N: usize>(
    operation: &str,
    payload: Option<&'a Value>,
    fields: [&str; N],
) -> Result<[&'a str; N], ErrorBody> {
    let refuse = |detail: String| {
        ErrorBody::malformed(
            detail,
            format!(
                "send {operation} a payload object with exactly the string fields {}",
                fields.join(", ")
            ),
        )
    };
    let Some(Value::Object(members)) = payload else {
        return Err(refuse(format!("{operation} needs a payload object")));
    };
    if let Some(unknown) = members
        .keys()
        .find(|member| !fields.contains(&member.as_str()))
    {
        return Err(refuse(format!("unknown payload field {unknown:?}")));
    }
    let mut values = [""; N];
    for (value, field) in values.iter_mut().zip(fields) {
        match members.get(field).and_then(Value::as_str) {
            // A control character never reaches an argument of Git or a line of its output.
            Some(text) if text.chars().any(char::is_control) => {
                return Err(refuse(format!(
                    "the payload field {field:?} holds a control character"
                )));
            }
            Some(text) => *value = text,
            None => {
                return Err(refuse(format!(
                    "the payload field {field:?} must be a string"
                )));
            }
        }
    }
    Ok(values)
}

/// The path of a managed worktree. `raw` is absolute, has no `..` component, is a strict
/// descendant of one of the managed roots `roots`, and no existing part of it below the
/// repository root is a symbolic link. The containment is lexical; the answer is spelled from the
/// canonical root, the way Git prints a worktree.
fn managed_path(repo: &Repository, raw: &str, roots: &[&str]) -> Result<PathBuf, ErrorBody> {
    let denied = |why: &str| {
        let allowed: Vec<String> = roots
            .iter()
            .map(|managed| repo.root.join(managed).display().to_string())
            .collect();
        ErrorBody::new(
            ErrorCode::PolicyDenied,
            FailureDomain::Policy,
            false,
            format!("the path {raw:?} {why}"),
            format!(
                "name an absolute path below {} without `..` and without symbolic links",
                allowed.join(" or ")
            ),
        )
    };
    let path = Path::new(raw);
    if !path.is_absolute() {
        return Err(denied("is not absolute"));
    }
    if path
        .components()
        .any(|component| component == Component::ParentDir)
    {
        return Err(denied("has a `..` component"));
    }
    let Some(relative) = roots.iter().find_map(|managed| {
        [&repo.named, &repo.root]
            .into_iter()
            .find_map(|root| path.strip_prefix(root.join(managed)).ok())
            .filter(|rest| !rest.as_os_str().is_empty())
            .map(|rest| Path::new(managed).join(rest))
    }) else {
        return Err(denied("is not inside a managed worktree root"));
    };
    let mut walked = repo.root.clone();
    for component in relative.components() {
        walked.push(component);
        match fs::symlink_metadata(&walked) {
            Ok(found) if found.file_type().is_symlink() => {
                return Err(denied(&format!(
                    "crosses the symbolic link {}",
                    walked.display()
                )));
            }
            Ok(_) => {}
            // The rest of the path does not exist yet.
            Err(_) => break,
        }
    }
    Ok(repo.root.join(relative))
}

/// A Git command in the repository. The hooks and the fsmonitor are off, so Git runs no file the
/// sandboxed requester wrote, and the environment of the runtime names no other repository.
fn git(repo: &Repository) -> Command {
    guarded(&repo.root)
}

/// A registered worktree and the administrative directory the main repository keeps for it.
struct Checkout {
    path: PathBuf,
    /// `<git common dir>/worktrees/<id>`: inside the `.git` of the main repository, which the
    /// sandboxed requester cannot write, unlike the gitfile `<path>/.git`.
    git_dir: PathBuf,
}

/// A Git command in the worktree `checkout`, with the guards of `git`. The git directory and the
/// working tree are explicit, so Git never follows the gitfile of the worktree: the requester can
/// rewrite it to name a git directory whose configuration runs a command.
fn git_at(checkout: &Checkout) -> Command {
    let mut command = guarded(&checkout.path);
    let mut git_dir = std::ffi::OsString::from("--git-dir=");
    git_dir.push(&checkout.git_dir);
    let mut work_tree = std::ffi::OsString::from("--work-tree=");
    work_tree.push(&checkout.path);
    command.arg(git_dir).arg(work_tree);
    command
}

/// A Git command in the directory `dir` with the hooks and the fsmonitor off and no Git variable
/// of the environment of the runtime.
fn guarded(dir: &Path) -> Command {
    let mut command = Command::new("git");
    command
        .arg("-C")
        .arg(dir)
        .args([
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.fsmonitor=false",
        ])
        .stdin(Stdio::null());
    for name in [
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_COMMON_DIR",
    ] {
        command.env_remove(name);
    }
    command
}

/// The output of a Git command; an error when Git cannot start.
fn run(mut command: Command) -> Result<Output, ErrorBody> {
    command.output().map_err(|err| {
        ErrorBody::new(
            ErrorCode::Internal,
            FailureDomain::Tooling,
            false,
            format!("git cannot start: {err}"),
            "install git on the PATH of the runtime, then repeat the request",
        )
    })
}

/// The error of a Git command that failed; `message` says what Git did not do.
fn git_failure(message: String, output: &Output) -> ErrorBody {
    let stderr = String::from_utf8_lossy(&output.stderr);
    let stderr: String = stderr.trim().chars().take(MAX_STDERR_CHARS).collect();
    ErrorBody::new(
        ErrorCode::InvariantViolation,
        FailureDomain::Tooling,
        false,
        message,
        "correct what the git_stderr fact names, then repeat the request",
    )
    .with_fact("git_stderr", stderr)
    .with_fact("git_exit_code", output.status.code())
}

/// The trimmed standard output of a Git command that must succeed; `message` says what Git did
/// not do when it fails.
fn checked(command: Command, message: impl FnOnce() -> String) -> Result<String, ErrorBody> {
    let output = run(command)?;
    if output.status.success() {
        Ok(String::from_utf8_lossy(&output.stdout).trim().to_owned())
    } else {
        Err(git_failure(message(), &output))
    }
}

/// One worktree of `git worktree list --porcelain`.
#[derive(Debug, Default)]
struct Listed {
    path: PathBuf,
    head: String,
    /// The full ref of the branch the worktree has checked out; `None` when it is detached.
    branch: Option<String>,
    /// Git found no working tree at the path.
    prunable: bool,
}

/// The worktrees of the repository. An existing path is canonical, so it compares with a
/// `managed_path`.
fn listed(repo: &Repository) -> Result<Vec<Listed>, ErrorBody> {
    let mut command = git(repo);
    command.args(["worktree", "list", "--porcelain"]);
    let text = checked(command, || {
        format!(
            "git could not list the worktrees of {}",
            repo.root.display()
        )
    })?;
    let mut worktrees: Vec<Listed> = Vec::new();
    for line in text.lines() {
        let (key, value) = line.split_once(' ').unwrap_or((line, ""));
        match (key, worktrees.last_mut()) {
            ("worktree", _) => {
                let path = Path::new(value);
                worktrees.push(Listed {
                    path: canonical(path).unwrap_or_else(|_| path.to_path_buf()),
                    ..Listed::default()
                });
            }
            ("HEAD", Some(last)) => value.clone_into(&mut last.head),
            ("branch", Some(last)) => last.branch = Some(value.to_owned()),
            ("prunable", Some(last)) => last.prunable = true,
            _ => {}
        }
    }
    Ok(worktrees)
}

/// The id of the commit `revision` names; `None` when the repository has no such commit.
fn commit_of(repo: &Repository, revision: &str) -> Result<Option<String>, ErrorBody> {
    let mut command = git(repo);
    command
        .args(["rev-parse", "--verify", "--quiet"])
        .arg(format!("{revision}^{{commit}}"));
    let output = run(command)?;
    match output.status.code() {
        Some(0) => Ok(Some(
            String::from_utf8_lossy(&output.stdout).trim().to_owned(),
        )),
        // `--quiet` answers a revision that names no commit with exit code 1 and no message.
        Some(1) => Ok(None),
        _ => Err(git_failure(
            format!("git could not resolve the revision {revision:?}"),
            &output,
        )),
    }
}

/// Refuse a branch that reads as an option or that Git does not accept as a branch name.
fn check_branch(repo: &Repository, branch: &str) -> Result<(), ErrorBody> {
    let refuse = |why: &str| {
        ErrorBody::malformed(
            format!("the branch {branch:?} {why}"),
            "name a branch that `git check-ref-format --branch` accepts and that does not start with `-`",
        )
    };
    if branch.starts_with('-') {
        return Err(refuse("starts with `-`"));
    }
    let mut command = git(repo);
    command.args(["check-ref-format", "--branch", branch]);
    let output = run(command)?;
    // `--branch` also expands `@{-N}` to another branch: a literal name comes back unchanged.
    if !output.status.success() || String::from_utf8_lossy(&output.stdout).trim() != branch {
        return Err(refuse("is not a valid branch name"));
    }
    Ok(())
}

/// The id of the commit the base names. A base never reads as an option.
fn base_commit(repo: &Repository, base: &str) -> Result<String, ErrorBody> {
    if base.starts_with('-') {
        return Err(ErrorBody::malformed(
            format!("the base {base:?} starts with `-`"),
            "name the base as a branch, a tag or a commit id",
        ));
    }
    commit_of(repo, base)?.ok_or_else(|| {
        ErrorBody::new(
            ErrorCode::NotFound,
            FailureDomain::EnvironmentPreparation,
            false,
            format!("the base {base:?} names no commit of the repository"),
            "name an existing branch, tag or commit id as the base, then repeat the request",
        )
    })
}

/// Whether `git worktree add` may create `path`: nothing is there, or an empty directory.
fn vacant(path: &Path) -> bool {
    match fs::symlink_metadata(path) {
        Ok(found) => {
            found.is_dir() && fs::read_dir(path).is_ok_and(|mut entries| entries.next().is_none())
        }
        Err(_) => true,
    }
}

/// A refusal that the state of the repository causes, not a failed Git command.
fn refused(message: String, remedy: &str) -> ErrorBody {
    ErrorBody::new(
        ErrorCode::InvariantViolation,
        FailureDomain::EnvironmentPreparation,
        false,
        message,
        remedy,
    )
}

/// `worktree.create`: a worktree at `path` below `.harness/.sandboxes/worktrees` on the new branch
/// `branch` that starts at the commit `base`. A repeated request answers `"created": false`, and a
/// branch that an interrupted attempt left at the base without a worktree is checked out.
pub(crate) fn create(
    state_dir: Option<&Path>,
    payload: Option<&Value>,
) -> Result<Value, ErrorBody> {
    let [raw_path, branch, base] =
        string_fields("worktree.create", payload, ["path", "branch", "base"])?;
    let repo = repository(state_dir)?;
    let path = managed_path(&repo, raw_path, &[SANDBOX_ROOT])?;
    check_branch(&repo, branch)?;
    let base_sha = base_commit(&repo, base)?;
    let branch_ref = format!("refs/heads/{branch}");
    let answer = |head: &str, created: bool| {
        json!({
            "path": path.to_string_lossy(),
            "branch": branch,
            "head": head,
            "created": created,
        })
    };

    let worktrees = listed(&repo)?;
    let mut holders = worktrees
        .iter()
        .filter(|worktree| worktree.branch.as_deref() == Some(branch_ref.as_str()));
    // A repeated request: the worktree is already there on its branch.
    if let Some(found) = holders
        .clone()
        .find(|found| found.path == path && !found.prunable)
    {
        return Ok(answer(&found.head, false));
    }
    if !vacant(&path) {
        return Err(refused(
            format!(
                "the path {} exists and is not an empty directory",
                path.display()
            ),
            "name a path that does not exist yet, or empty the directory, then repeat the request",
        ));
    }
    let mut add = git(&repo);
    add.args(["worktree", "add"]);
    match (commit_of(&repo, &branch_ref)?, holders.next()) {
        (None, _) => {
            add.args(["--no-track", "-b", branch])
                .arg(&path)
                .arg(&base_sha);
        }
        // An earlier attempt created the branch and stopped before the worktree.
        (Some(tip), None) if tip == base_sha => {
            add.arg(&path).arg(branch);
        }
        (Some(tip), None) => {
            return Err(refused(
                format!(
                    "the branch {branch:?} exists at another commit, {tip}, than the base {base_sha}"
                ),
                "name a new branch, or the base the branch points to, then repeat the request",
            )
            .with_fact("branch_head", tip));
        }
        (Some(tip), Some(holder)) => {
            return Err(refused(
                format!(
                    "the branch {branch:?} exists and is checked out elsewhere, in the worktree {}",
                    holder.path.display()
                ),
                "name a new branch, or remove the worktree that holds the branch, then repeat the request",
            )
            .with_fact("branch_head", tip));
        }
    }
    checked(add, || {
        format!(
            "git could not create the worktree {} on the branch {branch:?}",
            path.display()
        )
    })?;
    Ok(answer(&base_sha, true))
}

/// `worktree.remove`: remove the worktree at `path` below a managed root and keep its branch.
/// Nothing forces the removal: Git refuses a dirty or locked worktree, and so does this operation.
pub(crate) fn remove(
    state_dir: Option<&Path>,
    payload: Option<&Value>,
) -> Result<Value, ErrorBody> {
    let [raw_path] = string_fields("worktree.remove", payload, ["path"])?;
    let repo = repository(state_dir)?;
    let path = managed_path(&repo, raw_path, &[SANDBOX_ROOT, APPLICATION_ROOT])?;
    if !listed(&repo)?.iter().any(|worktree| worktree.path == path) {
        return Err(ErrorBody::new(
            ErrorCode::NotFound,
            FailureDomain::EnvironmentPreparation,
            false,
            format!("the repository has no worktree at {}", path.display()),
            "name the path of a worktree that `git worktree list` shows",
        ));
    }
    let mut command = git(&repo);
    command.args(["worktree", "remove"]).arg(&path);
    checked(command, || {
        format!("git refused to remove the worktree {}", path.display())
    })?;
    Ok(json!({"path": path.to_string_lossy(), "removed": true}))
}

/// The worktree at `raw` below a managed root that `git worktree list` shows, with the
/// administrative directory the main repository keeps for it.
fn registered(repo: &Repository, raw: &str) -> Result<(Checkout, Listed), ErrorBody> {
    let path = managed_path(repo, raw, &[SANDBOX_ROOT, APPLICATION_ROOT])?;
    let Some(worktree) = listed(repo)?
        .into_iter()
        .find(|worktree| worktree.path == path && !worktree.prunable)
    else {
        return Err(ErrorBody::new(
            ErrorCode::NotFound,
            FailureDomain::EnvironmentPreparation,
            false,
            format!("the repository has no worktree at {}", path.display()),
            "name the path of a worktree that `git worktree list` shows",
        ));
    };
    let git_dir = admin_dir(repo, &path)?;
    Ok((Checkout { path, git_dir }, worktree))
}

/// The administrative directory of the worktree at `path`: the entry
/// `<git common dir>/worktrees/<id>` whose `gitdir` file names `<path>/.git`. Only the metadata of
/// the main repository is read, never the gitfile in the worktree.
fn admin_dir(repo: &Repository, path: &Path) -> Result<PathBuf, ErrorBody> {
    let mut command = git(repo);
    command.args(["rev-parse", "--path-format=absolute", "--git-common-dir"]);
    let common = checked(command, || {
        format!(
            "git could not name the git directory of {}",
            repo.root.display()
        )
    })?;
    let entries = fs::read_dir(Path::new(&common).join("worktrees"));
    for entry in entries.into_iter().flatten().flatten() {
        let Ok(text) = fs::read_to_string(entry.path().join("gitdir")) else {
            continue;
        };
        let named = Path::new(text.trim_end_matches(['\n', '\r']));
        let names_path = named.file_name() == Some(".git".as_ref())
            && named
                .parent()
                .and_then(|dir| canonical(dir).ok())
                .is_some_and(|dir| dir == path);
        if names_path {
            return Ok(entry.path());
        }
    }
    Err(ErrorBody::new(
        ErrorCode::PolicyDenied,
        FailureDomain::Policy,
        false,
        format!(
            "the git directory of {} keeps no administrative directory for the worktree {}",
            repo.root.display(),
            path.display()
        ),
        "name the path of a worktree that `git worktree add` registered in the repository",
    ))
}

/// The short name of the branch the worktree at `path` has checked out; a detached HEAD is refused.
fn checked_out(path: &Path, worktree: &Listed) -> Result<String, ErrorBody> {
    let Some(branch_ref) = &worktree.branch else {
        return Err(refused(
            format!("the worktree {} has a detached HEAD", path.display()),
            "check out the issue branch in the worktree, then repeat the request",
        ));
    };
    Ok(branch_ref
        .strip_prefix("refs/heads/")
        .unwrap_or(branch_ref)
        .to_owned())
}

/// The project configuration the branch policy reads, relative to the repository root.
const PROJECT_FILE: &str = ".harness/project.json";

/// Refuse a branch that no worktree operation may change: an `integration/*` branch or the base
/// branch of the project, `base_branch` of `.harness/project.json`, or `master` and `main` when
/// the file or the field is missing. The client checks the same, but a requester can call the
/// operation directly. `branch_pattern` is not checked: the runtime has no regular expressions.
fn check_policy(repo: &Repository, path: &Path, branch: &str) -> Result<(), ErrorBody> {
    let denied = |why: String| {
        ErrorBody::new(
            ErrorCode::PolicyDenied,
            FailureDomain::Policy,
            false,
            why,
            "check out an issue branch in the worktree, never the base or an integration/* branch",
        )
    };
    let file = repo.root.join(PROJECT_FILE);
    let project = match fs::read_to_string(&file) {
        Ok(text) => Some(serde_json::from_str::<Value>(&text).map_err(|err| {
            denied(format!(
                "the project configuration {} is not JSON: {err}",
                file.display()
            ))
        })?),
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => None,
        Err(err) => {
            return Err(denied(format!(
                "the project configuration {} cannot be read: {err}",
                file.display()
            )));
        }
    };
    let bases = match project.as_ref().and_then(|found| found.get("base_branch")) {
        None => vec!["master", "main"],
        Some(Value::String(base)) if !base.is_empty() => vec![base.as_str()],
        Some(_) => {
            return Err(denied(format!(
                "the base_branch of the project configuration {} is not a non-empty string",
                file.display()
            )));
        }
    };
    if branch.starts_with("integration/") || bases.contains(&branch) {
        return Err(denied(format!(
            "the worktree {} has the protected branch {branch:?} checked out",
            path.display()
        )));
    }
    Ok(())
}

/// The longest commit message `worktree.commit` accepts, in bytes.
const MAX_MESSAGE_BYTES: usize = 64 * 1024;

/// A `worktree.commit` payload.
struct CommitRequest<'a> {
    path: &'a str,
    message: &'a str,
    /// The paths to stage, each read literally; `None` stages every change of the worktree.
    pathspecs: Option<Vec<&'a str>>,
}

/// The fields of a `worktree.commit` payload: the string fields `path` and `message` and the
/// optional non-empty array of strings `pathspecs`.
fn commit_request(payload: Option<&Value>) -> Result<CommitRequest<'_>, ErrorBody> {
    let refuse = |detail: String| {
        ErrorBody::malformed(
            detail,
            "send worktree.commit a payload object with the string fields path and message and, \
             optionally, pathspecs: a non-empty array of strings",
        )
    };
    let Some(Value::Object(members)) = payload else {
        return Err(refuse("worktree.commit needs a payload object".to_owned()));
    };
    if let Some(unknown) = members
        .keys()
        .find(|member| !["path", "message", "pathspecs"].contains(&member.as_str()))
    {
        return Err(refuse(format!("unknown payload field {unknown:?}")));
    }
    let text = |field: &str| {
        members
            .get(field)
            .and_then(Value::as_str)
            .ok_or_else(|| refuse(format!("the payload field {field:?} must be a string")))
    };
    let path = text("path")?;
    if path.chars().any(char::is_control) {
        return Err(refuse(
            "the payload field \"path\" holds a control character".to_owned(),
        ));
    }
    let message = text("message")?;
    if message.trim().is_empty() {
        return Err(refuse("the commit message is empty".to_owned()));
    }
    if message.len() > MAX_MESSAGE_BYTES {
        return Err(refuse(format!(
            "the commit message is longer than {MAX_MESSAGE_BYTES} bytes"
        )));
    }
    // A line break and a tab belong to a commit message; no other control character does.
    if message
        .chars()
        .any(|found| found.is_control() && found != '\n' && found != '\t')
    {
        return Err(refuse(
            "the commit message holds a control character other than a line break or a tab"
                .to_owned(),
        ));
    }
    let pathspecs = match members.get("pathspecs") {
        None => None,
        Some(Value::Array(items)) if !items.is_empty() => Some(
            items
                .iter()
                .map(|item| match item.as_str() {
                    Some(spec) if !spec.is_empty() && !spec.chars().any(char::is_control) => {
                        Ok(spec)
                    }
                    _ => Err(refuse(
                        "every pathspec must be a non-empty string without a control character"
                            .to_owned(),
                    )),
                })
                .collect::<Result<Vec<_>, _>>()?,
        ),
        Some(_) => {
            return Err(refuse(
                "the payload field \"pathspecs\" must be a non-empty array of strings".to_owned(),
            ));
        }
    };
    for spec in pathspecs.iter().flatten() {
        // Not `is_absolute()`: on Windows a rooted path without a drive ("/etc/passwd") and a
        // drive-relative one ("C:x") are both relative to it, and both leave the worktree.
        if Path::new(spec)
            .components()
            .any(|component| !matches!(component, Component::Normal(_) | Component::CurDir))
        {
            return Err(ErrorBody::new(
                ErrorCode::PolicyDenied,
                FailureDomain::Policy,
                false,
                format!("the pathspec {spec:?} is not inside the worktree"),
                "name paths relative to the worktree root, without `..`",
            ));
        }
    }
    Ok(CommitRequest {
        path,
        message,
        pathspecs,
    })
}

/// The output of `command` fed `input` on its standard input; an error when Git cannot start.
fn run_with_input(mut command: Command, input: &[u8]) -> Result<Output, ErrorBody> {
    use std::io::Write;

    let cannot_start = |err: std::io::Error| {
        ErrorBody::new(
            ErrorCode::Internal,
            FailureDomain::Tooling,
            false,
            format!("git cannot start: {err}"),
            "install git on the PATH of the runtime, then repeat the request",
        )
    };
    let mut child = command
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(cannot_start)?;
    if let Some(mut stdin) = child.stdin.take() {
        // Git reads the whole message before it writes anything, so the write cannot block on a
        // full output pipe. A write error means Git stopped early; its exit status says why.
        let _ = stdin.write_all(input);
    }
    child.wait_with_output().map_err(cannot_start)
}

/// `worktree.commit`: stage the changes of the worktree at `path` below a managed root, all of
/// them or the paths `pathspecs` names, and commit the index on the branch the worktree has
/// checked out. Git takes the author from its own configuration; the hooks and the fsmonitor are
/// off, and the message reaches Git on its standard input, never as an argument.
pub(crate) fn commit(
    state_dir: Option<&Path>,
    payload: Option<&Value>,
) -> Result<Value, ErrorBody> {
    let request = commit_request(payload)?;
    let repo = repository(state_dir)?;
    let (checkout, worktree) = registered(&repo, request.path)?;
    let path = &checkout.path;
    if let Some(kind) = underway(&checkout)? {
        return Err(refused(
            format!(
                "a {} is stopped in the worktree {}",
                kind.name(),
                path.display()
            ),
            "finish it with its own continue action, which commits the resolution, or abort it",
        ));
    }
    let branch = checked_out(path, &worktree)?;
    check_policy(&repo, path, &branch)?;

    let mut add = git_at(&checkout);
    add.args(["add", "--all", "--"]);
    for spec in request.pathspecs.iter().flatten() {
        add.arg(format!(":(literal){spec}"));
    }
    checked(add, || {
        format!(
            "git could not stage the changes of the worktree {}",
            path.display()
        )
    })?;
    let mut staged = git_at(&checkout);
    staged.args(["diff", "--cached", "--quiet"]);
    let output = run(staged)?;
    match output.status.code() {
        Some(1) => {}
        Some(0) => {
            return Err(refused(
                format!("the worktree {} has no change to commit", path.display()),
                "change a file of the worktree, or name the changed paths, then repeat the request",
            ));
        }
        _ => {
            return Err(git_failure(
                format!(
                    "git could not compare the index of the worktree {}",
                    path.display()
                ),
                &output,
            ));
        }
    }
    let mut command = git_at(&checkout);
    command.args(["commit", "--quiet", "--no-verify", "--file=-"]);
    let output = run_with_input(command, request.message.as_bytes())?;
    if !output.status.success() {
        return Err(git_failure(
            format!(
                "git could not commit in the worktree {} on the branch {branch:?}",
                path.display()
            ),
            &output,
        ));
    }
    let mut head = git_at(&checkout);
    head.args(["rev-parse", "HEAD"]);
    let head = checked(head, || {
        format!(
            "git could not read the new commit of the worktree {}",
            path.display()
        )
    })?;
    Ok(json!({
        "path": path.to_string_lossy(),
        "branch": branch,
        "head": head,
        "committed": true,
    }))
}

/// A Git operation that stops on a conflict and is finished by later requests.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Underway {
    Rebase,
    Merge,
}

impl Underway {
    fn name(self) -> &'static str {
        match self {
            Self::Rebase => "rebase",
            Self::Merge => "merge",
        }
    }
}

/// The string fields of a payload object, each named in `allowed`. No value holds a control
/// character, so none reaches an argument of Git or a line of its output.
fn text_fields<'a>(
    operation: &str,
    payload: Option<&'a Value>,
    allowed: &[&str],
) -> Result<BTreeMap<&'a str, &'a str>, ErrorBody> {
    let refuse = |detail: String| {
        ErrorBody::malformed(
            detail,
            format!(
                "send {operation} a payload object whose fields are strings among {}",
                allowed.join(", ")
            ),
        )
    };
    let Some(Value::Object(members)) = payload else {
        return Err(refuse(format!("{operation} needs a payload object")));
    };
    let mut fields = BTreeMap::new();
    for (name, value) in members {
        if !allowed.contains(&name.as_str()) {
            return Err(refuse(format!("unknown payload field {name:?}")));
        }
        match value.as_str() {
            Some(text) if text.chars().any(char::is_control) => {
                return Err(refuse(format!(
                    "the payload field {name:?} holds a control character"
                )));
            }
            Some(text) => {
                fields.insert(name.as_str(), text);
            }
            None => {
                return Err(refuse(format!(
                    "the payload field {name:?} must be a string"
                )));
            }
        }
    }
    Ok(fields)
}

/// The fields `path` and `action` of a payload of `operation`.
fn path_and_action<'a>(
    operation: &str,
    fields: &BTreeMap<&'a str, &'a str>,
) -> Result<(&'a str, &'a str), ErrorBody> {
    let field = |name: &str| {
        fields.get(name).copied().ok_or_else(|| {
            ErrorBody::malformed(
                format!("{operation} needs the string field {name:?}"),
                format!("send {operation} a payload object with the fields path and action"),
            )
        })
    };
    Ok((field("path")?, field("action")?))
}

/// The fields an action of `operation` takes: each of `needed` is present and no other field
/// of `optional` beside them.
fn action_fields<'a, const N: usize>(
    operation: &str,
    action: &str,
    fields: &BTreeMap<&'a str, &'a str>,
    needed: [&str; N],
    optional: &[&str],
) -> Result<[&'a str; N], ErrorBody> {
    let refuse = |detail: String| {
        ErrorBody::malformed(
            detail,
            format!(
                "the action {action:?} of {operation} takes path and action{}{}",
                needed
                    .iter()
                    .map(|name| format!(", {name}"))
                    .collect::<String>(),
                optional
                    .iter()
                    .map(|name| format!(", optionally {name}"))
                    .collect::<String>()
            ),
        )
    };
    if let Some(extra) = fields.keys().find(|name| {
        !["path", "action"].contains(name) && !needed.contains(name) && !optional.contains(name)
    }) {
        return Err(refuse(format!(
            "the action {action:?} takes no field {extra:?}"
        )));
    }
    let mut values = [""; N];
    for (value, name) in values.iter_mut().zip(needed) {
        *value = fields
            .get(name)
            .copied()
            .ok_or_else(|| refuse(format!("the action {action:?} needs the field {name:?}")))?;
    }
    Ok(values)
}

/// The id of the commit `revision` names in the worktree at `path`; `field` names it in errors.
/// A revision never reads as an option.
fn worktree_commit_of(
    checkout: &Checkout,
    field: &str,
    revision: &str,
) -> Result<String, ErrorBody> {
    if revision.starts_with('-') {
        return Err(ErrorBody::malformed(
            format!("the {field} {revision:?} starts with `-`"),
            format!("name the {field} as a branch, a tag or a commit id"),
        ));
    }
    let mut command = git_at(checkout);
    command
        .args(["rev-parse", "--verify", "--quiet"])
        .arg(format!("{revision}^{{commit}}"));
    let output = run(command)?;
    match output.status.code() {
        Some(0) => Ok(String::from_utf8_lossy(&output.stdout).trim().to_owned()),
        Some(1) => Err(ErrorBody::new(
            ErrorCode::NotFound,
            FailureDomain::EnvironmentPreparation,
            false,
            format!("the {field} {revision:?} names no commit of the repository"),
            format!(
                "name an existing branch, tag or commit id as the {field}, then repeat the request"
            ),
        )),
        _ => Err(git_failure(
            format!("git could not resolve the {field} {revision:?}"),
            &output,
        )),
    }
}

/// The operation that is stopped in the worktree at `path`, if any.
fn underway(checkout: &Checkout) -> Result<Option<Underway>, ErrorBody> {
    let path = &checkout.path;
    for (name, kind) in [
        ("rebase-merge", Underway::Rebase),
        ("rebase-apply", Underway::Rebase),
        ("MERGE_HEAD", Underway::Merge),
    ] {
        let mut command = git_at(checkout);
        command.args(["rev-parse", "--path-format=absolute", "--git-path", name]);
        let found = checked(command, || {
            format!(
                "git could not name the {name} file of the worktree {}",
                path.display()
            )
        })?;
        if Path::new(&found).exists() {
            return Ok(Some(kind));
        }
    }
    Ok(None)
}

/// A Git command in the worktree that may stop for a resolution: no editor ever opens, and the
/// message Git prepared is kept.
fn resumable(checkout: &Checkout) -> Command {
    let mut command = git_at(checkout);
    command.env("GIT_EDITOR", ":");
    command
}

/// The answer after `output` of a step of `kind` in the worktree at `path`. A step that stopped
/// with the operation still underway is an answer with `in_progress: true`, the unmerged paths in
/// `conflicts` and what Git printed in `git_output`; a step that failed otherwise is an error.
fn step_answer(
    checkout: &Checkout,
    kind: Underway,
    output: &Output,
    failed: impl FnOnce() -> String,
) -> Result<Value, ErrorBody> {
    let path = &checkout.path;
    let in_progress = underway(checkout)? == Some(kind);
    if !output.status.success() && !in_progress {
        return Err(git_failure(failed(), output));
    }
    let mut unmerged = git_at(checkout);
    unmerged.args(["diff", "--name-only", "--diff-filter=U", "-z"]);
    let unmerged = checked(unmerged, || {
        format!(
            "git could not list the conflicts of the worktree {}",
            path.display()
        )
    })?;
    let conflicts: Vec<&str> = unmerged
        .split('\0')
        .filter(|name| !name.is_empty())
        .collect();
    let mut head = git_at(checkout);
    head.args(["rev-parse", "HEAD"]);
    let head = checked(head, || {
        format!("git could not read HEAD of the worktree {}", path.display())
    })?;
    let mut branch = git_at(checkout);
    branch.args(["symbolic-ref", "--quiet", "--short", "HEAD"]);
    let branch = run(branch)?;
    let branch = branch
        .status
        .success()
        .then(|| String::from_utf8_lossy(&branch.stdout).trim().to_owned());
    let printed = if in_progress {
        let text = format!(
            "{}\n{}",
            String::from_utf8_lossy(&output.stdout).trim(),
            String::from_utf8_lossy(&output.stderr).trim()
        );
        Some(
            text.trim()
                .chars()
                .take(MAX_STDERR_CHARS)
                .collect::<String>(),
        )
    } else {
        None
    };
    Ok(json!({
        "path": path.to_string_lossy(),
        "branch": branch,
        "head": head,
        "in_progress": in_progress,
        "conflicts": conflicts,
        "git_output": printed,
    }))
}

/// Refuse to start `kind` while an operation is stopped, or to resume `kind` when it is not.
fn expect_underway(checkout: &Checkout, kind: Underway, starting: bool) -> Result<(), ErrorBody> {
    let path = &checkout.path;
    let found = underway(checkout)?;
    match (starting, found) {
        (true, None) => Ok(()),
        (true, Some(other)) => Err(refused(
            format!(
                "a {} is stopped in the worktree {}",
                other.name(),
                path.display()
            ),
            "continue or abort the stopped operation first, then repeat the request",
        )),
        (false, Some(other)) if other == kind => Ok(()),
        (false, _) => Err(refused(
            format!(
                "no {} is stopped in the worktree {}",
                kind.name(),
                path.display()
            ),
            "start the operation first, or send the action of the operation that is stopped",
        )),
    }
}

/// Stage every change of the worktree at `path`: the resolutions of a stopped operation.
fn stage_all(checkout: &Checkout) -> Result<(), ErrorBody> {
    let path = &checkout.path;
    let mut add = git_at(checkout);
    add.args(["add", "--all"]);
    checked(add, || {
        format!(
            "git could not stage the changes of the worktree {}",
            path.display()
        )
    })
    .map(drop)
}

/// `worktree.rebase`: `start` rebases the branch of the worktree at `path`, the commits above
/// `upstream`, onto `onto`; `continue` stages the resolutions and goes on, `skip` drops the commit
/// that stopped, and `abort` restores the branch. Autostash and the update of other branches are
/// off, so the rebase changes only this worktree and its branch.
pub(crate) fn rebase(
    state_dir: Option<&Path>,
    payload: Option<&Value>,
) -> Result<Value, ErrorBody> {
    const OPERATION: &str = "worktree.rebase";
    let fields = text_fields(OPERATION, payload, &["path", "action", "onto", "upstream"])?;
    let (raw_path, action) = path_and_action(OPERATION, &fields)?;
    let repo = repository(state_dir)?;
    let (checkout, worktree) = registered(&repo, raw_path)?;
    let path = &checkout.path;
    let mut command = resumable(&checkout);
    command.arg("rebase");
    match action {
        "start" => {
            let [onto, upstream] =
                action_fields(OPERATION, action, &fields, ["onto", "upstream"], &[])?;
            let branch = checked_out(path, &worktree)?;
            check_policy(&repo, path, &branch)?;
            expect_underway(&checkout, Underway::Rebase, true)?;
            let onto = worktree_commit_of(&checkout, "onto", onto)?;
            let upstream = worktree_commit_of(&checkout, "upstream", upstream)?;
            command
                .args(["--no-autostash", "--no-update-refs", "--onto"])
                .arg(onto)
                .arg(upstream);
        }
        "continue" | "skip" | "abort" => {
            action_fields(OPERATION, action, &fields, [], &[])?;
            expect_underway(&checkout, Underway::Rebase, false)?;
            if action == "continue" {
                stage_all(&checkout)?;
            }
            command.arg(format!("--{action}"));
        }
        _ => {
            return Err(ErrorBody::malformed(
                format!("{OPERATION} has no action {action:?}"),
                "send one of the actions start, continue, skip and abort",
            ));
        }
    }
    let output = run(command)?;
    step_answer(&checkout, Underway::Rebase, &output, || {
        format!(
            "git could not {action} the rebase in the worktree {}",
            path.display()
        )
    })
}

/// `worktree.merge`: `start` merges the commit `revision` into the branch of the worktree at
/// `path`, with Git's message or with `message`; `continue` stages the resolutions and commits
/// the merge, and `abort` restores the branch. Autostash is off.
pub(crate) fn merge(state_dir: Option<&Path>, payload: Option<&Value>) -> Result<Value, ErrorBody> {
    const OPERATION: &str = "worktree.merge";
    let fields = text_fields(
        OPERATION,
        payload,
        &["path", "action", "revision", "message"],
    )?;
    let (raw_path, action) = path_and_action(OPERATION, &fields)?;
    let repo = repository(state_dir)?;
    let (checkout, worktree) = registered(&repo, raw_path)?;
    let path = &checkout.path;
    let mut command = resumable(&checkout);
    command.arg("merge");
    match action {
        "start" => {
            let [revision] = action_fields(OPERATION, action, &fields, ["revision"], &["message"])?;
            let branch = checked_out(path, &worktree)?;
            check_policy(&repo, path, &branch)?;
            expect_underway(&checkout, Underway::Merge, true)?;
            let revision = worktree_commit_of(&checkout, "revision", revision)?;
            command.args(["--no-edit", "--no-autostash"]);
            if let Some(message) = fields.get("message") {
                if message.trim().is_empty() {
                    return Err(ErrorBody::malformed(
                        "the merge message is empty",
                        "send a non-empty message, or omit it for Git's message",
                    ));
                }
                command.arg("-m").arg(message);
            }
            command.arg(revision);
        }
        "continue" | "abort" => {
            action_fields(OPERATION, action, &fields, [], &[])?;
            expect_underway(&checkout, Underway::Merge, false)?;
            if action == "continue" {
                stage_all(&checkout)?;
            }
            command.arg(format!("--{action}"));
        }
        _ => {
            return Err(ErrorBody::malformed(
                format!("{OPERATION} has no action {action:?}"),
                "send one of the actions start, continue and abort",
            ));
        }
    }
    let output = run(command)?;
    step_answer(&checkout, Underway::Merge, &output, || {
        format!(
            "git could not {action} the merge in the worktree {}",
            path.display()
        )
    })
}

#[cfg(test)]
mod tests {
    use std::sync::atomic::{AtomicUsize, Ordering};

    use super::*;

    /// Run Git in `dir` as a test author; the trimmed standard output.
    fn git_in(dir: &Path, args: &[&str]) -> String {
        let output = Command::new("git")
            .arg("-C")
            .arg(dir)
            .args([
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "core.hooksPath=/dev/null",
            ])
            .args(args)
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "git {args:?}: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        String::from_utf8_lossy(&output.stdout).trim().to_owned()
    }

    /// A scratch Git repository with one commit on `main`, and the state directory of a runtime
    /// that serves it.
    struct Scratch {
        base: PathBuf,
        root: PathBuf,
        state_dir: PathBuf,
    }

    impl Scratch {
        fn new(name: &str) -> Self {
            static NEXT: AtomicUsize = AtomicUsize::new(0);
            let n = NEXT.fetch_add(1, Ordering::Relaxed);
            let base =
                std::env::temp_dir().join(format!("hr-worktree-{name}-{}-{n}", std::process::id()));
            let _ = fs::remove_dir_all(&base);
            fs::create_dir_all(base.join("repo")).unwrap();
            let base = canonical(&base).unwrap();
            let root = base.join("repo");
            git_in(&root, &["init", "--quiet", "--initial-branch=main"]);
            let scratch = Self {
                state_dir: root.join(state::migrate::STATE_REL),
                base,
                root,
            };
            scratch.commit("one");
            scratch
        }

        /// One more commit on the branch of the main checkout; its id.
        fn commit(&self, text: &str) -> String {
            fs::write(self.root.join("README"), text).unwrap();
            git_in(&self.root, &["add", "README"]);
            git_in(&self.root, &["commit", "--quiet", "-m", text]);
            git_in(&self.root, &["rev-parse", "HEAD"])
        }

        /// A path below the managed root of `worktree.create`.
        fn managed(&self, name: &str) -> PathBuf {
            self.root.join(SANDBOX_ROOT).join(name)
        }

        fn create(&self, path: &Path, branch: &str, base: &str) -> Result<Value, ErrorBody> {
            create(
                Some(&self.state_dir),
                Some(&json!({"path": path, "branch": branch, "base": base})),
            )
        }

        fn remove(&self, path: &Path) -> Result<Value, ErrorBody> {
            remove(Some(&self.state_dir), Some(&json!({"path": path})))
        }

        /// A managed worktree on a new branch, and a repository identity that its commits use.
        fn worktree(&self, name: &str) -> PathBuf {
            self.worktree_on(name, &format!("feature/{name}"))
        }

        /// A managed worktree on the new branch `branch`, and a repository identity.
        fn worktree_on(&self, name: &str, branch: &str) -> PathBuf {
            for setting in [
                ["user.name", "Test"],
                ["user.email", "test@example.invalid"],
                ["commit.gpgsign", "false"],
            ] {
                git_in(&self.root, &["config", setting[0], setting[1]]);
            }
            let path = self.managed(name);
            self.create(&path, branch, "main").unwrap();
            path
        }

        fn commit_in(&self, payload: &Value) -> Result<Value, ErrorBody> {
            commit(Some(&self.state_dir), Some(payload))
        }

        fn rebase_in(&self, payload: &Value) -> Result<Value, ErrorBody> {
            rebase(Some(&self.state_dir), Some(payload))
        }

        fn merge_in(&self, payload: &Value) -> Result<Value, ErrorBody> {
            merge(Some(&self.state_dir), Some(payload))
        }

        /// A worktree whose branch changes `README` to `ours` while `main` changes it to
        /// `theirs`, and the base both start from.
        fn diverged(&self, name: &str, ours: &str, theirs: &str) -> (PathBuf, String) {
            let path = self.worktree(name);
            let base = git_in(&path, &["rev-parse", "HEAD"]);
            fs::write(path.join("README"), ours).unwrap();
            git_in(&path, &["commit", "--quiet", "-am", "feat: ours"]);
            self.commit(theirs);
            (path, base)
        }

        fn branch_exists(&self, branch: &str) -> bool {
            Command::new("git")
                .arg("-C")
                .arg(&self.root)
                .args(["show-ref", "--verify", "--quiet"])
                .arg(format!("refs/heads/{branch}"))
                .status()
                .unwrap()
                .success()
        }
    }

    fn code(result: Result<Value, ErrorBody>) -> ErrorCode {
        result.unwrap_err().code
    }

    #[test]
    fn create_makes_the_worktree_on_a_new_branch_at_the_base() {
        let repo = Scratch::new("create");
        let base = repo.commit("two");
        let path = repo.managed("issue-1");

        let result = repo.create(&path, "feature/issue-1", "main").unwrap();

        assert_eq!(Path::new(result["path"].as_str().unwrap()), path);
        assert_eq!(result["branch"], "feature/issue-1");
        assert_eq!(result["head"], base.as_str());
        assert_eq!(result["created"], true);
        assert_eq!(base.len(), 40);
        assert_eq!(
            git_in(&repo.root, &["rev-parse", "refs/heads/feature/issue-1"]),
            base
        );
        assert_eq!(
            git_in(&path, &["symbolic-ref", "HEAD"]),
            "refs/heads/feature/issue-1"
        );
        assert_eq!(fs::read_to_string(path.join("README")).unwrap(), "two");
    }

    #[test]
    fn create_starts_the_branch_at_a_base_that_is_not_the_checked_out_commit() {
        let repo = Scratch::new("create-older");
        let first = git_in(&repo.root, &["rev-parse", "HEAD"]);
        repo.commit("two");
        let path = repo.managed("issue-1");

        let result = repo.create(&path, "feature/issue-1", &first).unwrap();

        assert_eq!(result["head"], first.as_str());
        assert_eq!(git_in(&path, &["rev-parse", "HEAD"]), first);
    }

    #[test]
    fn a_repeated_create_answers_created_false() {
        let repo = Scratch::new("repeat");
        let path = repo.managed("issue-1");
        let first = repo.create(&path, "feature/issue-1", "main").unwrap();

        let again = repo.create(&path, "feature/issue-1", "main").unwrap();

        assert_eq!(again["created"], false);
        assert_eq!(again["path"], first["path"]);
        assert_eq!(again["branch"], "feature/issue-1");
        assert_eq!(again["head"], first["head"]);
    }

    #[test]
    fn create_recovers_a_branch_at_the_base_without_a_worktree() {
        let repo = Scratch::new("recover");
        git_in(&repo.root, &["branch", "feature/issue-1", "main"]);
        let path = repo.managed("issue-1");

        let result = repo.create(&path, "feature/issue-1", "main").unwrap();

        assert_eq!(result["created"], true);
        assert_eq!(
            result["head"],
            git_in(&repo.root, &["rev-parse", "main"]).as_str()
        );
        assert_eq!(
            git_in(&path, &["symbolic-ref", "HEAD"]),
            "refs/heads/feature/issue-1"
        );
    }

    #[test]
    fn create_refuses_a_path_outside_its_managed_root() {
        let repo = Scratch::new("outside");
        let outside = [
            repo.base.join("elsewhere"),
            repo.root.join("elsewhere"),
            repo.root.join(SANDBOX_ROOT),
            repo.root
                .join(".harness/.sandboxes/worktrees-other/issue-1"),
            repo.managed("../issue-1"),
            repo.managed("issue-1/../../../../escaped"),
            repo.root.join(APPLICATION_ROOT).join("issue-1"),
            PathBuf::from(SANDBOX_ROOT).join("issue-1"),
        ];

        for path in outside {
            let error = repo
                .create(&path, "feature/issue-1", "main")
                .expect_err(&path.display().to_string());
            assert_eq!(error.code, ErrorCode::PolicyDenied, "{}", path.display());
            assert_eq!(error.domain, FailureDomain::Policy);
        }
        assert!(!repo.branch_exists("feature/issue-1"));
        assert!(!repo.base.join("elsewhere").exists());
        assert!(!repo.root.join("escaped").exists());
    }

    #[cfg(unix)]
    #[test]
    fn create_refuses_a_path_that_crosses_a_symbolic_link() {
        let repo = Scratch::new("symlink");
        let outside = repo.base.join("outside");
        fs::create_dir_all(&outside).unwrap();
        fs::create_dir_all(repo.root.join(SANDBOX_ROOT)).unwrap();
        std::os::unix::fs::symlink(&outside, repo.managed("link")).unwrap();

        let below = repo.create(&repo.managed("link/issue-1"), "feature/issue-1", "main");
        let itself = repo.create(&repo.managed("link"), "feature/issue-1", "main");

        assert_eq!(code(below), ErrorCode::PolicyDenied);
        assert_eq!(code(itself), ErrorCode::PolicyDenied);
        assert_eq!(fs::read_dir(&outside).unwrap().count(), 0);
        assert!(!repo.branch_exists("feature/issue-1"));
    }

    #[test]
    fn create_refuses_a_branch_or_a_base_that_reads_as_an_option() {
        let repo = Scratch::new("options");
        let path = repo.managed("issue-1");

        let branch = repo.create(&path, "--detach", "main");
        let base = repo.create(&path, "feature/issue-1", "--orphan");

        assert_eq!(code(branch), ErrorCode::MalformedRequest);
        assert_eq!(code(base), ErrorCode::MalformedRequest);
        assert!(!path.exists());
        assert!(!repo.branch_exists("feature/issue-1"));
    }

    #[test]
    fn create_refuses_a_name_that_is_no_literal_branch() {
        let repo = Scratch::new("branch-name");
        let path = repo.managed("issue-1");

        for branch in ["", "a..b", "with space", "@{-1}", "ends.lock"] {
            let refused = repo.create(&path, branch, "main");
            assert_eq!(code(refused), ErrorCode::MalformedRequest, "{branch:?}");
        }
        assert!(!path.exists());
    }

    #[test]
    fn create_answers_not_found_for_an_unknown_base() {
        let repo = Scratch::new("unknown-base");
        let path = repo.managed("issue-1");

        let error = repo
            .create(&path, "feature/issue-1", "no-such-base")
            .unwrap_err();

        assert_eq!(error.code, ErrorCode::NotFound);
        assert!(error.message.contains("no-such-base"), "{}", error.message);
        assert!(!path.exists());
        assert!(!repo.branch_exists("feature/issue-1"));
    }

    #[test]
    fn create_refuses_a_payload_it_does_not_define() {
        let repo = Scratch::new("payload");
        let path = repo.managed("issue-1");
        let payloads = [
            json!({"path": path, "branch": "feature/issue-1", "base": "main", "force": true}),
            json!({"path": path, "branch": "feature/issue-1"}),
            json!({"path": path, "branch": 1, "base": "main"}),
            json!({"path": path, "branch": "feature/issue-1", "base": "main\n--force"}),
            json!([path, "feature/issue-1", "main"]),
        ];

        for payload in payloads {
            let refused = create(Some(&repo.state_dir), Some(&payload));
            assert_eq!(code(refused), ErrorCode::MalformedRequest, "{payload}");
        }
        assert_eq!(
            code(create(Some(&repo.state_dir), None)),
            ErrorCode::MalformedRequest
        );
        assert!(!path.exists());
    }

    #[test]
    fn create_refuses_a_branch_that_exists_at_another_commit() {
        let repo = Scratch::new("other-commit");
        git_in(&repo.root, &["branch", "feature/issue-1", "main"]);
        repo.commit("two");
        let path = repo.managed("issue-1");

        let error = repo.create(&path, "feature/issue-1", "main").unwrap_err();

        assert_eq!(error.code, ErrorCode::InvariantViolation);
        assert!(
            error.message.contains("another commit"),
            "{}",
            error.message
        );
        assert!(!path.exists());
    }

    #[test]
    fn create_refuses_a_branch_that_another_worktree_has_checked_out() {
        let repo = Scratch::new("checked-out");
        repo.create(&repo.managed("issue-1"), "feature/issue-1", "main")
            .unwrap();
        let path = repo.managed("issue-2");

        let error = repo.create(&path, "feature/issue-1", "main").unwrap_err();

        assert_eq!(error.code, ErrorCode::InvariantViolation);
        assert!(
            error.message.contains("checked out elsewhere"),
            "{}",
            error.message
        );
        assert!(!path.exists());
    }

    #[test]
    fn create_refuses_a_path_that_is_not_an_empty_directory() {
        let repo = Scratch::new("occupied");
        let path = repo.managed("issue-1");
        fs::create_dir_all(&path).unwrap();
        fs::write(path.join("kept"), "mine").unwrap();
        let empty = repo.managed("issue-2");
        fs::create_dir_all(&empty).unwrap();

        let occupied = repo.create(&path, "feature/issue-1", "main");
        let created = repo.create(&empty, "feature/issue-2", "main").unwrap();

        assert_eq!(code(occupied), ErrorCode::InvariantViolation);
        assert_eq!(fs::read_to_string(path.join("kept")).unwrap(), "mine");
        assert!(!repo.branch_exists("feature/issue-1"));
        assert_eq!(created["created"], true);
    }

    #[cfg(unix)]
    #[test]
    fn create_runs_no_hook_of_the_repository() {
        use std::os::unix::fs::PermissionsExt;

        let repo = Scratch::new("hook");
        let marker = repo.base.join("hook-ran");
        let hooks = repo.root.join(".git/hooks");
        fs::create_dir_all(&hooks).unwrap();
        let hook = hooks.join("post-checkout");
        fs::write(&hook, format!("#!/bin/sh\ntouch '{}'\n", marker.display())).unwrap();
        fs::set_permissions(&hook, fs::Permissions::from_mode(0o755)).unwrap();

        repo.create(&repo.managed("issue-1"), "feature/issue-1", "main")
            .unwrap();

        assert!(!marker.exists(), "worktree.create ran the hook");
        // The same hook does run when nothing disables it: the check above is not vacuous.
        let enabled = format!("core.hooksPath={}", hooks.display());
        let plain = repo.base.join("plain");
        git_in(
            &repo.root,
            &[
                "-c",
                &enabled,
                "worktree",
                "add",
                "--quiet",
                "--detach",
                plain.to_str().unwrap(),
            ],
        );
        assert!(marker.exists(), "the hook of the test never runs");
    }

    #[test]
    fn remove_removes_a_clean_worktree_and_keeps_its_branch() {
        let repo = Scratch::new("remove");
        let path = repo.managed("issue-1");
        repo.create(&path, "feature/issue-1", "main").unwrap();

        let result = repo.remove(&path).unwrap();

        assert_eq!(Path::new(result["path"].as_str().unwrap()), path);
        assert_eq!(result["removed"], true);
        assert!(!path.exists());
        assert!(repo.branch_exists("feature/issue-1"));
        assert!(!git_in(&repo.root, &["worktree", "list", "--porcelain"]).contains("issue-1"));
    }

    #[test]
    fn remove_serves_the_root_of_the_coding_application_too() {
        let repo = Scratch::new("remove-application");
        let path = repo.root.join(APPLICATION_ROOT).join("session-1");
        git_in(
            &repo.root,
            &[
                "worktree",
                "add",
                "--quiet",
                "-b",
                "session-1",
                path.to_str().unwrap(),
            ],
        );

        let result = repo.remove(&path).unwrap();

        assert_eq!(result["removed"], true);
        assert!(!path.exists());
        assert!(repo.branch_exists("session-1"));
    }

    #[test]
    fn remove_refuses_a_dirty_worktree_and_leaves_it_in_place() {
        let repo = Scratch::new("dirty");
        let path = repo.managed("issue-1");
        repo.create(&path, "feature/issue-1", "main").unwrap();
        fs::write(path.join("untracked"), "work").unwrap();

        let error = repo.remove(&path).unwrap_err();

        assert_eq!(error.code, ErrorCode::InvariantViolation);
        assert_eq!(error.domain, FailureDomain::Tooling);
        assert!(!error.facts["git_stderr"].as_str().unwrap().is_empty());
        assert!(error.facts["git_exit_code"].as_i64().unwrap() != 0);
        assert_eq!(fs::read_to_string(path.join("untracked")).unwrap(), "work");
        assert!(git_in(&repo.root, &["worktree", "list", "--porcelain"]).contains("issue-1"));
    }

    #[test]
    fn remove_answers_not_found_for_a_path_that_is_no_worktree() {
        let repo = Scratch::new("unregistered");
        let path = repo.managed("issue-1");
        fs::create_dir_all(&path).unwrap();
        fs::write(path.join("kept"), "mine").unwrap();

        let error = repo.remove(&path).unwrap_err();

        assert_eq!(error.code, ErrorCode::NotFound);
        assert_eq!(fs::read_to_string(path.join("kept")).unwrap(), "mine");
    }

    #[test]
    fn remove_refuses_a_path_outside_the_managed_roots() {
        let repo = Scratch::new("remove-outside");
        let plain = repo.base.join("plain");
        git_in(
            &repo.root,
            &[
                "worktree",
                "add",
                "--quiet",
                "--detach",
                plain.to_str().unwrap(),
            ],
        );
        let outside = [
            plain.clone(),
            repo.root.clone(),
            repo.root.join(SANDBOX_ROOT),
            repo.root.join(APPLICATION_ROOT),
            repo.managed("../../../../plain"),
        ];

        for path in outside {
            let refused = repo.remove(&path);
            assert_eq!(code(refused), ErrorCode::PolicyDenied, "{}", path.display());
        }
        assert!(plain.join("README").exists());
        assert_eq!(
            code(remove(
                Some(&repo.state_dir),
                Some(&json!({"path": repo.managed("issue-1"), "force": true}))
            )),
            ErrorCode::MalformedRequest
        );
    }

    #[test]
    fn commit_records_every_change_of_the_worktree_on_its_branch() {
        let repo = Scratch::new("commit");
        let path = repo.worktree("issue-1");
        let base = git_in(&path, &["rev-parse", "HEAD"]);
        fs::write(path.join("README"), "changed").unwrap();
        fs::write(path.join("added"), "new").unwrap();
        let message = "feat: two changes\n\n--amend stays text\n";

        let result = repo
            .commit_in(&json!({"path": path, "message": message}))
            .unwrap();

        let head = git_in(&repo.root, &["rev-parse", "refs/heads/feature/issue-1"]);
        assert_eq!(result["head"], head.as_str());
        assert_eq!(result["branch"], "feature/issue-1");
        assert_eq!(result["committed"], true);
        assert_eq!(Path::new(result["path"].as_str().unwrap()), path);
        assert_eq!(git_in(&path, &["rev-parse", "HEAD^"]), base);
        assert_eq!(
            git_in(&path, &["log", "-1", "--format=%B"]),
            message.trim_end()
        );
        assert_eq!(
            git_in(&path, &["show", "--name-only", "--format=", "HEAD"]),
            "README\nadded"
        );
        assert_eq!(git_in(&path, &["status", "--porcelain"]), "");
    }

    #[test]
    fn commit_stages_only_the_named_paths_and_reads_them_literally() {
        let repo = Scratch::new("commit-paths");
        let path = repo.worktree("issue-1");
        fs::write(path.join("kept.txt"), "one").unwrap();
        fs::write(path.join("left.txt"), "two").unwrap();

        let glob = repo.commit_in(&json!({"path": path, "message": "x", "pathspecs": ["*.txt"]}));
        let named = repo
            .commit_in(&json!({"path": path, "message": "feat: kept", "pathspecs": ["kept.txt"]}))
            .unwrap();

        assert_eq!(code(glob), ErrorCode::InvariantViolation);
        assert_eq!(
            git_in(&path, &["show", "--name-only", "--format=", "HEAD"]),
            "kept.txt"
        );
        assert_eq!(named["committed"], true);
        assert_eq!(git_in(&path, &["status", "--porcelain"]), "?? left.txt");
    }

    #[test]
    fn commit_refuses_a_worktree_without_a_change() {
        let repo = Scratch::new("commit-clean");
        let path = repo.worktree("issue-1");
        let head = git_in(&path, &["rev-parse", "HEAD"]);

        let error = repo
            .commit_in(&json!({"path": path, "message": "feat: nothing"}))
            .unwrap_err();

        assert_eq!(error.code, ErrorCode::InvariantViolation);
        assert!(error.message.contains("no change"), "{}", error.message);
        assert_eq!(git_in(&path, &["rev-parse", "HEAD"]), head);
    }

    #[test]
    fn commit_refuses_a_worktree_with_a_detached_head() {
        let repo = Scratch::new("commit-detached");
        let path = repo.root.join(APPLICATION_ROOT).join("session-1");
        git_in(
            &repo.root,
            &[
                "worktree",
                "add",
                "--quiet",
                "--detach",
                path.to_str().unwrap(),
            ],
        );
        fs::write(path.join("added"), "new").unwrap();

        let error = repo
            .commit_in(&json!({"path": path, "message": "feat: detached"}))
            .unwrap_err();

        assert_eq!(error.code, ErrorCode::InvariantViolation);
        assert!(error.message.contains("detached"), "{}", error.message);
        assert_eq!(git_in(&path, &["status", "--porcelain"]), "?? added");
    }

    #[test]
    fn commit_refuses_a_path_that_is_no_managed_worktree() {
        let repo = Scratch::new("commit-outside");
        let unregistered = repo.managed("issue-1");
        fs::create_dir_all(&unregistered).unwrap();
        fs::write(unregistered.join("kept"), "mine").unwrap();

        let main = repo.commit_in(&json!({"path": repo.root, "message": "feat: main"}));
        let missing = repo.commit_in(&json!({"path": unregistered, "message": "feat: lost"}));

        assert_eq!(code(main), ErrorCode::PolicyDenied);
        assert_eq!(code(missing), ErrorCode::NotFound);
    }

    #[test]
    fn commit_refuses_a_payload_it_does_not_define() {
        let repo = Scratch::new("commit-payload");
        let path = repo.worktree("issue-1");
        fs::write(path.join("added"), "new").unwrap();
        let malformed = [
            json!({"path": path, "message": "feat: x", "amend": true}),
            json!({"path": path}),
            json!({"path": path, "message": " \n "}),
            json!({"path": path, "message": "feat: x\u{0}"}),
            json!({"path": path, "message": "feat: \u{1b}[31m"}),
            json!({"path": path, "message": "x".repeat(MAX_MESSAGE_BYTES + 1)}),
            json!({"path": path, "message": "feat: x", "pathspecs": []}),
            json!({"path": path, "message": "feat: x", "pathspecs": "added"}),
            json!({"path": path, "message": "feat: x", "pathspecs": [""]}),
            json!({"path": path, "message": "feat: x", "pathspecs": [1]}),
            json!([path, "feat: x"]),
        ];
        let outside = [
            json!({"path": path, "message": "feat: x", "pathspecs": ["../escaped"]}),
            json!({"path": path, "message": "feat: x", "pathspecs": ["/etc/passwd"]}),
        ];

        for payload in malformed {
            let refused = repo.commit_in(&payload);
            assert_eq!(code(refused), ErrorCode::MalformedRequest, "{payload}");
        }
        for payload in outside {
            let refused = repo.commit_in(&payload);
            assert_eq!(code(refused), ErrorCode::PolicyDenied, "{payload}");
        }
        assert_eq!(
            code(commit(Some(&repo.state_dir), None)),
            ErrorCode::MalformedRequest
        );
        assert_eq!(git_in(&path, &["status", "--porcelain"]), "?? added");
    }

    #[cfg(unix)]
    #[test]
    fn commit_runs_no_hook_of_the_repository() {
        use std::os::unix::fs::PermissionsExt;

        let repo = Scratch::new("commit-hook");
        let path = repo.worktree("issue-1");
        let marker = repo.base.join("hook-ran");
        let hooks = repo.root.join(".git/hooks");
        fs::create_dir_all(&hooks).unwrap();
        let hook = hooks.join("pre-commit");
        fs::write(&hook, format!("#!/bin/sh\ntouch '{}'\n", marker.display())).unwrap();
        fs::set_permissions(&hook, fs::Permissions::from_mode(0o755)).unwrap();
        fs::write(path.join("added"), "new").unwrap();

        repo.commit_in(&json!({"path": path, "message": "feat: no hook"}))
            .unwrap();

        assert!(!marker.exists(), "worktree.commit ran the hook");
        // The same hook does run when nothing disables it: the check above is not vacuous.
        fs::write(path.join("more"), "new").unwrap();
        git_in(&path, &["add", "more"]);
        let enabled = format!("core.hooksPath={}", hooks.display());
        git_in(
            &path,
            &["-c", &enabled, "commit", "--quiet", "-m", "feat: hook"],
        );
        assert!(marker.exists(), "the hook of the test never runs");
    }

    #[cfg(unix)]
    #[test]
    fn commit_never_reads_the_git_directory_the_worktree_gitfile_names() {
        let repo = Scratch::new("commit-gitfile");
        let path = repo.worktree("issue-1");
        let marker = repo.base.join("filter-ran");
        // A git directory the requester controls, with a clean filter that runs a command.
        let evil = repo.base.join("evil");
        fs::create_dir_all(&evil).unwrap();
        git_in(&evil, &["init", "--quiet"]);
        let filter = format!("touch '{}'; cat", marker.display());
        git_in(&evil, &["config", "filter.x.clean", &filter]);
        fs::write(
            path.join(".git"),
            format!("gitdir: {}\n", evil.join(".git").display()),
        )
        .unwrap();
        fs::write(path.join(".gitattributes"), "* filter=x\n").unwrap();
        fs::write(path.join("added"), "new").unwrap();

        let result = repo.commit_in(&json!({"path": path, "message": "feat: no filter"}));

        assert!(
            !marker.exists(),
            "worktree.commit ran the filter: {result:?}"
        );
        // The same filter does run when Git follows the gitfile: the check above is not vacuous.
        fs::write(path.join("more"), "new").unwrap();
        git_in(&path, &["add", "more"]);
        assert!(marker.exists(), "the filter of the test never runs");
    }

    /// Every change operation refuses the worktree on `branch` with `policy_denied` and changes
    /// neither the branch nor the index.
    fn assert_protected(repo: &Scratch, name: &str, branch: &str) {
        let path = repo.worktree_on(name, branch);
        let base = git_in(&path, &["rev-parse", "HEAD"]);
        fs::write(path.join("added"), "new").unwrap();
        repo.commit("moved");

        let committed = repo.commit_in(&json!({"path": path, "message": "feat: protected"}));
        let rebased = repo
            .rebase_in(&json!({"path": path, "action": "start", "onto": "main", "upstream": base}));
        let merged = repo.merge_in(&json!({"path": path, "action": "start", "revision": "main"}));

        for (operation, result) in [
            ("commit", committed),
            ("rebase", rebased),
            ("merge", merged),
        ] {
            let error = result.expect_err(operation);
            assert_eq!(
                error.code,
                ErrorCode::PolicyDenied,
                "{operation} on {branch}"
            );
            assert_eq!(error.domain, FailureDomain::Policy);
        }
        assert_eq!(
            git_in(&repo.root, &["rev-parse", &format!("refs/heads/{branch}")]),
            base
        );
        assert_eq!(git_in(&path, &["status", "--porcelain"]), "?? added");
    }

    #[test]
    fn change_operations_refuse_an_integration_branch() {
        let repo = Scratch::new("integration");

        assert_protected(&repo, "team", "integration/team");
    }

    #[test]
    fn change_operations_refuse_the_base_branch_of_the_project() {
        let repo = Scratch::new("base-branch");
        fs::create_dir_all(repo.root.join(".harness")).unwrap();
        fs::write(
            repo.root.join(PROJECT_FILE),
            r#"{"base_branch": "release"}"#,
        )
        .unwrap();

        assert_protected(&repo, "release", "release");
    }

    #[test]
    fn change_operations_refuse_master_without_a_project_base_branch() {
        let repo = Scratch::new("default-base");

        assert_protected(&repo, "master", "master");
    }

    #[test]
    fn rebase_carries_the_branch_onto_a_moved_tip() {
        let repo = Scratch::new("rebase");
        let path = repo.worktree("issue-1");
        let base = git_in(&path, &["rev-parse", "HEAD"]);
        fs::write(path.join("added"), "new").unwrap();
        git_in(&path, &["add", "added"]);
        git_in(&path, &["commit", "--quiet", "-m", "feat: added"]);
        let tip = repo.commit("moved");

        let result = repo
            .rebase_in(&json!({"path": path, "action": "start", "onto": "main", "upstream": base}))
            .unwrap();

        assert_eq!(result["in_progress"], false);
        assert_eq!(result["conflicts"], json!([]));
        assert_eq!(result["branch"], "feature/issue-1");
        assert_eq!(result["git_output"], Value::Null);
        assert_eq!(
            result["head"],
            git_in(&repo.root, &["rev-parse", "refs/heads/feature/issue-1"]).as_str()
        );
        assert_eq!(git_in(&path, &["rev-parse", "HEAD^"]), tip);
        assert_eq!(git_in(&path, &["log", "-1", "--format=%s"]), "feat: added");
    }

    #[test]
    fn rebase_stops_on_a_conflict_and_continues_with_the_resolution() {
        let repo = Scratch::new("rebase-conflict");
        let (path, base) = repo.diverged("issue-1", "ours", "theirs");
        let tip = git_in(&repo.root, &["rev-parse", "main"]);

        let stopped = repo
            .rebase_in(&json!({"path": path, "action": "start", "onto": "main", "upstream": base}))
            .unwrap();

        assert_eq!(stopped["in_progress"], true);
        assert_eq!(stopped["conflicts"], json!(["README"]));
        assert_eq!(stopped["branch"], Value::Null);
        assert!(
            stopped["git_output"].as_str().unwrap().contains("README"),
            "{stopped}"
        );

        fs::write(path.join("README"), "both").unwrap();
        let finished = repo
            .rebase_in(&json!({"path": path, "action": "continue"}))
            .unwrap();

        assert_eq!(finished["in_progress"], false);
        assert_eq!(finished["branch"], "feature/issue-1");
        assert_eq!(git_in(&path, &["rev-parse", "HEAD^"]), tip);
        assert_eq!(git_in(&path, &["log", "-1", "--format=%s"]), "feat: ours");
        assert_eq!(fs::read_to_string(path.join("README")).unwrap(), "both");
    }

    #[test]
    fn rebase_abort_restores_and_skip_drops_the_stopped_commit() {
        let repo = Scratch::new("rebase-abort");
        let (path, base) = repo.diverged("issue-1", "ours", "theirs");
        let head = git_in(&path, &["rev-parse", "HEAD"]);
        let start = json!({"path": path, "action": "start", "onto": "main", "upstream": base});
        repo.rebase_in(&start).unwrap();

        let aborted = repo
            .rebase_in(&json!({"path": path, "action": "abort"}))
            .unwrap();

        assert_eq!(aborted["in_progress"], false);
        assert_eq!(aborted["head"], head.as_str());
        assert_eq!(aborted["branch"], "feature/issue-1");

        repo.rebase_in(&start).unwrap();
        let skipped = repo
            .rebase_in(&json!({"path": path, "action": "skip"}))
            .unwrap();

        assert_eq!(skipped["in_progress"], false);
        assert_eq!(
            skipped["head"],
            git_in(&repo.root, &["rev-parse", "main"]).as_str()
        );
    }

    #[test]
    fn merge_stops_on_a_conflict_and_commits_the_resolution() {
        let repo = Scratch::new("merge");
        let (path, _) = repo.diverged("issue-1", "ours", "theirs");
        let ours = git_in(&path, &["rev-parse", "HEAD"]);
        let theirs = git_in(&repo.root, &["rev-parse", "main"]);

        let stopped = repo
            .merge_in(&json!({
                "path": path, "action": "start", "revision": "main",
                "message": "chore: merge the moved tip",
            }))
            .unwrap();

        assert_eq!(stopped["in_progress"], true);
        assert_eq!(stopped["conflicts"], json!(["README"]));
        assert_eq!(stopped["branch"], "feature/issue-1");

        fs::write(path.join("README"), "both").unwrap();
        let finished = repo
            .merge_in(&json!({"path": path, "action": "continue"}))
            .unwrap();

        assert_eq!(finished["in_progress"], false);
        assert_eq!(
            git_in(&path, &["log", "-1", "--format=%P"]),
            format!("{ours} {theirs}")
        );
        assert_eq!(
            git_in(&path, &["log", "-1", "--format=%s"]),
            "chore: merge the moved tip"
        );
        assert_eq!(git_in(&path, &["status", "--porcelain"]), "");
    }

    #[test]
    fn merge_finishes_without_a_conflict_and_abort_restores_a_stopped_one() {
        let repo = Scratch::new("merge-clean");
        let path = repo.worktree("issue-1");
        fs::write(path.join("added"), "new").unwrap();
        git_in(&path, &["add", "added"]);
        git_in(&path, &["commit", "--quiet", "-m", "feat: added"]);
        repo.commit("moved");

        let merged = repo
            .merge_in(&json!({"path": path, "action": "start", "revision": "main"}))
            .unwrap();

        assert_eq!(merged["in_progress"], false);
        assert_eq!(fs::read_to_string(path.join("README")).unwrap(), "moved");

        let (conflicted, _) = repo.diverged("issue-2", "ours", "theirs");
        let head = git_in(&conflicted, &["rev-parse", "HEAD"]);
        repo.merge_in(&json!({"path": conflicted, "action": "start", "revision": "main"}))
            .unwrap();
        let aborted = repo
            .merge_in(&json!({"path": conflicted, "action": "abort"}))
            .unwrap();

        assert_eq!(aborted["in_progress"], false);
        assert_eq!(aborted["head"], head.as_str());
        assert_eq!(git_in(&conflicted, &["status", "--porcelain"]), "");
    }

    #[test]
    fn rebase_and_merge_refuse_a_step_out_of_order() {
        let repo = Scratch::new("order");
        let (path, base) = repo.diverged("issue-1", "ours", "theirs");

        let idle_continue = repo.rebase_in(&json!({"path": path, "action": "continue"}));
        let idle_abort = repo.merge_in(&json!({"path": path, "action": "abort"}));
        repo.rebase_in(&json!({"path": path, "action": "start", "onto": "main", "upstream": base}))
            .unwrap();
        let merge_during_rebase =
            repo.merge_in(&json!({"path": path, "action": "start", "revision": "main"}));
        let commit_during_rebase = repo.commit_in(&json!({"path": path, "message": "feat: x"}));

        assert_eq!(code(idle_continue), ErrorCode::InvariantViolation);
        assert_eq!(code(idle_abort), ErrorCode::InvariantViolation);
        assert_eq!(code(merge_during_rebase), ErrorCode::InvariantViolation);
        assert_eq!(code(commit_during_rebase), ErrorCode::InvariantViolation);
    }

    #[test]
    fn rebase_and_merge_refuse_a_payload_they_do_not_define() {
        let repo = Scratch::new("change-payload");
        let path = repo.worktree("issue-1");
        let malformed_rebase = [
            json!({"path": path}),
            json!({"path": path, "action": "start", "onto": "main"}),
            json!({"path": path, "action": "start", "onto": "-x", "upstream": "main"}),
            json!({"path": path, "action": "abort", "onto": "main"}),
            json!({"path": path, "action": "edit-todo"}),
            json!({"path": path, "action": "start", "onto": "main", "upstream": "main", "x": "y"}),
            json!({"path": path, "action": 1}),
        ];
        let malformed_merge = [
            json!({"path": path, "action": "start"}),
            json!({"path": path, "action": "start", "revision": "--squash"}),
            json!({"path": path, "action": "start", "revision": "main", "message": " "}),
            json!({"path": path, "action": "start", "revision": "main", "message": "a\nb"}),
            json!({"path": path, "action": "skip"}),
            json!({"path": path, "action": "continue", "revision": "main"}),
        ];

        for payload in malformed_rebase {
            let refused = repo.rebase_in(&payload);
            assert_eq!(code(refused), ErrorCode::MalformedRequest, "{payload}");
        }
        for payload in malformed_merge {
            let refused = repo.merge_in(&payload);
            assert_eq!(code(refused), ErrorCode::MalformedRequest, "{payload}");
        }
        let unknown = repo.merge_in(&json!({"path": path, "action": "start", "revision": "nope"}));
        let outside = repo.rebase_in(&json!({"path": repo.root, "action": "abort"}));
        assert_eq!(code(unknown), ErrorCode::NotFound);
        assert_eq!(code(outside), ErrorCode::PolicyDenied);
    }

    #[test]
    fn rebase_and_merge_refuse_to_start_on_a_detached_head() {
        let repo = Scratch::new("change-detached");
        let path = repo.root.join(APPLICATION_ROOT).join("session-1");
        git_in(
            &repo.root,
            &[
                "worktree",
                "add",
                "--quiet",
                "--detach",
                path.to_str().unwrap(),
            ],
        );

        let rebased = repo.rebase_in(
            &json!({"path": path, "action": "start", "onto": "main", "upstream": "main"}),
        );
        let merged = repo.merge_in(&json!({"path": path, "action": "start", "revision": "main"}));

        assert_eq!(code(rebased), ErrorCode::InvariantViolation);
        assert_eq!(code(merged), ErrorCode::InvariantViolation);
    }

    #[cfg(unix)]
    #[test]
    fn rebase_runs_no_hook_of_the_repository() {
        use std::os::unix::fs::PermissionsExt;

        let repo = Scratch::new("rebase-hook");
        let (path, base) = repo.diverged("issue-1", "ours", "ours");
        let marker = repo.base.join("hook-ran");
        let hooks = repo.root.join(".git/hooks");
        fs::create_dir_all(&hooks).unwrap();
        let hook = hooks.join("pre-rebase");
        fs::write(&hook, format!("#!/bin/sh\ntouch '{}'\n", marker.display())).unwrap();
        fs::set_permissions(&hook, fs::Permissions::from_mode(0o755)).unwrap();

        repo.rebase_in(&json!({"path": path, "action": "start", "onto": "main", "upstream": base}))
            .unwrap();

        assert!(!marker.exists(), "worktree.rebase ran the hook");
    }

    #[test]
    fn a_runtime_that_serves_no_state_knows_no_repository() {
        let payload = json!({"path": "/repo/.harness/.sandboxes/worktrees/issue-1"});

        let error = remove(None, Some(&payload)).unwrap_err();

        assert_eq!(error.code, ErrorCode::InvariantViolation);
        assert_eq!(error.domain, FailureDomain::EnvironmentPreparation);
    }
}
