# Changelog

All notable changes to Forge are documented here.

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
