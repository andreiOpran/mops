# Raw collector (T-01)

Archives the TPBI GTFS-RT feeds (Vehicle Positions, Trip Updates) every 15 s and the static GTFS schedule, exactly as received (gzip-compressed). It does not interpret the data: arrival detection (US-02) and delay calculation (US-03) are developed in the Sprint and replay these files.

Technical task, not a User Story. Tests were written after the code (not TDD).

## Deployment

| | |
|---|---|
| VPS | `217.156.93.22` (Ubuntu 26.04 LTS, 2 vCPU, 2 GB RAM, 38 GB disk) |
| User | `mops` (SSH key only; root and password login are disabled) |
| Service | `stb-collector` (systemd, runs as system user `stbcollector`) |
| Code | `/opt/stb-collector` |
| Data | `/var/lib/stb-collector` |
| Running since | 2026-10-29 20:51 UTC |

## Output

Everything is under `/var/lib/stb-collector` (times in UTC):

| Path | Content |
|---|---|
| `raw/<feed>/YYYY-MM-DD/HH/YYYYMMDDTHHMMSSZ.pb.gz` | one file per new snapshot |
| `static/<timestamp>_<sha12>.zip` | one copy per distinct schedule version (checked every 6 h) |
| `polls/YYYY-MM-DD.jsonl` | one line per request: `saved`, `not_modified`, `error`, `disk_full` (source for data gaps, FR-06) |
| `status.json` | last successful poll per feed |

Requests send `If-None-Match` (ETag). An unchanged feed returns 304 and nothing is saved. A failed request is not retried immediately: the next poll happens 15 s later (NFR-02).

Measured volume: ~330 KB uncompressed per poll (both feeds), ~105 KB stored. About 0.6 GB per day on disk, ~3.3 GB per day of incoming traffic. At this rate the 38 GB disk lasts until about mid-December (see T-02).

## Configuration (environment variables)

| Variable | Default |
|---|---|
| `STB_DATA_DIR` | `/var/lib/stb-collector` |
| `STB_POLL_SECONDS` | `15` |
| `STB_STATIC_CHECK_SECONDS` | `21600` |
| `STB_MIN_FREE_GB` | `5` (below this limit nothing is saved and `disk_full` is logged) |
| `STB_USER_AGENT` | `stb-delay-monitor/0.1 (MOPS student project)` |

## Local tests

```bash
cd collector
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest --cov=archiver --cov-report=term-missing
```

## Team access

Each member uses their own SSH key (private keys are never shared):

1. Generate a key: `ssh-keygen -t ed25519 -f ~/.ssh/mops -C "<name>-mops"`
2. Send only `~/.ssh/mops.pub` to the VPS admin, who adds it on the VPS (as `mops`):
   `cat key.pub >> ~/.ssh/authorized_keys`
3. Add to `~/.ssh/config`:

   ```
   Host mops
       HostName 217.156.93.22
       User mops
       IdentityFile ~/.ssh/mops
       IdentitiesOnly yes
   ```

4. Connect: `ssh mops`. Reading the data does not need `sudo`.

Inspect a snapshot (the `peek` tool is already set up in the `mops` home directory):

```bash
~/peek-venv/bin/python ~/tools/peek.py latest vehiclePositions 3
~/peek-venv/bin/python ~/tools/peek.py latest tripUpdates 1
```

## Operations

```bash
systemctl status stb-collector
journalctl -u stb-collector -f
cat /var/lib/stb-collector/status.json
tail -n 4 /var/lib/stb-collector/polls/$(date -u +%F).jsonl
df -h /var/lib/stb-collector
grep -c '"error"' /var/lib/stb-collector/polls/$(date -u +%F).jsonl   # failed requests today
```

Copy the data to a local machine:

```bash
rsync -av mops:/var/lib/stb-collector/ ./data/
```

(`mops` is in the `stbcollector` group, which has read access to the data.)

## Installing or updating

Requirements: Ubuntu 26.04 LTS, an SSH key already added for root, at least ~60 GB of free disk.

From a local checkout of the repository:

```bash
rsync -av --exclude __pycache__ --exclude .venv --exclude .coverage collector/ root@<vps-ip>:/root/collector/   # first install
ssh root@<vps-ip> bash /root/collector/deploy/setup-vps.sh mops
```

The script:

- updates the system and enables automatic security updates;
- creates the admin user (the SSH key is copied from root);
- SSH with keys only, no root login, no passwords (checked with `sshd -T`);
- `ufw` firewall: only SSH allowed in;
- `fail2ban` for SSH;
- clock synchronisation (NTP);
- system user `stbcollector`, without a shell, which runs the collector;
- isolated systemd service (writes only to `/var/lib/stb-collector`, restarts automatically, NFR-01).

**Important:** do not close the current SSH session until you have checked, in a new terminal, that `ssh mops` works.

To update the code later (root login is disabled by then), copy `collector/` to the VPS as `mops` and run the script again with `sudo`:

```bash
rsync -av --exclude __pycache__ --exclude .venv --exclude .coverage collector/ mops:~/collector/
ssh -t mops sudo bash collector/deploy/setup-vps.sh mops
```
