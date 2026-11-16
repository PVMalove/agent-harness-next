// Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
// SPDX-License-Identifier: BUSL-1.1
// Licensed under the Business Source License 1.1 (BSL-1.1).
// Commercial use, sale, or use in commercial application development is strictly
// prohibited without prior written permission from the copyright holder.
// Removing or altering this header is prohibited and voids all license rights.

//! `worktree.create` and `worktree.remove`: the managed issue worktrees of the repository
//! (issue #1180).
//!
//! The coordinator runs inside an agent sandbox that mounts the repository's `.git/worktrees`
//! read-only, so `git worktree add` and `git worktree remove` fail there. The runtime runs outside
//! the sandbox, so it creates and removes these worktrees when the coordinator asks.
//!
//! The requester is sandboxed and the runtime is not, so an operation must not let the requester
//! run code or touch a path outside the managed roots. A path is a strict descendant of a managed
//! root and crosses no symbolic link below the repository root; a branch or a base never reads as
//! an option; every Git call disables the hooks and the fsmonitor and gets its arguments as
//! separate items, never through a shell.

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
    let mut command = Command::new("git");
    command
        .arg("-C")
        .arg(&repo.root)
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
    fn a_runtime_that_serves_no_state_knows_no_repository() {
        let payload = json!({"path": "/repo/.harness/.sandboxes/worktrees/issue-1"});

        let error = remove(None, Some(&payload)).unwrap_err();

        assert_eq!(error.code, ErrorCode::InvariantViolation);
        assert_eq!(error.domain, FailureDomain::EnvironmentPreparation);
    }
}
