# Harness next releases

## Version and contents

The harness uses [SemVer](https://semver.org/): `MAJOR.MINOR.PATCH`. The same version
is written in `harness/VERSION`, `pyproject.toml`, the `CHANGELOG.md` section heading, and the tag name
`vMAJOR.MINOR.PATCH`. `harness/VERSION` is the verifiable version source for CD.

The GitHub workflow [release.yml](https://github.com/PVMalove/agent-harness-next/blob/master/.github/workflows/release.yml) runs on a push to `master`
and on a push of a tag strictly of the form `vMAJOR.MINOR.PATCH`. For a push to `master` the tag is derived from
`harness/VERSION`. If that tag already exists, the workflow ends without publishing. Then the job
`preflight` checks within seconds that the tag equals `harness/VERSION`, and that the section and its categories exist in
`CHANGELOG.md` (`python scripts/build_release.py --tag vX.Y.Z --check`; the same check can be
run locally before the merge). After that, all checks of
[verify.yml](https://github.com/PVMalove/agent-harness-next/blob/master/.github/workflows/verify.yml) are called, and only then is the archive built. On an error, no Release
and no tag are created. A successful run creates the tag on the verified commit (if it does not exist yet) and
a GitHub Release with two Assets:
`claude-agent-harness-vX.Y.Z.tar.gz` and `claude-agent-harness-vX.Y.Z.tar.gz.sha256`.
The Release Notes body is taken from the `[X.Y.Z]` section in `CHANGELOG.md`.

The archive contains `harness/`, `skills/`, `global/`, `global-skills/`, `bin/`, `third_party/`,
`README.md`, and the license files. `docs/`, `tests/`, and `.github/` are not in the archive.

## Release

1. In the issue branch, change `harness/VERSION` and `pyproject.toml` to one version. Add a
   `CHANGELOG.md` section `[X.Y.Z]` only with those Keep a Changelog categories that have entries
   (`Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`, `Breaking Changes`). Do not write empty
   categories or placeholders; `build_release.py` rejects a category without entries. Run the checks and the
   usual PR process; the developer does the merge.
2. After the merge to `master`, the `release` workflow publishes the version automatically: it creates the tag `vX.Y.Z`
   on the merge commit and the GitHub Release; no manual tag is needed. If the automatic release
   did not happen, after you fix the cause you can publish the tag by hand on the verified commit:

   ```bash
   git switch master
   git pull --ff-only origin master
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

3. Wait for the `release` workflow to succeed. Download the Assets on the
   [GitHub Releases](https://github.com/PVMalove/agent-harness-next/releases) page or through the CLI:

   ```bash
   gh release download vX.Y.Z --pattern 'claude-agent-harness-vX.Y.Z.tar.gz*'
   sha256sum --check claude-agent-harness-vX.Y.Z.tar.gz.sha256
   ```

   In PowerShell, compare the hash from `.sha256` with the output of
   `Get-FileHash .\claude-agent-harness-vX.Y.Z.tar.gz -Algorithm SHA256`.

A separate verified parser bundle has a manual workflow,
[release-parser-bundle.yml](https://github.com/PVMalove/agent-harness-next/blob/master/.github/workflows/release-parser-bundle.yml). Run it after a
successful main release, with `release_tag` pointing to the same commit. It checks the pinned wheels,
builds and audits the bundle, and attaches `parser-bundle.tar.gz` to the existing Release. The main
archive installs independently of this additional Asset. When the parser
bundle is missing, Repo Map returns the `minimal` level.

Release CD is implemented for GitHub only. The installable workflow of the target project may
use `glab` for tickets and merge requests; there is no GitLab release pipeline in this repository.

## Private terms check

[scripts/check_private_terms.py](https://github.com/PVMalove/agent-harness-next/blob/master/scripts/check_private_terms.py) prevents the publication of
the maintainer's private terms: client names, internal hosts, and ticket codes. It is a tool of
this repository only; it does not reach the release archive or the target projects. The check
runs in three places:

- `make verify` checks the staged diff, unpublished commits (`HEAD --not --remotes`), and the name
  of the current branch;
- the repo-local PreToolUse hook from `.claude/settings.json`
  ([scripts/hooks/check-private-terms.sh](https://github.com/PVMalove/agent-harness-next/blob/master/scripts/hooks/check-private-terms.sh)) before
  `git commit`, `git push`, and `gh issue|pr create|edit|comment` checks the command text and its
  body files (`-F`/`--file`/`--body-file`), and also the staged diff (with `-a`, `git diff HEAD`)
  for commit, unpublished commits for push, and the branch name. On a match the command is
  blocked. The hook starts to work in sessions that began after the change reached the
  current branch;
- the `private-terms` job in [verify.yml](https://github.com/PVMalove/agent-harness-next/blob/master/.github/workflows/verify.yml) for a pull request
  checks the messages and the added lines of every PR commit, the head branch, the title, and the body.

### Term list

The list comes from the non-empty environment variable `HARNESS_PRIVATE_TERMS`. If it is not set, the list
is read from the file `.private-terms.txt` in the root of the main checkout. This file is shared by all
linked worktrees and is listed in `.gitignore`. The sources are not merged. An empty variable
counts as unset. If there is neither a variable nor a file, the check ends with code 0 and
prints `private-terms: skipped: no term list ...`. A list of only comments also
counts as a skip.

Format: UTF-8 (a BOM is allowed), one term per line, spaces at the edges are dropped.
Empty lines and lines that start with `#` are skipped. There are no trailing comments:
`#` can be part of a term. The term number in the output equals the line number in the source.
The comparison looks for a case-insensitive substring in Latin and Cyrillic, `ё` matches `е`, and
full-width and decomposed characters are normalized to the usual ones (NFKC). So the terms must be
distinctive: a short or numeric term gives false positives. Homoglyphs, zero-width
characters, and a term broken by a line break are not detected.

```bash
cat > .private-terms.txt <<'EOF'
# synthetic example: one term per line
Zorblax
КвазиПлюх
qx-7741
EOF
chmod 600 .private-terms.txt
git check-ignore -q .private-terms.txt && echo ignored
```

`git clean -x` or `git clean -X` removes this file, after which the check silently falls back to
the skip notice.

### Repository secret

The `private-terms` job reads the list from the secret `HARNESS_PRIVATE_TERMS` in the same format. You can create
or update it from the file:

```bash
gh secret set HARNESS_PRIVATE_TERMS < .private-terms.txt
```

The same can be done in Settings → Secrets and variables → Actions → New repository secret.
The secret goes only into the env of the check step. In PRs from forks and from Dependabot the secret is empty, so the
job prints a `::notice` about the skip and ends successfully. The runner prints the step env to the log, and
GitHub's secret masking in logs is case-sensitive. So only the secret itself stays in the env:
its value matches the secret verbatim and is printed as `***`. The step reads the PR title, body, head branch, and
commit range from the event file `$GITHUB_EVENT_PATH`, and the check itself never
prints the terms.

### Output and manual run

Exit codes: 0 means no matches or the check was skipped; 1 means there are matches; 2 means an error (in the hook,
code 2 blocks the command). Each finding is printed as `<location>: term #N`, without the term itself
and without the line text:

- `notes.md:3` is an added line of the staged diff, `path:line` is a line of a body file;
- `commit <sha12>:3` is line 3 of the commit message (line 1 is the subject),
  `commit <sha12> path:line` is an added line of this commit;
- `branch:1` is the branch name, `command:4` is a line of the command text in the hook;
- `staged file #k`, `commit <sha12> file #k`, `commit #j`, `body file #k` are ordinal
  labels in place of the path, sha, or body file path that contains the term; `(name)` is a term in a file
  name. A path in git quotes is also replaced by a label.

Expand a label only locally, not in CI:
`git diff --cached --name-only --no-renames | sed -n 'kp'` for `staged file #k`,
`git show --format= --name-only --no-renames <sha> | sed -n 'kp'` for `commit <sha12> file #k`, and
`git log --format=%H <range> | sed -n 'jp'` for `commit #j`; `body file #k` is the k-th argument of
`--body-file`.

```bash
python scripts/check_private_terms.py --staged --commits --branch
python scripts/check_private_terms.py --commits origin/master..HEAD --body-file pr-body.md
```

The hook needs a literal path: with `cd "$DIR"` or a body file with shell substitution, it blocks the
command if a list exists. Commands outside the Bash tool (the developer's terminal), `gh api`, and edits in the web
interface are not checked. For a PR, the CI job is the safety net.

### Known hook limitations

The hook sees the state before the command runs and parses the shell approximately. What it misses here
is caught by the push check (unpublished commits) and `make verify`:

- commit checks the staged diff as of before the command, so a file from `git add X && git commit`
  in the same command and a pathspec commit `git commit -m ok X` are checked only at push or
  in `make verify`;
- option names are compared exactly: git accepts an abbreviated long option, for example `--fil=msg.md`,
  but the hook does not read this message file;
- a command is recognized after assignments, the words `if`, `then`, `elif`, `else`, `do`, `while`,
  `until`, `!`, `{`, the prefixes `timeout`, `nice`, `nohup`, `command`, `exec`, `time`, `env`, and
  also inside `$(...)` and backticks. Not recognized: `sudo`, `bash -c`, `eval`, `xargs`,
  shell aliases, aliases from the git configuration, and an alias from `-c alias.*` that refers to another
  alias.
