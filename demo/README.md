# Static V1 presentation

Plain HTML/CSS/JavaScript; no Python service, frontend build tool, CDN or remote
font dependency. Serve this directory over HTTP; `file://` cannot fetch the
verified snapshot. All paths are relative, so project Pages subpaths work.

Source is safe to review. **No derived snapshot is tracked or approved for public
distribution.** The UI intentionally fails closed without the private export.
Do not create a Pages deployment until the exact public fields, attribution/logo
and publication approval are resolved.

The source `snapshot-contract.json` binds the local export manifest hash. Data
assets are verified with Web Crypto SHA-256 before use. Integrity against that
contract is not a digital signature or a grant of provider rights.

See [static demo instructions](../docs/STATIC_DEMO.md) for export, local serving,
field inventory, parity checks, supported scenarios and publication limits.
