# Changelog

All notable changes to Forge are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed
- Stopping a command could report "stopped" while it ran on: Forge waited only for the command's shell, so a program the shell started that ignored SIGTERM survived. Stop (and timeouts) now wait for the whole process group and kill whatever remains (macOS and Linux; Windows already ends the tree with `taskkill /T /F`).
- A stop requested just before a run started was forgotten when the run began. Stop now holds until `WorkflowRunner.reset()`, which the app calls before each run.
- A file step with a blank path acted on the folder Forge was running in: a blank **delete** step deleted its contents. Blank paths are now refused, and a delete may not target a drive root, your home folder, the folder Forge runs in, or a folder containing one of those.

### Added
- `CONTRIBUTING.md`, `docs/ARCHITECTURE.md`, `docs/V1_RELEASE_CHECKLIST.md` and `docs/RECORDING_GUIDE.md`.
- README: a comparison with the well-known alternatives, and links to the rest of the Depot suite.

- `WorkflowRunner(on_event=...)`: optional structured progress (step started, succeeded, failed with the command's PID and exit code, run finished) for programs that drive Forge, such as Depot. Log output is unchanged.

### Changed
- `SECURITY.md` now states supported versions, response times and the threat model.
- The bug report form asks for the run method and the expected behaviour.

## [1.0.2] - 2026-09-26

### Fixed
- A command's Timeout and Stop terminated only the shell that launched it: the command itself kept running, and Forge waited for it to finish. Commands now run in their own process group, and the whole group is stopped.

### Added
- Behavioural tests covering the areas above and the rest of the core.

## [1.0.1] - 2026-09-26

### Added
- Release builds for macOS (Apple Silicon) and Linux (x86_64) alongside Windows, with one `SHA256SUMS.txt` per release.
- The application icon, which the Windows executable was missing.
- A screenshot of the running app in the README.

### Changed
- CI builds the macOS and Linux packages on every push.

## [1.0.0] - 2026-09-16

### Added
- Polished public release documentation and screenshot.
- Cross-platform CI checks plus Windows executable build artifact.
- Automated tagged GitHub Release workflow with SHA256 checksum.
- Issue templates and security/reporting guidance.

### Current product
- Named reusable workflows
- Command, copy, move, folder, write, delete, HTTP, wait, and launch steps
- Reorder, duplicate, and edit steps
- Per-step timeout and continue-on-error controls
- Live execution log and stop support
- Portable .forge.json import/export
