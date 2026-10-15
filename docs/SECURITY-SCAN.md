# Security scan (Trivy)

**What is scanned.** On every push, CI builds the backend and frontend images and runs Trivy v0.70.0 on
each before anything is pushed. Trivy inspects the image's OS packages (Debian 13 for the backend,
Alpine for the frontend) and the application dependencies baked into it (each Python package in the
backend; the nginx runtime and static assets in the frontend), comparing them with public vulnerability
databases. The gate is `severity: HIGH,CRITICAL`, `ignore-unfixed: true`, `exit-code: 1`: any HIGH or
CRITICAL finding that has a fix available fails the job and the image is not pushed.

**Result of the latest run (commit `9779b01`).** Clean: 0 HIGH/CRITICAL findings across the Debian 13.7 OS
layer and every Python package in the backend, and none in the frontend image. A clean result means no
*known, fixable* HIGH/CRITICAL CVE existed on that day, not that the image is flawless: new CVEs are
published daily, so the scan runs on every push and Dependabot proposes base-image and dependency bumps
weekly. A SARIF copy of each scan is uploaded to the repository's Security tab.

**If a finding appears**, the response is: read the table (package, installed version, fixed version),
bump the digest-pinned base image or the pinned dependency, rebuild, and re-scan. A `.trivyignore` entry
is only acceptable with a written justification for an unfixable false positive.

**Supply-chain note.** In March 2026 the `aquasecurity/trivy-action` tags were compromised; because
every action here is pinned to a full commit SHA of a post-incident release (v0.36.0), the pipeline was
not exposed to mutable-tag hijacking.
