# Security

## Reporting a vulnerability

Please do not publish exploit details in a public issue. Open a GitHub issue with minimal non-sensitive reproduction information and mark it clearly as a security report, or contact the repository owner privately through GitHub if sensitive details are required.

## Scope

Forge executes workflows the user creates or imports. Imported workflows should be reviewed before execution, especially command and destructive file steps.

Workflows and logs stay local in ~/.forge/. There is no hosted runner, account, telemetry, or backend.
