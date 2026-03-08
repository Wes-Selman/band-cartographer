# Contributing

Thanks for helping map the GarageBand binary format. Every GarageBand version and Mac architecture is a valuable data point — even if your results look similar to existing ones, cross-version comparison is how we identify which byte offsets are stable enough to build a parser on.

## What makes a good contribution

- **A complete set of experiments** — all 18 canonical labels if possible, or as many as you have time for
- **A clean baseline** — the simplest possible project: one track, one region, default tempo, nothing else
- **One change per file** — each `.band` file should differ from baseline by exactly one thing
- **Accurate labels** — use the exact canonical names (`add-audio-track`, not `added-audio-track` or `audio track added`)

## Step by step

### 1. Fork and clone

```bash
git clone XXX
cd garageband-format-research
pip3 install -r requirements.txt
```

### 2. Check what GarageBand version you have

```bash
mdls -name kMDItemVersion /Applications/GarageBand.app
```

Note your version and whether your Mac is Intel (x86_64) or Apple Silicon (arm64):
```bash
uname -m
```

### 3. Set up your baseline

The repo includes a canonical `baseline.band` — a minimal GarageBand project with one software instrument track, one region at bar 1, and default tempo. **Use this file as your starting point.** Do not create your own baseline.

```bash
# Copy the canonical baseline into your experiments folder
mkdir -p experiments
cp -r baseline.band experiments/baseline.band
```

Then verify it before doing anything else:

```bash
python3 band_cartographer.py verify-baseline experiments/baseline.band
```

You should see:
```
✓  Inner blob hash matches canonical baseline.
   You have not opened this file in GarageBand yet — good.
   You are ready to begin experiments.
```

**Why this matters:** Everyone starting from the same file means byte offsets can be directly compared across GarageBand versions and architectures. If you start from a different baseline, your offsets will be structurally similar but not directly comparable.

### 4. Open the baseline in GarageBand

Double-click `experiments/baseline.band`. GarageBand will rewrite the file on open — this is normal. Run `verify-baseline` again after this first open; you'll see a hash mismatch warning, which is expected and fine. The script will confirm you can proceed.

**Do not close and reopen `experiments/baseline.band` between experiments.** Keep it open in GarageBand for the whole session, or at minimum use the same post-open copy as your baseline throughout.

### 5. Run your experiments

```bash
# Single file
python3 band_cartographer.py diff experiments/baseline.band experiments/add-audio-track.band

# Or batch process the whole folder
python3 band_cartographer.py batch experiments/
```

Results are written to `research/<version>_<arch>/research.json` automatically.

### 6. Review your findings

```bash
python3 band_cartographer.py report experiments/
```

### 7. Submit a Pull Request

```bash
python3 band_cartographer.py contribute experiments/
# Follow the instructions it prints
```

Open a PR with the title: `research: GarageBand <version> <arch>`

In the PR description, note:
- GarageBand version
- macOS version  
- Mac architecture (Intel or Apple Silicon)
- How many experiments you completed
- Anything unusual you noticed

## What NOT to include in your PR

- `.band` files — these can be large and contain your personal audio. The `.gitignore` excludes them automatically.
- Audio files or personal projects
- Changes to `band_cartographer.py` or `README.md` (open a separate issue for those)

## Questions or anomalies?

If something looks unexpected — an experiment produced no changes, or an unusual number of changed ranges — open an issue describing what you saw. These anomalies are often the most informative findings.

## Code of conduct

This is a technical research project. Be precise, be kind, cite your sources.
