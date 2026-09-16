# Forge

**Forge is a local workflow runner for chaining commands, file operations, HTTP calls, waits, and app launches into reusable desktop automations.**

It is aimed at personal developer workflows: build a release, prepare a folder, package files, run checks, call an endpoint, or repeat a fiddly sequence without adopting a cloud automation platform.

## Highlights

- Create multiple named workflows
- Add, edit, remove, duplicate, and reorder steps
- V1 step types: command, copy, move, create folder, write file, delete, HTTP request, wait, and open path/app
- Per-step timeout and continue-on-error controls
- Live execution log with stop support
- Local JSON workflow storage in `~/.forge/`
- Import and export portable `.forge.json` workflow files
- No account, backend, telemetry, or hosted runner

## Run from source

```powershell
pyw forge_desktop.pyw
```

Python 3.10+; standard library only at runtime.

## Build Windows executable

```powershell
powershell -ExecutionPolicy Bypass -File .\build-windows.ps1
```

Creates `dist\Forge.exe`.

## Safety

Forge executes only workflows the user creates or imports. Delete steps are visibly labelled and the desktop app asks for confirmation before running a workflow that contains deletion. Review imported workflow files before execution, especially command steps.

## License

MIT
