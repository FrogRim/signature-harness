# Resume Check Contract - <resume-check-id>

Resume checks are allowlisted contracts, not shell command strings.

```yaml
id:
argv: []
shell: false
env_from_user: []
timeout_sec:
allowed_egress: []
writable_paths:
  - <sandbox-tmp>
sandbox_required: true
records_secret: false
```

## Security Rules

- Do not format user input into `argv`.
- Inject secrets only through isolated subprocess environment variables.
- Reject shell metacharacters: `;`, `&&`, `|`, backticks, `$(`, `>`, `<`, newline, or carriage return.
- `shell` must be `false`.
- Run in a least-privilege sandbox.
- Network is denied unless explicitly listed in `allowed_egress`.
- Write access is limited to sandbox temp and declared evidence outputs.
- On security rejection, abort the current run and write a security incident receipt.
