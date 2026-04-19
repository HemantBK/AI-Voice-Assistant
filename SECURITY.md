# Security

## Supported versions

| Version | Supported |
|---|---|
| `main` | ✅ |
| tagged releases | latest minor only |

## Reporting a vulnerability

**Do not file a public issue.** Email the project maintainer (see `git log` for current address) or, if GitHub, use the "Report a vulnerability" flow under the Security tab.

Please include:

- A clear description of the issue.
- Reproduction steps (a minimal PoC is ideal).
- The commit SHA you tested against.
- Any relevant logs (redacted).

You'll get an acknowledgement within 72 hours. Fix timeline depends on severity; we aim for:

| Severity | Target |
|---|---|
| Critical (remote code exec, data loss) | 7 days |
| High (auth bypass, audio exfiltration) | 30 days |
| Medium | 60 days |
| Low | next minor release |

## Threat model (summary)

**In scope:**
- Unauthenticated access to `/api/*` and `/ws/voice` when `API_KEY` is set.
- Replay attacks against WS messages.
- Injection via user-supplied text reaching Ollama / Groq.
- Resource exhaustion (memory, CPU) from crafted audio inputs.
- Arbitrary file read via path injection in `PIPER_VOICE` or model paths.
- Voice cloning without consent.

**Out of scope (document your own stance):**
- Physical access to the host.
- Compromised underlying models (supply chain trust in Ollama, HF, etc.).
- Privilege escalation in the host OS.
- DDoS at the network layer.

## Hardening checklist for deployment

The repo ships with dev-friendly defaults. Before exposing the backend on a public network:

- [ ] Set `API_KEY` to a random ≥ 32-byte secret.
- [ ] Set `ALLOWED_ORIGINS` to the exact frontend origin(s). Remove `*`.
- [ ] Wire `require_api_key_ws` into the `/ws/voice` handshake (TODO in Phase F — see [phase-f-notes](docs/design/phase-f-notes.md)).
- [ ] Put the backend behind a TLS-terminating reverse proxy (Caddy / nginx / Traefik).
- [ ] Use a process manager (systemd / Kubernetes) with a non-root user.
- [ ] Rate-limit at the proxy in addition to the in-process limiter.
- [ ] Swap the in-memory rate limiter for Redis if running more than one replica.
- [ ] `LOG_FORMAT=json` and ship logs to your log pipeline.
- [ ] Run a dependency audit: `pip-audit` + `npm audit` (ideally in CI).
- [ ] Enable Dependabot (not yet configured; tracked).
- [ ] Review the voice-cloning consent flow against your jurisdiction's deepfake rules (see [phase-d-notes](docs/design/phase-d-notes.md)).

## Audio data handling

- In local mode (`LLM_PROVIDER=ollama`, default), mic audio is never transmitted outside the host.
- In Groq mode, the user's transcript (text, not audio) is sent to Groq's API per their ToS.
- Raw audio bytes are held in memory for the duration of one turn only. No disk writes unless `OPENVOICE_REFERENCE_WAV` is enrolled (explicit, opt-in, consent-gated).
- We do **not** log transcripts at any level by default. If you want them, write a logging hook — don't expect one.

## Cryptographic practices

- `API_KEY` comparison uses `secrets.compare_digest` — constant-time.
- No secrets are generated or stored by this codebase. Bring your own via env or a secret manager.
- TLS is expected to terminate at the proxy. The backend does not serve HTTPS directly.
