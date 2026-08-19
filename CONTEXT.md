# ARIA-ET Context

Last updated: 2026-08-19

## Current State

This repo implements ARIA eye-tracking acquisition tasks using PsychoPy and the
Tobii Pro SDK, with export from raw ARIA acquisition artifacts to BIDS
eyetracking files.

Primary runtime commands:

- `aria-et check-eyetracker`
- `aria-et calibrate-eyetracker`
- `aria-et run-am`
- `aria-et run-si`
- `aria-et run-ss`
- `aria-et run-plr`
- `aria-et export-bids`

The lab Mac is using:

- Python: `/Users/scotterik/miniforge3/envs/aria-et_310/bin/python`
- Tobii SDK: `2.1.0.1`
- Tracker: Tobii Pro Spectrum `TPSP1-010214213025`
- Tracker address: `tobii-prp://169.254.10.180`
- Stimulus display: PsychoPy screen `1`, fullscreen `1920x1080`
- Data root: `/Users/scotterik/aria-et-data`

## Recent Design Change

The gaze recording path was hardened in two commits:

- `c797bee Batch Tobii gaze file flushes`
- `2333e4f Move Tobii gaze writes off SDK callback`

Before these changes, the Tobii SDK callback serialized each gaze sample to JSON,
wrote a row to `gaze.jsonl`, and flushed frequently in the callback path.

Current behavior:

```text
Tobii SDK callback:
  capture received_at
  enqueue raw gaze sample with put_nowait()
  return quickly

Writer thread:
  drain bounded queue
  JSON serialize samples
  write one JSONL row per sample
  flush every 250 samples or 0.5 s
  drain and flush on clean stop
```

This preserves the existing raw data format while reducing Python allocation,
JSON serialization, and file I/O inside the SDK callback thread.

Session logs now prefix each captured stdout/stderr line and uncaught traceback
line with a local wall-clock ISO timestamp, making `session.log` easier to align
with `events.jsonl`, `gaze.jsonl`, PsychoPy warnings, and macOS crash reports.

Tobii run sessions now record calibration provenance in `session.json` when a
calibration artifact exists under the same sourcedata subject/session directory:
`sourcedata/sub-<subject>/ses-<session>/calibrations/calibration-*/calibration.json`.
The stored provenance includes relative artifact paths, calibration timestamp,
method, tracker metadata, and the full calibration metadata payload. Dry runs
with `--tracker none` omit calibration provenance.

Relevant files:

- `src/aria_et/eyetracker.py`
- `src/aria_et/session.py`
- `tests/test_eyetracker.py`
- `tests/test_session.py`

Validation after the design change:

```text
191 passed, 7 skipped
```

## Data Validation Notes

### `sub-scott/ses-01/task-static-social-scenes_run-02`

This was rerun after moving gaze writes off the SDK callback. It completed
without crashing.

```text
events.jsonl: 26 events
gaze.jsonl: 189,704 samples
duration by Tobii system timestamp: 316.522 s
sample rate: ~599.3 Hz
last event: static-social-scenes.ended, trial_count=12
```

### `sub-abby/ses-01`

Subset of the battery was run with one macOS segfault during Activity Monitoring.

Raw data summary:

```text
ActivityMonitoring
  incomplete: crashed after starting am-08
  events: 30
  gaze samples: 122,517
  rate: ~598 Hz

SocialInteractive
  complete: 4 trials
  events: 10
  gaze samples: 85,072
  rate: ~599 Hz

StaticSocialScenes
  complete: 4 trials
  events: 10
  gaze samples: 65,724
  rate: ~598 Hz

PupillaryLightReflex
  complete: 4 trials
  events: 26
  gaze samples: 36,349
  rate: ~595 Hz
```

The real BIDS export for `sub-abby/ses-01` is present under:

```text
/Users/scotterik/aria-et-data/bids/sub-abby/ses-01/beh
```

Raw-to-BIDS count check:

```text
ActivityMonitoring     raw 122,517  eye1 122,517  eye2 122,517
PupillaryLightReflex   raw  36,349  eye1  36,349  eye2  36,349
SocialInteractive      raw  85,072  eye1  85,072  eye2  85,072
StaticSocialScenes     raw  65,724  eye1  65,724  eye2  65,724
```

The BIDS validator reports only recommended-metadata warnings for `sub-abby`.
The whole BIDS root still has an unrelated real validator error from an earlier
test session named `ses-flush-test`; BIDS session labels cannot contain `-`.

## Known Crash

Observed on macOS during:

```text
sub-abby/ses-01/task-activity-monitoring_run-01
```

The run crashed after completing `am-07` and starting `am-08`. The macOS
diagnostic report signature:

```text
EXC_BAD_ACCESS / SIGSEGV
faulting frame: glDeleteBuffers
```

This resembles earlier macOS PsychoPy/OpenGL finalizer crashes
(`glDeleteBuffers` / `glDeleteTextures`). We are parking deeper investigation
unless the same issue appears on the production Windows laptop.

The local crash note and copied `.ips` are under ignored `issues/`:

```text
issues/macos-psychopy-opengl-segfault-2026-08-19.md
issues/crash-reports/python3.10-2026-08-19-121231.ips
```

Because `issues/` is ignored by `.gitignore`, these files are preserved locally
but not committed.

## BIDS Export

Per-run export command:

```bash
python -m aria_et.cli export-bids \
  --input /path/to/task-*_run-* \
  --output /Users/scotterik/aria-et-data/bids
```

Batch export pattern:

```bash
PY=/Users/scotterik/miniforge3/envs/aria-et_310/bin/python
OUT=/Users/scotterik/aria-et-data/bids

find /Users/scotterik/aria-et-data/sourcedata/sub-<subject>/ses-<session> \
  -mindepth 1 -maxdepth 1 -type d -name 'task-*_run-*' | sort | while IFS= read -r run_dir; do
    "$PY" -m aria_et.cli export-bids --input "$run_dir" --output "$OUT"
  done
```

Validate:

```bash
/Users/scotterik/miniforge3/envs/aria-et_310/bin/bids-validator-deno /Users/scotterik/aria-et-data/bids
```

Expected current warnings:

- missing `README`
- missing or sparse `Authors`
- recommended `License`, `SourceDatasets`, `HEDVersion`
- recommended task sidecar metadata: `Instructions`, `TaskDescription`,
  `InstitutionName`, etc.

Known current error outside `sub-abby`:

```text
sub-staff/ses-flush-test
```

Use BIDS-safe session labels such as `flushtest`, not `flush-test`.

## Open Work

- Subscribe to Tobii buffer-overflow notifications and record any occurrence in
  session artifacts.
- Make child-friendly calibration responsive to early gaze by collecting after a
  short dwell delay and retrying until success or timeout.
- Decide whether optional Tobii SDK streams should be recorded in production:
  eye openness, user position guide, eye images, external signal, time
  synchronization, stream errors, tracker notifications.
- Build the Qt GUI layer with a dry-run launch path backed by a fake/no-tracker
  backend.

## Practical Production Notes

- Use normal Terminal for tracker operations. Codex sandboxed runs may not see
  tracker network discovery.
- For dry runs, use `--tracker none`.
- For real runs, use the explicit tracker address:

```bash
--tracker tobii --address tobii-prp://169.254.10.180
```

- Avoid hyphens in BIDS entity labels for subject/session/run.
- Treat incomplete runs as exportable but not analytically complete.

## Hardware Smoke Tests

Opt-in hardware smoke tests live in:

```text
tests/test_hardware_smoke.py
```

They are marked `requires_eyetracker` and skipped during normal test runs. These
tests check tracker connection, run two acquisition trials for AM/SI/SS/PLR,
verify raw `session.json`, `tracker.json`, `events.jsonl`, `gaze.jsonl`, and
`session.log`, export each smoke run to BIDS, and confirm BIDS eye1/eye2 physio
row counts match raw gaze sample counts.

Run on the lab machine with:

```bash
ARIA_ET_HARDWARE=1 \
ARIA_ET_TRACKER_ADDRESS=tobii-prp://169.254.10.180 \
/Users/scotterik/miniforge3/envs/aria-et_310/bin/python -m pytest \
  -m requires_eyetracker tests/test_hardware_smoke.py
```

Useful optional environment variables:

```bash
ARIA_ET_SMOKE_SUBJECT=smoke
ARIA_ET_SMOKE_SESSION=hardware
ARIA_ET_SMOKE_TRIAL_LIMIT=2
ARIA_ET_PSYCHOPY_SCREEN=1
ARIA_ET_SCREEN_RESOLUTION=1920x1080
ARIA_ET_SCREEN_SIZE_METERS=0.527x0.296
ARIA_ET_SCREEN_DISTANCE_METERS=0.65
ARIA_ET_SMOKE_OUTPUT_ROOT=/Users/scotterik/aria-et-data/smoke-tests/sourcedata
ARIA_ET_SMOKE_BIDS_ROOT=/Users/scotterik/aria-et-data/smoke-tests/bids
```
