# Resume Check Contract - <resume-check-id>

Resume checks are allowlisted contracts, not shell command strings.

```yaml
id:
argv: []
shell: false
env_from_user: []
timeout_sec:
allowed_egress: []
declared_evidence_outputs: []
writable_paths:
  - <sandbox-tmp>
sandbox_required: true
records_secret: false
```

## Security Rules

- Do not format user input into `argv`.
- Inject secrets only through isolated subprocess environment variables.
- Bind the contract to a blocked receipt with `resume_check_contract_sha256`; validating an arbitrary well-formed JSON contract is not enough.
- Reject shell metacharacters: `;`, `&&`, `|`, `&`, backticks, `$(`, `%`, `^`, `!`, `>`, `<`, newline, or carriage return.
- Reject `.bat`, `.cmd`, `.ps1`, and known Windows script shims such as `npm`, `npx`, `pnpm`, and `yarn`.
- `shell` must be `false`.
- Run in a least-privilege sandbox.
- Network is denied unless explicitly listed in `allowed_egress` as `host:port` with port `1..65535`.
- Write access is limited to `<sandbox-tmp>` and `declared_evidence_outputs`.
- On security rejection, abort the current run and write a security incident receipt.
