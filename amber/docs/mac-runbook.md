# Mac runbook — setting up and executing M0

Step-by-step for an Apple-silicon Mac. Work through the phases in order; each
ends with a checkpoint that tells you whether to continue.

Three commands are marked **VERIFY** because the exact package name or URL may
have changed since this was written. Check the linked page rather than trusting
the command blindly — and once you confirm the real one, correct it here.

---

## Phase 0 — get the code

```bash
cd ~/Developer 2>/dev/null || mkdir -p ~/Developer && cd ~/Developer
git clone https://github.com/OrganizedMan/hello-world.git
cd hello-world
git checkout claude/build-to-plan-z8y813
cd amber
```

**Checkpoint:** `ls` shows `AGENTS.md`, `amber/`, `docs/`, `scripts/`, `tests/`.

---

## Phase 1 — Python environment

macOS ships an older Python. Amber needs 3.11+.

```bash
python3 --version
```

If that reports less than 3.11:

```bash
brew install python@3.12
```

Then:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e '.[dev]'
```

**Checkpoint — the test suite must pass before you install anything else.**
This proves the logic works independently of the external toolchain:

```bash
python -m pytest tests -q
```

Expect `~180 passed` with a few skips (the skips are the FFmpeg-dependent
tests, which will start running in Phase 2). If tests fail here, stop and fix
that first — do not debug a tool problem and a code problem at the same time.

---

## Phase 2 — external tools

### FFmpeg and COLMAP

```bash
brew install ffmpeg colmap
```

This takes a while; COLMAP is a large build. Then:

```bash
ffmpeg -version | head -1
ffprobe -version | head -1
colmap help
```

### Brush — **VERIFY**

Not in Homebrew. Check <https://github.com/ArthurBrussee/brush> for a
prebuilt Apple-silicon release first; if there is one, download it and put the
binary on your PATH:

```bash
# after downloading and unpacking the release
sudo mv brush /usr/local/bin/
chmod +x /usr/local/bin/brush
brush --help
```

If there is no release binary, build from source (needs Rust):

```bash
brew install rust
git clone https://github.com/ArthurBrussee/brush.git ~/Developer/brush
cd ~/Developer/brush && cargo build --release
sudo cp target/release/brush /usr/local/bin/
cd ~/Developer/hello-world/amber
```

**Save the output of `brush --help` somewhere.** Amber discovers Brush's flags
rather than assuming them, and if the flag names differ from the candidates in
`amber/backends/trainers/brush.py`, that help text is what you need to fix it.

### SplatTransform — **VERIFY**

An npm package from PlayCanvas. Check
<https://github.com/playcanvas/splat-transform> for the published name:

```bash
brew install node
npm install -g @playcanvas/splat-transform
splat-transform --help
```

### Checkpoint

```bash
./scripts/doctor.sh
```

This prints what is installed and what each build supports, and writes
`docs/doctor-report.json`. It exits non-zero until everything is present.

Read the COLMAP line carefully. It reports which `max_image_size` option name
your build uses and that option's CLI default — usually 3200, meaning **4K
input is downscaled internally unless you raise it**. That number matters for
Gate B, so record it.

**Now record every version in `docs/feasibility-results.md` §0.** Do this before
running anything else; it is the pin for everything that follows.

---

## Phase 3 — Gate A, part 1: pose on public control data

The point of Gate A is to separate *your* problems from *the tools'* problems
using data with a known-good answer.

### Get the control scene — **VERIFY**

Get the South Building dataset URL from
<https://colmap.github.io/datasets.html>:

```bash
mkdir -p ~/amber-control && cd ~/amber-control
# substitute the real URL from the datasets page:
curl -L -O https://demuc.de/colmap/datasets/south-building.zip
unzip -q south-building.zip
ls south-building
```

**Record the license and the retrieval URL and date in
`docs/feasibility-results.md` before using the data.** Do not skip this — the
plan requires it and it takes thirty seconds.

### Run pose from the raw images

```bash
cd ~/amber-control/south-building
mkdir -p amber-run/sparse

time colmap feature_extractor \
  --database_path amber-run/database.db \
  --image_path images \
  --ImageReader.single_camera 1

time colmap exhaustive_matcher \
  --database_path amber-run/database.db

time colmap mapper \
  --database_path amber-run/database.db \
  --image_path images \
  --output_path amber-run/sparse
```

Check how many images registered:

```bash
colmap model_analyzer --path amber-run/sparse/0
```

**Checkpoint:** roughly **128 of 128** registered. The floor is 126.

- **Fewer than 126?** Your COLMAP install or build is the problem, not your
  footage. Fix that before touching Gate B.
- **Around 128?** The pose toolchain works. Record the timings and the
  registered count in `docs/feasibility-results.md` §A1–A3.

### Benchmark the global mapper on a copy of the same database

Copying the database is what makes this a mapper comparison rather than a
comparison of two different pipelines:

```bash
cp amber-run/database.db amber-run/database-global.db
mkdir -p amber-run/sparse-global
colmap view_graph_calibrator --database_path amber-run/database-global.db || true
time colmap global_mapper \
  --database_path amber-run/database-global.db \
  --image_path images \
  --output_path amber-run/sparse-global
colmap model_analyzer --path amber-run/sparse-global/0
```

Record both results side by side. Faster is not automatically better — a lower
registered count or worse reprojection error outranks speed.

---

## Phase 4 — Gate A, part 2: train from the *reference* model

This deliberately bypasses Amber's pose stage, so a failure here means the
trainer or the toolchain, never your camera solve.

```bash
cd ~/amber-control/south-building
mkdir -p brush-dataset/sparse
cp -R images brush-dataset/images
cp -R sparse/0 brush-dataset/sparse/0     # the dataset's own reference model
```

Then run Brush against it. The exact flags depend on your build — use the
`--help` output you saved:

```bash
brush brush-dataset --export-path ~/amber-control/brush-out
```

Watch memory in another terminal while it runs:

```bash
# in a second Terminal tab
sudo memory_pressure -l warn
```

**Checkpoint:** a `.ply` appears in `~/amber-control/brush-out` and you did not
exhaust 16 GB. Record peak memory, wall clock, and the output size.

If Brush fails, diagnose it here. Do not move to your own footage with a broken
trainer.

### Convert and view

```bash
splat-transform ~/amber-control/brush-out/*.ply ~/amber-control/scene.sog
ls -lh ~/amber-control/scene.sog
```

Open the `.ply` or `.sog` in a local SuperSplat build or the SuperSplat web
editor, on the Mac and then on your iPhone. Record file size, whether it
loaded, load time, and the frame-rate range you observe. Note your iPhone's
actual Safari version.

**Gate A is now complete.** Fill in every §A table before continuing.

---

## Phase 5 — Gate B: your own captures

Read `docs/capture-guide.md` first. The single most important thing: **walk
around the subject; do not stand still and pan.**

Record two videos on the iPhone 16 Pro, 1× rear camera, AE/AF locked, ordinary
Video mode:

1. a textured tabletop object, full orbit, ~45 s
2. a small room or outdoor sitting area, ~60–90 s

AirDrop them to the Mac. Keep them **outside this repository** — the
`.gitignore` blocks video, but do not rely on that.

```bash
cd ~/Developer/hello-world/amber
source .venv/bin/activate
mkdir -p ~/amber-captures

amber process ~/amber-captures/object-01.MOV \
  --capture-class object \
  --title "Tabletop object, August 2026"
```

Then the room:

```bash
amber process ~/amber-captures/room-01.MOV \
  --capture-class room \
  --title "Living room, August 2026"
```

### Reading the outcome

Whatever happens, inspect it:

```bash
amber list
amber inspect "$(amber list | grep -m1 '^  /' | tr -d ' ')" --verify
```

Or point at the scene directory directly:

```bash
amber inspect ~/Pictures/Amber\ Memories/<scene-dir> --json | less
```

**If the pose gate fails**, the failure names a specific cause — most often
`insufficient_translation`, meaning the camera rotated but did not move through
space. That is real information about the footage. You get **one** deliberate
recapture per scene under the effort bound; use it deliberately, not
reflexively.

**If a stage errors on a tool problem**, fix and resume without redoing the
earlier work:

```bash
amber retry ~/Pictures/Amber\ Memories/<scene-dir> --from train
```

### Storage

```bash
amber inspect <scene> | tail -20
amber prune <scene> --dry-run
```

Record the byte counts in `docs/feasibility-results.md`. These are what set the
M1 retention default, so they need to be real numbers from these two captures.

---

## Phase 6 — decide, and commit the evidence

Log every session in the effort ledger at the bottom of
`docs/feasibility-results.md` as you go. Six sessions, three active hours each,
two for Gate A and four for Gate B.

At the bound — even if another parameter is tempting — write
`docs/decisions/0004-m0-outcome.md` choosing **proceed**, **re-scope**, or
**stop**, using the ADR format in `AGENTS.md` rule 18. Then move
`0001-sfm-pipeline.md` from Proposed to Accepted with the feature, matcher,
mapper, and resolution defaults your measurements actually chose.

```bash
git add docs/
git commit -m "Record M0 Gate A and Gate B results"
git push
```

Do not commit the footage or the scene archives.

---

## Quick reference

| Command | Purpose |
| --- | --- |
| `./scripts/doctor.sh` | what is installed, what each build supports |
| `amber process <video> --capture-class room` | full pipeline |
| `amber inspect <scene> --verify` | stages, split, storage, checksums |
| `amber retry <scene> --from <stage>` | resume without redoing earlier stages |
| `amber prune <scene> --dry-run` | what could be freed, and its regeneration cost |
| `python -m pytest tests -q` | the suite; run after any code change |
