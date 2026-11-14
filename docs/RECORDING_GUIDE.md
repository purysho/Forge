# Recording the demo GIF

Tool: [LICEcap](https://www.cockos.com/licecap/) (Windows/macOS) or
[Peek](https://github.com/phw/peek) (Linux).

Target: 15–20 seconds, 800×500px window, 10fps.

## Script for Forge

1. Launch the app — show the empty state with no workflows
2. Click **New**, name the workflow, and add a **mkdir** step for a scratch folder
3. Add a **write** step that creates a file in that folder, then a **command** step that lists it
4. Click **Run** — show the live log reaching "Workflow complete"
5. Add a **wait** step of 30 seconds, run again, and press **Stop** to show the run ending at once

Record against throwaway data: the GIF is public, so keep real paths, hostnames,
tokens and project names out of frame.

Save as `docs/demo.gif`. Update the README img tag to point to it, and remove
the "Demo GIF coming" note beneath the screenshot.
