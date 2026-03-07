# GarageBand Format Research

Open reverse engineering of the GarageBand `.band` file format — specifically the binary blob inside `projectData` that stores tracks, regions, tempo, and plugin state.

**The goal:** build a public map of the binary format so that tools like version control, diff viewers, and DAW bridges can read and write GarageBand projects programmatically.

---

## Why this exists

GarageBand's `.band` files are folder bundles containing a `projectData` file. The outer wrapper is NSKeyedArchiver (which we can decode with [`nska_deserialize`](https://github.com/avibrazil/NSKeyedArchiver)). But the core song data — tracks, regions, tempo — lives inside a proprietary binary blob called `DfLogicModelLogicSong` that Apple has never documented.

This project maps that blob systematically: make one change in GarageBand, diff the binary, record what moved. After enough experiments, patterns emerge and we can build a parser.

This research will feed directly into a project I am working on but the format map is useful to anyone building tools around GarageBand or Logic Pro.

---

## Current findings

See [`FINDINGS.md`](FINDINGS.md) for the human-readable summary of what has been confirmed so far.

Research data by GarageBand version lives in [`/research`](research/):

| Version | Arch | Experiments | Contributor |
|---|---|---|---|
| *(none yet — be the first!)* | | | |

---

## How it works

```
You make one change in GarageBand
        ↓
band_cartographer.py diffs the binary blobs
        ↓
research.json logs which byte ranges changed
        ↓
After many experiments, patterns emerge
        ↓
FINDINGS.md summarizes confirmed field locations
        ↓
parser.py (coming soon) reads those fields
```

---

## Setup

# Clone the repo
git clone https://github.com/Wes-Selman/band-cartographer
cd band-cartographer

# Install dependencies
pip3 install -r requirements.txt

---

## Running your first experiment

### 1. Copy and verify the canonical baseline

The repo includes `baseline.band` — a minimal GarageBand project everyone uses as their starting point. Copy it into a local experiments folder and verify it:

```bash
mkdir -p experiments
cp -r baseline.band experiments/baseline.band
python3 band_cartographer.py verify-baseline experiments/baseline.band
```

**Do not create your own baseline.** Starting from the same file is what makes results comparable across GarageBand versions and architectures.

### 2. Open the baseline in GarageBand

Double-click `experiments/baseline.band` to open it. **GarageBand rewrites the file the moment it opens it** — this is normal and expected. Every copy of GarageBand does this regardless of version. Your diffs are still valid because you use this same post-open file as the baseline for all your experiments.

If you run `verify-baseline` again after this first open you'll see a hash mismatch warning. That is fine — the script explains this and lets you continue.

### 3. Make one change

In GarageBand, make **exactly one change** from the list below. Save a copy with the canonical label name:

```bash
# Example: you added one audio track
cp -r ~/Music/GarageBand/MyChanged.band experiments/add-audio-track.band
```

See the full list of canonical experiments:
```bash
python3 band_cartographer.py list
```

### 3. Run the diff

```bash
python3 band_cartographer.py diff \
    experiments/baseline.band \
    experiments/add-audio-track.band
```

The results are automatically written to `research/<your-gb-version>/research.json`.

### 4. Batch process (once you have several files)

```bash
python3 band_cartographer.py batch experiments/
```

### 5. View findings

```bash
python3 band_cartographer.py report experiments/
```

---

## Canonical experiments

These are the 18 standard experiments. Use **exact label names** so results can be cross-referenced across GarageBand versions.

| Label | What to do |
|---|---|
| `add-audio-track` | Add one empty audio track |
| `add-midi-track` | Add one software instrument track |
| `delete-track` | Start with 2 tracks, delete one |
| `rename-track` | Rename a track |
| `reorder-tracks` | Drag one track above another |
| `add-region` | Drag a loop into an empty track |
| `move-region` | Move a region to a different bar |
| `resize-region` | Drag a region edge to make it longer |
| `delete-region` | Delete a region |
| `duplicate-region` | Option+drag to duplicate a region |
| `change-tempo-1bpm` | Change global tempo by 1 BPM |
| `change-time-sig-3-4` | Change time signature from 4/4 to 3/4 |
| `add-tempo-change-bar9` | Add a tempo change event at bar 9 |
| `change-track-volume` | Move a track's volume fader |
| `change-track-pan` | Move a track's pan knob |
| `mute-track` | Mute a track (M key) |
| `solo-track` | Solo a track (S key) |
| `add-plugin` | Add one effect plugin to a track |

---

## Contributing your results

Different GarageBand versions and Mac architectures (Intel x86_64 vs Apple Silicon arm64) may have different binary layouts. **Your results are valuable even if they look similar to existing ones.**

```bash
# Check what you have so far
python3 band_cartographer.py status experiments/

# Stage and push your research
python3 band_cartographer.py contribute experiments/
```

Then open a Pull Request. The script will give you the exact commit message to use.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for full details.

---

## What the research.json looks like

Each entry records one experiment — the label, the environment it was run on, and the exact byte ranges that changed:

```json
{
  "label": "add-audio-track",
  "description": "Add one empty audio track",
  "timestamp": "2026-03-07T14:00:00Z",
  "environment": {
    "garageband_version": "10.4.8",
    "architecture": "x86_64",
    "macos_version": "13.6",
    "CbVersion": 30000
  },
  "outer_diff": [],
  "inner_diff": {
    "size_delta": 512,
    "num_changed_ranges": 3,
    "changed_ranges": [
      {
        "offset_hex": "0x40",
        "length": 4,
        "as_uint32_le": "8",
        "as_float32": null
      }
    ]
  }
}
```

---

## For repo maintainers

### Setting up a new canonical baseline

1. Create the baseline project in GarageBand (one software instrument track, one MIDI region at bar 1, 120 BPM, nothing else)
2. Save it as `baseline.band` in the repo root
3. **Before opening it again**, generate the canonical hash:
   ```bash
   python3 band_cartographer.py generate-baseline-hash baseline.band
   ```
4. Paste the printed hash into `BASELINE_INNER_SHA256` in `band_cartographer.py`
5. Commit both files together:
   ```bash
   git add baseline.band band_cartographer.py
   git commit -m "baseline: add canonical baseline.band and hash"
   ```

The hash only verifies the inner binary blob — it will not match after GarageBand opens the file (GarageBand always rewrites on open). That is expected. The hash confirms contributors started from the right file before their first open.

---

- [nska_deserialize](https://github.com/avibrazil/NSKeyedArchiver) — the library used to decode the outer NSKeyedArchiver wrapper
- [Robert Heaton's Logic Pro synth file reverse engineering](https://robertheaton.com/2017/07/17/reverse-engineering-logic-pro-synth-files/) — the methodology this project is based on

---

## License

Research data (`research.json` files) is released under [CC0](https://creativecommons.org/publicdomain/zero/1.0/) — no rights reserved, use freely.

Code (`band_cartographer.py`) is MIT licensed.
