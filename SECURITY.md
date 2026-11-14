# Security Policy

## Supported versions

The latest release is supported. Older releases do not receive security patches.

## Reporting a vulnerability

Open a GitHub issue titled `[SECURITY] <brief description>` that names the
affected area but leaves out exploit details, or contact the maintainer
directly through the GitHub profile if the details are sensitive.

Please do not disclose publicly until the maintainer has had a chance to
respond. We aim to acknowledge within 72 hours and patch within 14 days for
confirmed vulnerabilities.

## Threat model

Forge is a local desktop application. It does not:

- open listening network ports by default
- send telemetry, usage data, or crash reports
- require an account or sign-in
- upload files, code, or configuration to any server

Specific to Forge:

- Forge runs the steps you define, and nothing else. `command` steps run through your shell with your permissions; `http` steps contact the URL you wrote; `delete` steps remove the path you wrote.
- Workflows live in `~/.forge/workflows.json`.

Vulnerabilities we care about:

- Command injection through user-supplied configuration or workflow inputs
- Unintended reads or writes outside declared scope
- State file corruption leading to data loss
- Any way for a workflow to run without the user pressing **Run** (for example on import or on launch)
- A step that does something other than what its label and fields show
- A stopped or timed-out command that keeps running
- Corruption of `workflows.json` leading to loss of workflows

Out of scope:

- Attacks requiring physical access to the machine
- Attacks that require an account on the machine that can already read or change your files
- Vulnerabilities in dependencies we do not control (report upstream)

## Scope

Forge executes workflows the user creates or imports. That a `command` step can run arbitrary commands is the purpose of the tool, not a vulnerability. Imported `.forge.json` files should be read before they are run, especially command and delete steps — treat them like shell scripts from the same source.
