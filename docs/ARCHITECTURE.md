# Architecture

## Entry point

`forge_desktop.pyw` — calls `forge.app.main()`, which constructs the main window
and starts the Tk event loop. No business logic here. Forge takes no
command-line arguments.

## Module layout

| Module | Responsibility |
|---|---|
| `forge_desktop.pyw` | Entry point |
| `forge/app.py` | `ForgeApp` Tkinter window (workflow list, step list, run log) and the step editor dialog |
| `forge/engine.py` | `WorkflowRunner`: runs a workflow's steps in order, handles timeout, stop and continue-on-error |
| `forge/models.py` | `Step` and `Workflow` dataclasses, `STEP_TYPES` |
| `forge/storage.py` | `ForgeStore`: workflows on disk, `.forge.json` import and export |
| `tests/` | Unit and behavioural tests for the engine, models and storage |
| `docs/` | Documentation and screenshots |
| `assets/` | Icons |

`app.py` is the only module that imports Tkinter.

## Workflow model

A `Workflow` is a name, a description and an ordered list of `Step`s. A `Step`
has a `type`, a free-form `config` dict, an optional display `name`, a
`timeout` in seconds (0 = none), and `continue_on_error`.

| Type | Config | What it does |
|---|---|---|
| `command` | `command`, `cwd` | Runs through the shell, output streamed to the log |
| `copy` / `move` | `source`, `target` | File or folder copy/move, creating parent folders |
| `mkdir` | `path` | Creates the folder and its parents |
| `write` | `path`, `content`, `append` | Writes or appends text |
| `delete` | `path` | Removes a file or a whole folder tree; a missing path is not an error |
| `http` | `method`, `url`, `headers`, `body` | Sends a request; an HTTP error status fails the step |
| `wait` | `seconds` | Sleeps, interruptible by **Stop** |
| `open` | `path` | Opens a file, folder or URL with the system handler |

## Execution

`WorkflowRunner.run()` executes steps in order and reports through a single
`logger(str)` callback. A failing step halts the workflow unless
`continue_on_error` is set.

`command` steps start in their own process group (`start_new_session` on
macOS/Linux, `CREATE_NEW_PROCESS_GROUP` on Windows). On timeout or **Stop**,
Forge stops the whole group — `killpg(SIGTERM)` then `SIGKILL` after 3 s, or
`taskkill /T /F` on Windows — so the command itself ends, not just its shell.

## State storage

`~/.forge/workflows.json`, a JSON list of workflows. Written atomically: JSON
goes to `workflows.tmp`, then `Path.replace()` over the target. A missing or
unreadable file loads as an empty list.

Export writes one workflow to a `.forge.json` file chosen in a dialog; import
reads one back. Importing never runs anything.

## Threading model

The UI runs on the main thread. **Run** starts `WorkflowRunner.run()` on a
daemon thread; a `command` step adds one more daemon thread that pumps the
command's output. **Stop** sets a `threading.Event` that the runner checks
between steps and every 50 ms while a command runs.

Log lines are handed to the UI with `self.after(0, callback)` from the worker
threads. This works with the Tcl builds shipped with CPython, but Tkinter does
not guarantee that `after()` is safe to call from another thread. Moving to a
`queue.Queue` polled by an `after()` timer on the main thread is the documented
direction and is tracked for v1.

## CI

Every push and pull request (`.github/workflows/ci.yml`):

- Unit tests and `compileall` on Ubuntu and Windows, Python 3.10 and 3.12
- A Windows executable build with a size check, uploaded as an artifact
- macOS and Linux PyInstaller packages, each launched by
  `.github/scripts/launch-check.sh` to prove it starts

Tagged releases (`v*`, `.github/workflows/release.yml`): tests, Windows, macOS
and Linux builds, optional code signing when the signing secrets exist, one
`SHA256SUMS.txt`, and a GitHub Release.

## Build

```bash
powershell -ExecutionPolicy Bypass -File ./build-windows.ps1
```

Output: `dist/Forge.exe` — portable, no installer. The macOS and Linux build
commands are the `package` job in `ci.yml`.

## Dependency policy

No third-party packages at runtime. Standard library only. This keeps the
executable small, the build reproducible, and the attack surface minimal.
Build-time tools (PyInstaller) are the exception.
