# count-skill-usage

## 1. Name and localization
- **English name:** count-skill-usage
- **Translation / Essence:**

```text
Collection of skill usage statistics.
```
## 2. Full description
The script is a hook that is called before a tool is used (`PreToolUse(Skill)`).
Its main task is to count the calls of each skill for later analysis.
The hook works for analytics only, on the best-effort principle, and never blocks the main agent process (it always returns the success code `exit 0`).

Internal logic:
1. Reads data from the standard input stream (`stdin`) and extracts the name of the called skill from it with `grep` and `sed` (JSON format is expected).
2. If the skill name is extracted successfully, checks for the file `.claude/.skill-usage.json` in the directory `CLAUDE_PROJECT_DIR` (or in the current directory by default). If the file does not exist, creates it with an empty JSON object `{}`.
3. Reads the current number of calls for this skill from the file.
4. Increases the call counter by 1.
5. Updates the statistics file with `sed`: if the skill appears for the first time, adds a new key-value pair; if the skill already exists, updates the counter value.
## 3. Contracts
- **Input (Input/Brief):** JSON data from `stdin` that contains the field `"skill"` with the name of the called skill. The optional environment variable `CLAUDE_PROJECT_DIR`.
- **Output (Output/Report):** Always returns `exit 0`. Creates or updates the file `.claude/.skill-usage.json` and saves the updated skill statistics.
## Source

[count-skill-usage.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/count-skill-usage.sh)
