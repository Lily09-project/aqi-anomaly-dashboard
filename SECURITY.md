# Security policy

## Reporting a vulnerability

Please report suspected vulnerabilities through GitHub's private vulnerability reporting feature. Do not include API keys, credentials, personal data, or exploit details in a public issue.

Include the affected revision, reproduction steps, expected impact, and any suggested mitigation. Reports concerning unsupported forks, modified dependency sets, or data supplied by an untrusted third party may require separate reproduction against the current default branch.

## Supported version

Security fixes target the current default branch. Historical commits and third-party deployments are not maintained as supported releases.

## Security boundaries

- The repository does not require credentials for its deterministic sample workflow.
- Real API credentials belong in an untracked `.env` file or the hosting platform's secret store.
- API mode accepts HTTPS endpoints; plain HTTP is limited to loopback development addresses.
- Generated data, web exports, builds, caches, and local environments are excluded from Git.
- The static site ships a strict Content-Security-Policy, no inline scripts, and makes no third-party requests at runtime; CSV exports neutralise spreadsheet formulas.
- The browser-side what-if model is plain coefficients in JSON; no serialized executable model is ever loaded.
- GitHub Actions use read-only repository permissions, immutable action revisions, dependency auditing, static analysis, and Git-history secret scanning.

Taiwan Air Lab is an analytical prototype, not an official alerting or health-advice service.
