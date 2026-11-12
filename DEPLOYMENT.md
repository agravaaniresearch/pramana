# Deploying Pramana

This file is self-contained. An engineer can deploy the service from it without reading the rest of the repository.

> **What you are deploying.** A small, read-only HTTP service that answers "what did this rulebook say at this moment" and "has the record been altered", over a ledger file. The bundled data is **synthetic and for illustrative purposes only**. It is a research prototype, not a production legal system. See "What production would still need" at the end.

## 1. What runs

| Item | Detail |
|---|---|
| Language | Python 3.10 or later |
| Runtime dependencies | None (standard library only) |
| Process | One process, `python -m pramana.server` |
| Port | `PORT`, default 8080 |
| State | Two files: an append-only ledger (`.jsonl`) and a corpus sidecar (`.json`) |
| Network | Inbound only. The service makes no outbound calls. |
| Write path | None over HTTP. Publishing is the separate `pramana publish` command on the host. |

## 2. Configuration

| Variable | Default | Meaning |
|---|---|---|
| `PORT` | `8080` | Listen port. |
| `PRAMANA_LEDGER` | `data/synthetic_ledger.jsonl` | Path to the ledger. |
| `PRAMANA_CORPUS` | `data/synthetic_corpus.json` | Path to the corpus sidecar (instrument titles, shadow circulars, fact patterns). |
| `PRAMANA_LOG` | unset | Set to any value to log requests to stderr. |

The service loads both files **once at start**. Restart it (or send it a restart through your supervisor) after publishing. There is no hot reload, by design, so a running instance always serves a state that passed verification at start.

## 3. Option A: container

```bash
docker build -t pramana .
docker run --rm -p 8080:8080 pramana
python scripts/smoke_test.py http://127.0.0.1:8080
```

The image bakes in the synthetic data under `/data`. To serve your own files, mount them **read-only**:

```bash
docker run --rm -p 8080:8080 \
  -v /srv/pramana/ledger.jsonl:/data/ledger.jsonl:ro \
  -v /srv/pramana/corpus.json:/data/corpus.json:ro \
  pramana
```

The image runs as an unprivileged user (uid 10001) and has a health check on `/healthz`.

> **Note on testing.** The Dockerfile was written but could **not be built in the environment where this prototype was authored** (no container daemon was available). The same steps it performs (install the package, write the synthetic data, start the server, run the smoke test) were run successfully in a clean virtual environment, which is option B. If the build fails on your side, option B is the fallback and the first place to look for the difference.

## 4. Option B: virtual environment, no container

```bash
python3 -m venv /opt/pramana/venv
/opt/pramana/venv/bin/pip install /path/to/pramana          # the repository checkout
mkdir -p /var/lib/pramana
/opt/pramana/venv/bin/pramana build-synthetic --out /var/lib/pramana   # demo data only
export PRAMANA_LEDGER=/var/lib/pramana/synthetic_ledger.jsonl
export PRAMANA_CORPUS=/var/lib/pramana/synthetic_corpus.json
export PORT=8080
/opt/pramana/venv/bin/python -m pramana.server
```

For a supervised service use `deploy/pramana.service` (systemd; edit the paths, then `systemctl enable --now pramana`). It runs with `NoNewPrivileges`, a read-only view of the data directory and a private temp directory.

## 5. Reverse proxy and TLS

The service speaks plain HTTP and has no authentication, because it only serves public, read-only content. Put it behind a reverse proxy that terminates TLS. `deploy/nginx.conf` is a starting point and denies every method except GET. Certificates are yours to provide.

## 6. Endpoints

All responses are JSON. All timestamps in requests must carry an explicit offset; URL-encode `+` as `%2B`.

| Method and path | Parameters | Returns |
|---|---|---|
| `GET /healthz` | none | `{"status":"ok","entries":N}` |
| `GET /head` | none | The anchor: `{"length":N,"head_hash":"..."}` |
| `GET /verify` | optional `anchor` (JSON) | Chain verification result. With `anchor`, also detects truncation and rewritten history. |
| `GET /instruments` | none | Instrument list. |
| `GET /asof` | `instrument`, `at`, optional `regime` (`tora` or `legacy`), optional `known_at` | The instrument as it stood at `at`, with per-clause provenance. |
| `GET /exposure` | `instrument`, `act`, `hindsight` | Law visible to a citizen at `act` versus law applied by `hindsight`, with causes. |

Errors: `400` for a missing or malformed parameter, `404` for an unknown path, `501` for any non-GET method.

Example:

```bash
curl --noproxy '*' "http://127.0.0.1:8080/asof?instrument=SYN-FIL-02&at=2024-12-12T17:01:00%2B05:30"
```

## 7. Smoke test

```bash
python scripts/smoke_test.py http://127.0.0.1:8080
```

It checks that the service is healthy, that the chain verifies, that the head anchor verifies, and, on the bundled synthetic data, that the law at 4:00 pm and 5:01 pm on 12 December 2024 are the 60-day and 45-day rules and that the earlier act's governing law is stable. It exits non-zero on any failure, so it can gate a rollout. On any other corpus it runs the generic checks and skips the synthetic-specific ones.

## 8. Publishing and the anchor

Publishing is an operator action on the host that holds the ledger, not an HTTP call:

```bash
pramana --ledger /var/lib/pramana/ledger.jsonl publish --diff amendment.json
```

`amendment.json` must match `schemas/diff.schema.json`. The command takes an exclusive file lock, verifies the existing chain, refuses to append to a broken ledger, assigns the **system clock** as the publication time, appends one line and fsyncs. It never rewrites existing lines. Restart the service afterwards.

**Publish the anchor.** After each publication run `pramana --ledger ... anchor` and record the output somewhere the ledger's operator does not control (an independent register, a notice board, a second organisation). Without this, a fully re-hashed history and a truncated tail are invisible: the test bed measured 0 of 1000 detections for each. With it, all eight tested attacks were caught in every trial. To check at any time:

```bash
pramana --ledger /var/lib/pramana/ledger.jsonl verify --anchor '{"length":15,"head_hash":"..."}'
```

## 9. Operations

- **Backups.** Copy the ledger file. It is append-only; any prefix of it is a valid ledger.
- **Rollback.** There is none, by design. A mistake is corrected by publishing a new amendment.
- **Permissions.** The service needs read access to the two files and nothing else. Only the publisher account needs write access to the ledger and its `.lock` file.
- **Clock.** Keep the host clock synchronised (NTP). The publication time is the host's clock, and the ledger refuses a time earlier than its head, so a clock that jumps backwards will block publishing until it catches up.
- **Resources.** The service holds the whole ledger in memory and verification is linear in its length. The synthetic ledger is a few kilobytes. It has not been tested at the scale of a national rulebook.

## 10. Troubleshooting

| Symptom | Likely cause |
|---|---|
| `ClockRegression` on publish | Host clock is behind the last entry. Fix NTP; do not edit the ledger. |
| `refusing to append to a ledger that fails verification` | The file has been altered. Run `pramana verify` to find the entry, restore from backup. |
| `400 missing parameter` | A required query parameter is absent. |
| `400 timestamp must carry a timezone offset` | Add `Z` or `+05:30`. Remember to URL-encode `+`. |
| Service shows old data after a publish | It loads at start. Restart it. |
| Smoke test fails only on the 4:00 pm checks | You are serving a different corpus than the synthetic one. Treat as a skip. |

## 11. What production would still need

None of these exist in the prototype.

1. **Authenticated publication**: named publishing authorities, signing keys held in an HSM or equivalent, and an approval workflow.
2. **An independent anchor service** and, ideally, an independent trusted timestamp.
3. **A Merkle-tree ledger** with signed heads and compact inclusion proofs, so one clause can be verified without the whole history.
4. **High availability and mirrors**, since the point is that citizens can always read the law.
5. **A legal definition of publication** and the policy decisions in `POLICY.md`.
6. **Scale testing** and a real data-migration path from existing rule repositories.

*Code and runs are synthetic and for illustrative purposes only.*
