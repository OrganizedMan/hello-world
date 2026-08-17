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

### Brush

Not in Homebrew, but it **does** ship an Apple-silicon binary. As of v0.3.0 the
release asset is `brush-app-aarch64-apple-darwin.tar.xz` — note `.tar.xz`, not
`.tar.gz`.

```bash
cd ~/Downloads
curl -L -O https://github.com/ArthurBrussee/brush/releases/latest/download/brush-app-aarch64-apple-darwin.tar.xz
tar -xf brush-app-aarch64-apple-darwin.tar.xz
ls                                   # confirm the extracted binary's name
```

This is a `cargo-dist` release, so it unpacks into a folder rather than dropping
a bare binary, and the executable inside is `brush_app` — underscore, not
hyphen. Locate it rather than guessing:

```bash
find . -maxdepth 2 -type f -perm -u+x -name 'brush*'
# → ./brush-app-aarch64-apple-darwin/brush_app
```

Install it as `brush`, which is the name Amber's backend looks for. Note that
**`/usr/local/bin` does not exist on many Apple-silicon Macs** — Homebrew moved
to `/opt/homebrew` — so create it first or `mv` fails with a confusing
"No such file or directory" that appears to blame the source file:

```bash
sudo mkdir -p /usr/local/bin
xattr -d com.apple.quarantine ./brush-app-aarch64-apple-darwin/brush_app 2>/dev/null || true
chmod +x ./brush-app-aarch64-apple-darwin/brush_app
sudo mv ./brush-app-aarch64-apple-darwin/brush_app /usr/local/bin/brush
brush --help
```

`/usr/local/bin` is in `/etc/paths` by default, so it joins your PATH as soon as
it exists. If you have Homebrew and would rather skip `sudo`, its bin directory
is already yours to write to:

```bash
mv ./brush-app-aarch64-apple-darwin/brush_app "$(brew --prefix)/bin/brush"
```

The `xattr` line matters: without it Gatekeeper refuses an unsigned download
with "the developer cannot be verified", which reads like a corrupt file rather
than a permissions flag. If it still complains, `xattr -c "$(which brush)"`
clears every attribute.

Record the pin while you are here — a hash of the exact binary is a stronger
pin than a version string:

```bash
shasum -a 256 "$(which brush)"
```

Brush runs headless as a CLI; `--with-viewer` opens the UI alongside it.

**Save the `brush --help` output.** Amber discovers Brush's flags rather than
assuming them, so if the real names differ from the candidates in
`amber/backends/trainers/brush.py`, that text is what you need to correct them.

#### If the download 404s

The asset name may have changed in a later release. Ask GitHub directly rather
than hunting through the releases page:

```bash
curl -s https://api.github.com/repos/ArthurBrussee/brush/releases/latest \
| python3 -c "import sys,json;d=json.load(sys.stdin);print('tag:',d.get('tag_name','NONE'));[print('  ',a['name']) for a in d.get('assets',[])]"
```

Confirm your own architecture too — `arm64` means Apple silicon:

```bash
uname -m
```

#### Reading the asset names

Rust binaries are named by target triple, `architecture-vendor-os`:

| In the filename | Meaning | Want it? |
| --- | --- | --- |
| `aarch64-apple-darwin` | Apple silicon Mac | **yes** |
| `arm64` + `macos`/`darwin` | same, informal naming | **yes** |
| `universal` / `universal2` | Intel **and** Apple silicon | yes |
| `x86_64-apple-darwin` | Intel Mac | no — wrong chip |
| `unknown-linux-gnu`, `pc-windows-msvc` | Linux, Windows | no |
| `Source code (zip)` / `(tar.gz)` | GitHub adds these to *every* release | **no — not a binary** |

That last row is the common trap: those two entries exist on every GitHub
release whether or not the project ships binaries, so their presence tells you
nothing.

#### If a matching binary exists

macOS quarantines downloaded binaries and Gatekeeper will refuse to run them
("the developer cannot be verified"). Strip the flag:

```bash
cd ~/Downloads
tar -xzf brush-*.tar.gz          # or: unzip brush-*.zip
xattr -d com.apple.quarantine brush 2>/dev/null || true
chmod +x brush
sudo mv brush /usr/local/bin/
brush --help
```

#### If there is no matching binary

This is the likely outcome and it is not a problem. Build from source:

```bash
brew install rust
git clone https://github.com/ArthurBrussee/brush.git ~/Developer/brush
cd ~/Developer/brush
cargo build --release
sudo cp target/release/brush /usr/local/bin/
brush --help
cd ~/Developer/hello-world/amber
```

The first `cargo build --release` compiles every dependency and takes a while.
Warnings are expected; you want `Finished` at the end and no `error:` lines.

**Save the output of `brush --help` somewhere.** Amber discovers Brush's flags
rather than assuming them, and if the flag names differ from the candidates in
`amber/backends/trainers/brush.py`, that help text is what you need to fix it.

### SplatTransform

Confirmed published as `@playcanvas/splat-transform`:

```bash
brew install node
npm install -g @playcanvas/splat-transform
splat-transform --help
```

Usage is `splat-transform input [actions] output [actions]`, and the output
format follows the output file's extension — so `scene.sog` produces SOG with no
format flag needed.

The spherical-harmonic control is `-H, --filter-harmonics <0|1|2|3>`, which
removes SH bands above *n*. That is equivalent to setting the delivery SH
degree, and it is what Amber's delivery profiles use: `mobile-sh0` passes 0,
`mobile-sh2` passes 2. Milestone 2 measures which one to default to on your
actual iPhone.

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
