# GarageBand Format Research

Open reverse engineering of the GarageBand `.band` file format — specifically the binary blob inside `ProjectData` that stores tracks, regions, tempo, and plugin state.

**The goal:** build a public map of the binary format so that tools like version control, diff viewers, and DAW bridges can read and write GarageBand projects programmatically.

---

## Why this exists

GarageBand's `.band` files are folder bundles containing a `ProjectData` file. On GarageBand 10.4+, this is a raw proprietary binary starting with the magic bytes `gnoS` ("Song" reversed). On older versions it is wrapped in NSKeyedArchiver (decodable with [`nska_deserialize`](https://github.com/avibrazil/NSKeyedArchiver)). Either way, the core song data — tracks, regions, tempo, plugin chains — lives inside an undocumented binary format that Apple has never published.

This project maps that binary systematically: make one change in GarageBand, diff the binary, record what moved. After enough experiments, patterns emerge and we can build a parser.

This research feeds directly into a project I am working on but the format map is useful to anyone building tools around GarageBand or Logic Pro.

---

## Current findings

See [`FINDINGS.md`](FINDINGS.md) for the human-readable summary of what has been confirmed so far.

Research reports by GarageBand version:

| Version | Arch | Experiments | Contributor |
|---|---|---|---|
| 10.4.8 | arm64 | 18/18 | Wes Selman |

---

## How it works

```
You make one change in GarageBand
        ↓
band_cartographer.py diffs the binary blobs
        ↓
Noise mask filters out always-changing bytes (timestamps, counters)
        ↓
report.txt logs which meaningful byte ranges changed
        ↓
After many experiments, patterns emerge
        ↓
FINDINGS.md summarizes confirmed field locations
        ↓
parser.py (coming soon) reads those fields
```

---

## Setup

```bash
# Clone the repo
git clone https://github.com/Wes-Selman/band-cartographer
cd band-cartographer

# Install dependencies
pip3 install -r requirements.txt
```

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

### 3. Build your noise mask

GarageBand rewrites a large number of byte ranges on every save regardless of what the user changed — timestamps, session counters, internal checksums. Without filtering these out, every experiment produces tens of thousands of spurious changed ranges that obscure the real signal.

To build your noise mask:

- With `experiments/baseline.band` already open in GarageBand, make **no changes**
- **File → Save As** → save it as `experiments/noise-sampler.band`
- Run:

```bash
python3 band_cartographer.py learn-noise \
    experiments/baseline.band \
    experiments/noise-sampler.band
```

This writes a `noise_mask.json` to your research folder. All future diffs will automatically filter these offsets out. **This step makes a significant difference** — on GarageBand 10.4.8 arm64, it removes ~18,600 spurious ranges per experiment.

### 4. Make one change and save an experiment file

In GarageBand, make **exactly one change** from the canonical list. Then save a copy with the canonical label name:

```bash
# Example: you added one audio track
# In GarageBand: File → Save As → add-audio-track.band
# Move it into your experiments folder:
mv ~/Music/GarageBand/add-audio-track.band experiments/
```

See the full list of canonical experiments:
```bash
python3 band_cartographer.py list
```

### 5. Run the diff

```bash
python3 band_cartographer.py diff \
    experiments/baseline.band \
    experiments/add-audio-track.band
```

Results are automatically written to `research/<your-gb-version>/research.json` and `report.txt`.

### 6. Batch process (once you have several files)

```bash
python3 band_cartographer.py batch experiments/
```

### 7. View findings

```bash
python3 band_cartographer.py report experiments/
# or read the file directly:
cat research/<version>_<arch>/report.txt
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

# Generate your report and prepare to contribute
python3 band_cartographer.py contribute experiments/
```

Then open a Pull Request with your `report.txt`. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for full details.

---

## What the report looks like

Each experiment shows the label, size delta, and the meaningful byte ranges that changed after noise filtering:

```
[change-tempo-1bpm]  Δsize=-104  ranges=4  (+18626 noisy filtered)
  offset 0xaa   len=2  uint32=1210000
  offset 0x102  len=2  uint32=1210000
  offset 0x3be  len=2  uint32=1210000
  offset 0x12cc len=2  uint32=1210000  near='tSxT'

[change-track-pan]  Δsize=-104  ranges=1  (+18628 noisy filtered)
  offset 0xc5   len=1  uint32=8
```

The noise filtering is what makes these results readable — without it, `change-track-pan` would show 18,629 changed ranges instead of 1.

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

## References

- [nska_deserialize](https://github.com/avibrazil/NSKeyedArchiver) — the library used to decode the outer NSKeyedArchiver wrapper on older GB versions
- [Robert Heaton's Logic Pro synth file reverse engineering](https://robertheaton.com/2017/07/17/reverse-engineering-logic-pro-synth-files/) — the methodology this project is based on

---

## License

Research data (`report.txt` files) is released under [CC0](https://creativecommons.org/publicdomain/zero/1.0/) — no rights reserved, use freely.

Code (`band_cartographer.py`) is MIT licensed.
