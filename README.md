<div align="center">
  <img src="assets/icon.svg" width="132" alt="Forge icon">
  <h1>Forge</h1>
  <p><strong>A local workflow runner for chaining commands, files, HTTP calls, waits, and app launches into reusable automations.</strong></p>
  <p>
    <a href="https://github.com/purysho/Forge/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/purysho/Forge/actions/workflows/ci.yml/badge.svg"></a>
    <a href="https://github.com/purysho/Forge/releases"><img alt="Releases" src="https://img.shields.io/github/v/release/purysho/Forge?display_name=tag&sort=semver"></a>
    <a href="LICENSE"><img alt="MIT" src="https://img.shields.io/badge/license-MIT-202832.svg"></a>
    <a href="#download"><img alt="Status: beta" src="https://img.shields.io/badge/status-beta-C9A44C.svg"></a>
  </p>
  <p><strong>Download:</strong> <a href="https://github.com/purysho/Forge/releases/latest/download/Forge-Windows-x64.exe">Windows</a> · <a href="https://github.com/purysho/Forge/releases/latest/download/Forge-macOS-arm64.zip">macOS</a> · <a href="https://github.com/purysho/Forge/releases/latest/download/Forge-Linux-x86_64.tar.gz">Linux</a> · <a href="#run-from-source">Run from source</a> · <a href="https://github.com/purysho/Forge/issues">Report an issue</a></p>
</div>

![Forge after running a six-step backup workflow, with its run log](docs/screenshot.png)

> 📹 Demo GIF coming in the next release. See the screenshot above for the current UI.

## What it does

- Named reusable workflows
- Command, copy, move, folder, write, delete, HTTP, wait, and launch steps
- Reorder, duplicate, and edit steps
- Per-step timeout and continue-on-error controls
- Live execution log and stop support
- Portable .forge.json import/export

## Why not make, GitHub Actions, just or shell scripts?

| Tool | What it does better | Where Forge differs |
|---|---|---|
| [`make`](https://www.gnu.org/software/make/) | Dependency graphs and incremental rebuilds: only what changed is rebuilt. | Forge runs steps top to bottom every time, with no dependency tracking. It is for sequences, not builds. |
| [GitHub Actions](https://docs.github.com/actions) | Runs on pushes, pull requests and schedules, on hosted machines, with secrets and matrices. | Forge runs only on your machine and only when you press **Run**. |
| [`just`](https://github.com/casey/just) | Named recipes with arguments in a `justfile` that lives in the repository and is reviewed like code. | If the commands belong to one project and its team, use `just`. Forge workflows are personal and live outside any repository. |
| Shell scripts | The most flexible option: variables, conditionals, loops, pipes. | Forge has none of those. It gives you file and HTTP steps without shell syntax, a per-step timeout, a live log, and a **Stop** button that ends the whole process tree. |

These are great tools, and each is more capable than Forge. The difference is operational, not technical: Forge is a single portable download, needs no account, no server, no Docker, and no configuration to start, and stores everything locally under `~/.forge/`. If you already use one of the tools above and it works for you, keep using it. Forge exists for the handful of personal multi-step chores you would otherwise retype, with zero setup and no cloud dependency.

## Part of the Depot suite

Depot (in development) brings these tools together in one app — shared workspace
context, an event bus that connects them, and a unified session timeline.

[Depot](https://github.com/purysho/Depot) ·
[Switchyard](https://github.com/purysho/Switchyard) ·
[Needle](https://github.com/purysho/Needle) ·
[Relay](https://github.com/purysho/Relay) ·
[Pulse](https://github.com/purysho/Pulse) ·
[BLACKBOX](https://github.com/purysho/BLACKBOX) ·
[Forge](https://github.com/purysho/Forge)

## Download

| Platform | File |
|---|---|
| Windows 10/11 (x64) | [Forge-Windows-x64.exe](https://github.com/purysho/Forge/releases/latest/download/Forge-Windows-x64.exe) — portable, no installer |
| macOS (Apple Silicon) | [Forge-macOS-arm64.zip](https://github.com/purysho/Forge/releases/latest/download/Forge-macOS-arm64.zip) — unzip and move to Applications |
| Linux (x86_64) | [Forge-Linux-x86_64.tar.gz](https://github.com/purysho/Forge/releases/latest/download/Forge-Linux-x86_64.tar.gz) — extract and run `./Forge` |

Each [release](https://github.com/purysho/Forge/releases) is built from the tagged source by GitHub Actions and carries a `SHA256SUMS.txt`. The builds are not yet code-signed, so on first launch Windows SmartScreen may ask you to confirm ("More info" → "Run anyway"), and macOS may need you to Control-click the app and choose **Open**.

**Status: beta.** Forge does what this README describes and is covered by CI on Windows, macOS and Linux, but it is young: expect rough edges, and please [report them](https://github.com/purysho/Forge/issues).

## Run from source

Requirements: Python 3.10+ with Tk support.

```powershell
pyw forge_desktop.pyw
```

The application uses Python's standard library at runtime.

## Build a standalone Windows executable

```powershell
powershell -ExecutionPolicy Bypass -File .\build-windows.ps1
```

Output:

```text
dist\Forge.exe
```

## Privacy

Workflows and logs stay local in ~/.forge/. There is no hosted runner, account, telemetry, or backend.

## Scope

Forge executes workflows the user creates or imports. Imported workflows should be reviewed before execution, especially command and destructive file steps.

## Release process

- Every push runs tests/compile checks and builds a Windows executable artifact.
- Tags matching `v*` build the executable again, compute SHA256, and publish both files to GitHub Releases.
- See [CHANGELOG.md](CHANGELOG.md) for release history.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Security reports: [SECURITY.md](SECURITY.md).

## License

MIT
