# Contributing

Thanks for helping map the GarageBand binary format. Every GarageBand version and Mac architecture is a valuable data point — even if your results look similar to existing ones, cross-version comparison is how we identify which byte offsets are stable enough to build a parser on.

## What makes a good contribution

- **A complete set of experiments** — all 18 canonical labels if possible, or as many as you have time for
- **A noise mask** — run `learn-noise` before your experiments (see below). Results without noise filtering have tens of thousands of spurious ranges and are much harder to analyze.
- **A clean baseline** — use the canonical `baseline.band` from the repo, not a project you created yourself
- **One change per file** — each `.band` file should differ from baseline by exactly one thing
- **Accurate labels** — use the exact canonical names (`add-audio-track`, not `added-audio-track` or `audio track added`)

---

## Step by step

### 1. Fork and clone

```bash
git clone https://github.com/Wes-Selman/band-cartographer
cd band-cartographer
pip3 install -r requirements.txt
```

### 2. Check your GarageBand version and architecture

```bash
mdls -name kMDItemVersion /Applications/GarageBand.app
uname -m   # x86_64 = Intel, arm64 = Apple Silicon
```

Note these — they go in your PR description.

### 3. Set up your baseline

```bash
mkdir -p experiments
cp -r baseline.band experiments/baseline.band
python3 band_cartographer.py verify-baseline experiments/baseline.band
```

You should see:
```
✓  Inner blob hash matches canonical baseline.
   You have not opened this file in GarageBand yet — good.
   You are ready to begin experiments.
```

**Why this matters:** Everyone starting from the same file means byte offsets can be directly compared across GarageBand versions and architectures.

### 4. Open the baseline in GarageBand

Double-click `experiments/baseline.band`. GarageBand will rewrite the file on open — this is normal. Run `verify-baseline` again after this first open; you'll see a hash mismatch warning, which is expected and fine.

**Do not close and reopen `experiments/baseline.band` between experiments.** Keep the same post-open copy as your baseline throughout your session.

### 5. Build your noise mask

This is the most important step for result quality. GarageBand rewrites thousands of byte ranges on every save — timestamps, session counters, checksums — regardless of what you actually changed. Without filtering these, your results will have ~18,000 spurious ranges per experiment.

- With `experiments/baseline.band` open in GarageBand, make **no changes**
- **File → Save As** → `experiments/noise-sampler.band`
- Run:

```bash
python3 band_cartographer.py learn-noise \
    experiments/baseline.band \
    experiments/noise-sampler.band
```

You should see something like:
```
Raw diff: 18629 changed ranges (all of these are noise)
✓ Noise mask saved → research/10.4.8_arm64/noise_mask.json
  95016 offsets will be filtered from future diffs.
```

All subsequent diffs will automatically apply this mask.

### 6. Run your experiments

For each canonical experiment: make exactly one change in GarageBand, save as `<label>.band` in your experiments folder, then either diff individually or batch process:

```bash
# Single file
python3 band_cartographer.py diff experiments/baseline.band experiments/add-audio-track.band

# Or batch process the whole folder at once
python3 band_cartographer.py batch experiments/
```

Results are written to `research/<version>_<arch>/research.json` and `report.txt` automatically.

### 7. Review your findings

```bash
cat research/<version>_<arch>/report.txt
```

### 8. Submit a Pull Request

```bash
python3 band_cartographer.py contribute experiments/
# Follow the instructions it prints
```

**Submit your `report.txt` file** — not `research.json`. The full JSON file is several megabytes and contains tens of thousands of byte ranges that are impractical to review in a PR. The `report.txt` contains all the meaningful findings in a readable format.

Open a PR with the title: `research: GarageBand <version> <arch>`

In the PR description, include:
- GarageBand version
- macOS version
- Mac architecture (Intel or Apple Silicon)
- Number of experiments completed
- Whether you ran `learn-noise` (please do — it makes a big difference)
- Anything unusual you noticed

---

## What NOT to include in your PR

- `research.json` — too large, not human-reviewable. Submit `report.txt` instead.
- `noise_mask.json` — this is specific to your machine and session; it does not need to be shared
- `.band` files — these can be large and contain your personal audio. The `.gitignore` excludes them automatically.
- Audio files or personal projects
- Changes to `band_cartographer.py` or `README.md` — open a separate issue for those

---

## Questions or anomalies?

If something looks unexpected — an experiment produced no changes, or an unusual number of changed ranges even after noise filtering — open an issue describing what you saw. These anomalies are often the most informative findings.

## Code of conduct

This is a technical research project. Be precise, be kind, cite your sources.
