#!/usr/bin/env python3
"""
band_cartographer.py
====================
Systematic reverse engineering tool for the GarageBand .band binary format.

Part of the garageband-format-research open research project.
https://github.com/YOUR_USERNAME/garageband-format-research

SETUP:
    pip3 install nska_deserialize

WORKFLOW:
    1. Copy the canonical baseline from the repo into your experiments folder:
         cp -r baseline.band experiments/baseline.band

       Then verify it is intact and unmodified:
         python3 band_cartographer.py verify-baseline experiments/baseline.band

       IMPORTANT: Do not open baseline.band in GarageBand before verifying.
       GarageBand rewrites files on open, which would invalidate the checksum.

    2. Open baseline.band in GarageBand, make ONE change, then save a copy
       with a canonical label name:
         add-audio-track.band
         change-tempo-1bpm.band
         ...etc (see: python3 band_cartographer.py list)

    3. Run diff against baseline:
         python3 band_cartographer.py diff \\
             experiments/baseline.band \\
             experiments/add-audio-track.band

       The label is inferred from the filename automatically.

    4. After collecting several files, batch process the whole folder:
         python3 band_cartographer.py batch experiments/

       (verify-baseline runs automatically before batch processing)

    5. Print a summary of findings:
         python3 band_cartographer.py report experiments/

    6. When ready to share your results:
         python3 band_cartographer.py contribute experiments/
         (prints the exact git commands to run)

REPO MAINTAINER ONLY — regenerate the baseline checksum after updating baseline.band:
    python3 band_cartographer.py generate-baseline-hash baseline.band

OUTPUT FILES (written into the same folder as your .band files):
    research.json  — machine-readable log of all diffs
    report.txt     — human-readable findings summary

CONTRIBUTING:
    See CONTRIBUTING.md for how to submit your research.json to the project.
    Different GarageBand versions and architectures are valuable — even if
    your results look similar to existing ones.
"""

import sys
import os
import json
import struct
import hashlib
import platform
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

try:
    import nska_deserialize as nsd
    NSKA_VERSION = getattr(nsd, "__version__", "unknown")
except ImportError:
    print("ERROR: nska_deserialize not installed.")
    print("Run:   pip3 install nska_deserialize")
    sys.exit(1)


# ── Canonical experiment labels ──────────────────────────────────────────────
# These are the standard set. Contributors should use these exact names
# so results can be cross-referenced across GB versions.

CANONICAL_EXPERIMENTS = {
    # Track structure
    "add-audio-track":      "Add one empty audio track",
    "add-midi-track":       "Add one software instrument (MIDI) track",
    "delete-track":         "Delete a track (start with 2 tracks, delete one)",
    "rename-track":         "Rename a track to something different",
    "reorder-tracks":       "Drag one track above another (swap order)",
    # Regions
    "add-region":           "Drag a loop into an empty track (adds one region)",
    "move-region":          "Move a region to a different bar position",
    "resize-region":        "Resize a region (drag edge to make it longer)",
    "delete-region":        "Delete a region from a track",
    "duplicate-region":     "Duplicate a region (Option+drag)",
    # Tempo / time signature
    "change-tempo-1bpm":    "Change global tempo by exactly 1 BPM",
    "change-time-sig-3-4":  "Change time signature from 4/4 to 3/4",
    "add-tempo-change-bar9":"Add a tempo change event at bar 9",
    # Mix
    "change-track-volume":  "Move a track's volume fader",
    "change-track-pan":     "Move a track's pan knob",
    "mute-track":           "Mute a track (M key)",
    "solo-track":           "Solo a track (S key)",
    # Plugins
    "add-plugin":           "Add one plugin/effect to a track's plugin chain",
}



# ── Canonical baseline checksum ──────────────────────────────────────────────
# SHA-256 of the inner binary blob (DfLogicModelLogicSong NS.data) from the
# committed baseline.band. This is what every contributor's baseline is checked
# against BEFORE they open it in GarageBand.
#
# GarageBand rewrites files on open — so the baseline diverges from this hash
# the moment it is opened. That is expected and normal. The hash only confirms
# that the contributor started from the correct unmodified file.
#
# To regenerate after updating baseline.band:
#   python3 band_cartographer.py generate-baseline-hash baseline.band

BASELINE_INNER_SHA256 = "2e9caefda7dae5f02746d0e933410dbcfe2928bc32b40beab7b470f131552a91"  # set by repo maintainer after first baseline is committed
BASELINE_OUTER_FIELDS = {
    # Key outer fields we expect in the canonical baseline.
    # Used as a secondary sanity check when the inner hash can't be verified.
    "CbVersion": 30000,
    "arrange.DfMetronome": True,
    "arrange.DfCountIn": True,
}


# ════════════════════════════════════════════════════════════════════════════
# BASELINE VERIFICATION
# ════════════════════════════════════════════════════════════════════════════

def _hash_inner(band_path: Path) -> Optional[str]:
    """Return SHA-256 hex digest of the inner binary blob, or None if unavailable."""
    try:
        loaded = load_band(band_path)
        inner = loaded.get("inner")
        if inner:
            return hashlib.sha256(inner).hexdigest()
    except Exception:
        pass
    return None


def _hash_projectdata(band_path: Path) -> str:
    """SHA-256 of the raw projectData file — used when generating the stored hash."""
    project_data = band_path / "projectData"
    return hashlib.sha256(project_data.read_bytes()).hexdigest()


def cmd_verify_baseline(baseline_path: str) -> bool:
    """
    Verify a contributor's baseline.band against the canonical checksum.
    Returns True if the baseline is valid, False otherwise.
    Prints clear guidance in both cases.
    """
    baseline_p = Path(baseline_path)
    print(f"\n── Verifying baseline: {baseline_p.name} ─────────────────────────")

    if not (baseline_p / "projectData").exists():
        print("  ✗  Not a valid .band bundle — no projectData found.")
        return False

    # Check 1: inner blob hash (primary)
    if BASELINE_INNER_SHA256:
        contributor_hash = _hash_inner(baseline_p)
        if contributor_hash is None:
            print("  ⚠  Could not extract inner blob — skipping hash check.")
        elif contributor_hash == BASELINE_INNER_SHA256:
            print("  ✓  Inner blob hash matches canonical baseline.")
            print("     You have not opened this file in GarageBand yet — good.")
            print("     You are ready to begin experiments.\n")
            return True
        else:
            print("  ⚠  Inner blob hash does NOT match.")
            print("     This usually means GarageBand has already opened and")
            print("     rewritten this file. That is expected and okay — it")
            print("     means GarageBand added its own timestamps and state.")
            print()
            print("     Your diffs will still be valid AS LONG AS you use this")
            print("     same opened-baseline as your baseline for all experiments.")
            print("     Do not re-copy baseline.band from the repo mid-session.")
            print()
            _check_outer_fields(baseline_p)
            return True  # warn but don't block — post-open baseline is still usable

    else:
        # No hash stored yet — do a structural check instead
        print("  ⚠  No canonical hash stored yet (repo maintainer needs to run")
        print("     generate-baseline-hash after committing the first baseline).")
        print("     Falling back to structural check.\n")
        return _check_outer_fields(baseline_p)


def _check_outer_fields(baseline_p: Path) -> bool:
    """Secondary check: verify expected outer fields are present."""
    try:
        loaded = load_band(baseline_p)
        outer  = loaded["outer"]

        def get_nested(d, dotkey):
            keys = dotkey.split(".")
            val  = d
            for k in keys:
                if not isinstance(val, dict):
                    return "__MISSING__"
                val = val.get(k, "__MISSING__")
            return val

        all_ok = True
        for field, expected in BASELINE_OUTER_FIELDS.items():
            actual = get_nested(outer, field)
            if actual == expected:
                print(f"  ✓  {field} = {expected}")
            else:
                print(f"  ✗  {field}: expected {expected!r}, got {actual!r}")
                all_ok = False

        if all_ok:
            print("\n  Structural check passed. Proceed with experiments.")
        else:
            print("\n  ✗  Structural check failed.")
            print("     Make sure you are using baseline.band from the repo root,")
            print("     not a project you created yourself.")

        return all_ok

    except Exception as e:
        print(f"  ✗  Could not load baseline: {e}")
        return False


def cmd_generate_baseline_hash(baseline_path: str):
    """
    REPO MAINTAINER ONLY.
    Compute the canonical hash for a new baseline.band and print the
    line to paste into this script's BASELINE_INNER_SHA256 constant.
    """
    baseline_p = Path(baseline_path)
    print(f"\n── Generating canonical baseline hash ───────────────────────────")

    inner_hash = _hash_inner(baseline_p)
    raw_hash   = _hash_projectdata(baseline_p)

    if inner_hash:
        print(f"\n  Inner blob SHA-256 (recommended — use this one):")
        print(f"  {inner_hash}")
        print(f"\n  Paste this into band_cartographer.py:")
        print(f"  BASELINE_INNER_SHA256 = \"{inner_hash}\"")
    else:
        print("  Could not extract inner blob.")

    print(f"\n  Raw projectData SHA-256 (for reference):")
    print(f"  {raw_hash}")
    print()
    print("  IMPORTANT: Generate this hash BEFORE opening baseline.band")
    print("  in GarageBand. Once opened, the file will be rewritten and")
    print("  the hash will change. Commit the .band file first, generate")
    print("  the hash second, then update this script and commit again.")



def detect_environment(band_path: Path) -> dict:
    """
    Auto-detect GarageBand version, macOS version, and architecture.
    Used to name the research folder and tag every entry in research.json.
    """
    env = {
        "macos_version":        platform.mac_ver()[0],
        "architecture":         platform.machine(),   # x86_64 or arm64
        "python_version":       platform.python_version(),
        "nska_version":         NSKA_VERSION,
        "detected_at":          datetime.now(timezone.utc).isoformat(),
    }

    # Try to get GarageBand app version via mdls or defaults
    gb_version = _get_garageband_version()
    env["garageband_version"] = gb_version

    # Also read CbVersion from the band file as a cross-check
    try:
        project_data = band_path / "projectData"
        with open(project_data, "rb") as f:
            data = nsd.deserialize_plist(f)
        for item in data:
            if isinstance(item, dict) and "CbVersion" in item:
                env["CbVersion"] = item["CbVersion"]
                break
    except Exception:
        pass

    return env


def _get_garageband_version() -> str:
    """Try multiple methods to get the installed GarageBand version."""
    # Method 1: mdls on the app bundle
    try:
        result = subprocess.run(
            ["mdls", "-name", "kMDItemVersion",
             "/Applications/GarageBand.app"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            line = result.stdout.strip()
            # Output: kMDItemVersion = "10.4.8"
            if '"' in line:
                return line.split('"')[1]
    except Exception:
        pass

    # Method 2: defaults read on Info.plist
    try:
        result = subprocess.run(
            ["defaults", "read",
             "/Applications/GarageBand.app/Contents/Info",
             "CFBundleShortVersionString"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return "unknown"


def folder_name_for_env(env: dict) -> str:
    """
    Generate a standardized folder name from environment info.
    e.g. "10.4.8_x86_64" or "10.4.9_arm64"
    """
    gb  = env.get("garageband_version", "unknown").replace(" ", "_")
    arch = env.get("architecture", "unknown")
    return f"{gb}_{arch}"


# ════════════════════════════════════════════════════════════════════════════
# CORE: Load a .band bundle
# ════════════════════════════════════════════════════════════════════════════

def load_band(band_path: Path) -> dict:
    """
    Load a .band bundle and return:
      outer:  deserialized NSKeyedArchiver fields (readable)
      inner:  raw bytes of DfLogicModelLogicSong NS.data (opaque binary)
      raw:    raw projectData bytes
    """
    project_data = band_path / "projectData"
    if not project_data.exists():
        raise FileNotFoundError(f"No projectData in {band_path}")

    raw_bytes = project_data.read_bytes()

    with open(project_data, "rb") as f:
        deserialized = nsd.deserialize_plist(f)

    outer = {}
    inner_bytes = None

    for item in deserialized:
        if not isinstance(item, dict):
            continue

        if "CbVersion" in item:
            outer["CbVersion"] = item["CbVersion"]

        if "DfDocument arrange model" in item:
            arrange = item["DfDocument arrange model"]
            outer["arrange"] = {
                k: v for k, v in arrange.items()
                if not isinstance(v, (bytes, bytearray))
            }

        if "DfDocument logic model" in item:
            logic = item["DfDocument logic model"]
            if "DfLogicModelLogicSong" in logic:
                song = logic["DfLogicModelLogicSong"]
                if isinstance(song, dict) and "NS.data" in song:
                    raw_data = song["NS.data"]
                    if isinstance(raw_data, (bytes, bytearray)):
                        inner_bytes = bytes(raw_data)
                    elif isinstance(raw_data, str):
                        inner_bytes = raw_data.encode("latin-1")

    return {
        "outer": outer,
        "inner": inner_bytes,
        "raw":   raw_bytes,
        "path":  str(band_path),
    }


# ════════════════════════════════════════════════════════════════════════════
# DIFF
# ════════════════════════════════════════════════════════════════════════════

def diff_outer(a: dict, b: dict) -> list:
    def flatten(d, prefix=""):
        out = {}
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                out.update(flatten(v, key))
            else:
                out[key] = v
        return out

    af = flatten(a)
    bf = flatten(b)
    changes = []
    for key in sorted(set(af) | set(bf)):
        av = af.get(key, "__MISSING__")
        bv = bf.get(key, "__MISSING__")
        if av != bv:
            changes.append({"field": key, "baseline": str(av), "changed": str(bv)})
    return changes


def diff_inner_bytes(baseline: bytes, changed: bytes) -> dict:
    if baseline is None and changed is None:
        return {"error": "inner blob missing from both files"}
    if baseline is None:
        return {"error": "inner blob missing from baseline"}
    if changed is None:
        return {"error": "inner blob missing from changed file"}

    b_len, c_len = len(baseline), len(changed)
    min_len = min(b_len, c_len)

    changed_ranges = []
    i = 0
    while i < min_len:
        if baseline[i] != changed[i]:
            start = i
            while i < min_len and baseline[i] != changed[i]:
                i += 1
            end = i
            changed_ranges.append({
                "offset_start":  start,
                "offset_end":    end,
                "length":        end - start,
                "offset_hex":    hex(start),
                "baseline_hex":  baseline[start:end].hex(),
                "changed_hex":   changed[start:end].hex(),
                "as_uint32_le":  _try_uint32(changed, start),
                "as_float32":    _try_float32(changed, start),
                "as_string":     _try_string(changed, start),
            })
        else:
            i += 1

    size_delta = c_len - b_len
    appended   = changed[min_len:].hex() if c_len > b_len else None
    removed    = baseline[min_len:].hex() if b_len > c_len else None

    return {
        "baseline_size":      b_len,
        "changed_size":       c_len,
        "size_delta":         size_delta,
        "num_changed_ranges": len(changed_ranges),
        "changed_ranges":     changed_ranges,
        "appended_bytes":     appended,
        "removed_bytes":      removed,
    }


def _try_uint32(data, offset):
    try:
        if offset + 4 <= len(data):
            return str(struct.unpack_from("<I", data, offset)[0])
    except Exception:
        pass
    return None


def _try_float32(data, offset):
    try:
        if offset + 4 <= len(data):
            val = struct.unpack_from("<f", data, offset)[0]
            if val == val:  # exclude NaN
                return f"{val:.4f}"
    except Exception:
        pass
    return None


def _try_string(data, offset, window=64):
    try:
        chunk = data[max(0, offset - 8): offset + window]
        printable = "".join(chr(b) if 32 <= b < 127 else "·" for b in chunk)
        readable = [s for s in printable.split("·") if len(s) >= 3]
        if readable:
            return " | ".join(readable[:3])
    except Exception:
        pass
    return None


# ════════════════════════════════════════════════════════════════════════════
# RESEARCH LOG
# ════════════════════════════════════════════════════════════════════════════

def load_research(research_file: Path) -> list:
    if research_file.exists():
        with open(research_file) as f:
            return json.load(f)
    return []


def save_research(research_file: Path, entries: list):
    with open(research_file, "w") as f:
        json.dump(entries, f, indent=2)
    print(f"  ✓ Saved → {research_file}")


def append_entry(research_file: Path, label: str, env: dict,
                 outer_diff: list, inner_diff: dict):
    entries = load_research(research_file)

    # Overwrite if label already exists
    entries = [e for e in entries if e["label"] != label]

    entries.append({
        "label":       label,
        "description": CANONICAL_EXPERIMENTS.get(label, "custom experiment"),
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "environment": env,
        "outer_diff":  outer_diff,
        "inner_diff":  inner_diff,
    })

    save_research(research_file, entries)
    return entries


# ════════════════════════════════════════════════════════════════════════════
# REPORT
# ════════════════════════════════════════════════════════════════════════════

def generate_report(research_file: Path) -> str:
    entries = load_research(research_file)
    if not entries:
        return "No research entries yet. Run some diffs first."

    env = entries[0].get("environment", {}) if entries else {}
    lines = []
    lines.append("=" * 70)
    lines.append("GarageBand Format Research — Findings Report")
    lines.append(f"GarageBand: {env.get('garageband_version', '?')}  "
                 f"Arch: {env.get('architecture', '?')}  "
                 f"macOS: {env.get('macos_version', '?')}")
    lines.append(f"CbVersion: {env.get('CbVersion', '?')}")
    lines.append(f"Entries: {len(entries)} / {len(CANONICAL_EXPERIMENTS)} canonical")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 70)

    # Coverage
    done  = {e["label"] for e in entries}
    lines.append("\n── EXPERIMENT COVERAGE ─────────────────────────────────────────────")
    for label, desc in CANONICAL_EXPERIMENTS.items():
        tick = "✓" if label in done else "○"
        lines.append(f"  {tick}  {label:<30}  {desc}")

    extra = [e["label"] for e in entries if e["label"] not in CANONICAL_EXPERIMENTS]
    if extra:
        lines.append("\n  Custom experiments:")
        for label in extra:
            lines.append(f"  +  {label}")

    # Outer fields
    lines.append("\n── READABLE OUTER FIELD CHANGES ────────────────────────────────────")
    field_counts = {}
    for entry in entries:
        for c in entry.get("outer_diff", []):
            field_counts[c["field"]] = field_counts.get(c["field"], 0) + 1

    if field_counts:
        for field, count in sorted(field_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {count:2d}x  {field}")
    else:
        lines.append("  (none detected)")

    # Inner binary map
    lines.append("\n── INNER BINARY BYTE MAP ───────────────────────────────────────────")
    for entry in entries:
        inner = entry.get("inner_diff", {})
        label = entry["label"]

        if "error" in inner:
            lines.append(f"  [{label}]  ERROR: {inner['error']}")
            continue

        n     = inner.get("num_changed_ranges", 0)
        delta = inner.get("size_delta", 0)
        lines.append(f"\n  [{label}]  Δsize={delta:+d}  ranges={n}")

        for r in inner.get("changed_ranges", [])[:8]:
            parts = [f"offset {r['offset_hex']}  len={r['length']}"]
            if r["as_uint32_le"]: parts.append(f"uint32={r['as_uint32_le']}")
            if r["as_float32"]:   parts.append(f"float32={r['as_float32']}")
            if r["as_string"]:    parts.append(f"near='{r['as_string']}'")
            lines.append("    " + "  ".join(parts))
        if n > 8:
            lines.append(f"    ... +{n-8} more ranges")

    # Hypotheses
    lines.append("\n── HYPOTHESES ──────────────────────────────────────────────────────")
    hypotheses = _generate_hypotheses(entries)
    if hypotheses:
        for h in hypotheses:
            lines.append(f"  • {h}")
    else:
        lines.append("  (need more entries to detect patterns)")

    # What's next
    todo = [l for l in CANONICAL_EXPERIMENTS if l not in done]
    lines.append("\n── NEXT EXPERIMENTS ────────────────────────────────────────────────")
    if todo:
        for label in todo[:6]:
            lines.append(f"  ○  {label}  —  {CANONICAL_EXPERIMENTS[label]}")
        if len(todo) > 6:
            lines.append(f"  ... and {len(todo)-6} more (see `list` command)")
    else:
        lines.append("  All canonical experiments complete!")
        lines.append("  Consider submitting your research.json via a Pull Request.")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def _generate_hypotheses(entries: list) -> list:
    hypotheses = []

    # Offsets that appear in multiple experiments
    offset_map = {}
    for entry in entries:
        for r in entry.get("inner_diff", {}).get("changed_ranges", []):
            offset = r["offset_hex"]
            offset_map.setdefault(offset, []).append(entry["label"])

    for offset, labels in sorted(offset_map.items(), key=lambda x: -len(x[1])):
        if len(labels) > 1:
            hypotheses.append(
                f"Offset {offset} changes in {len(labels)} experiments "
                f"({', '.join(labels[:3])}{'…' if len(labels) > 3 else ''}) "
                f"— likely a shared header field or timestamp"
            )

    # Consistent size delta across track operations
    track_entries = [
        e for e in entries
        if "track" in e["label"]
        and "error" not in e.get("inner_diff", {})
    ]
    if len(track_entries) >= 2:
        deltas = [e["inner_diff"].get("size_delta", 0) for e in track_entries]
        if len(set(deltas)) == 1 and deltas[0] != 0:
            hypotheses.append(
                f"All track experiments: size_delta={deltas[0]} bytes — "
                f"candidate per-track record size"
            )

    # Float32 near tempo changes
    for entry in entries:
        if "tempo" not in entry["label"]:
            continue
        for r in entry.get("inner_diff", {}).get("changed_ranges", []):
            if r.get("as_float32"):
                hypotheses.append(
                    f"Offset {r['offset_hex']} in [{entry['label']}] "
                    f"= float32 {r['as_float32']} — tempo candidate"
                )
                break

    return hypotheses


# ════════════════════════════════════════════════════════════════════════════
# RESOLVE PATHS: Given a .band file, find or create its research folder
# ════════════════════════════════════════════════════════════════════════════

def resolve_research_paths(band_path: Path):
    """
    Given a .band file path, return (research_dir, research_json, report_txt).
    The research folder is auto-created and named after the GarageBand version.
    """
    env = detect_environment(band_path)
    folder = folder_name_for_env(env)

    # Put research/ at the repo root (two levels up from where the band file is,
    # or just next to it if we can't find a repo root)
    repo_root = _find_repo_root(band_path) or band_path.parent
    research_dir = repo_root / "research" / folder
    research_dir.mkdir(parents=True, exist_ok=True)

    return (
        research_dir,
        research_dir / "research.json",
        research_dir / "report.txt",
        env,
    )


def _find_repo_root(start: Path) -> Optional[Path]:
    """Walk up from start looking for a .git folder."""
    current = start if start.is_dir() else start.parent
    for _ in range(10):
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


# ════════════════════════════════════════════════════════════════════════════
# CLI COMMANDS
# ════════════════════════════════════════════════════════════════════════════

def cmd_diff(baseline_path: str, changed_path: str, label: str = None):
    baseline_p = Path(baseline_path)
    changed_p  = Path(changed_path)

    # Infer label from filename if not provided
    if not label:
        label = changed_p.stem
    label = label.lower().replace(" ", "-")

    # Warn if not a canonical label
    if label not in CANONICAL_EXPERIMENTS:
        print(f"  ⚠  '{label}' is not a canonical label.")
        print(f"     Run `list` to see canonical names.")
        print(f"     Proceeding anyway as a custom experiment.\n")

    print(f"\n── Diff: {label} ──────────────────────────────────────────────")

    baseline = load_band(baseline_p)
    changed  = load_band(changed_p)

    research_dir, research_json, report_txt, env = resolve_research_paths(baseline_p)
    print(f"  Research folder: {research_dir}")

    outer_diff = diff_outer(baseline["outer"], changed["outer"])
    inner_diff = diff_inner_bytes(baseline["inner"], changed["inner"])

    # Print summary
    print(f"\n  Outer field changes: {len(outer_diff)}")
    for c in outer_diff:
        print(f"    {c['field']}: {c['baseline']!r} → {c['changed']!r}")

    print(f"\n  Inner binary:")
    if "error" in inner_diff:
        print(f"    ERROR: {inner_diff['error']}")
    else:
        print(f"    Size: {inner_diff['baseline_size']} → {inner_diff['changed_size']} "
              f"({inner_diff['size_delta']:+d} bytes)")
        print(f"    Changed ranges: {inner_diff['num_changed_ranges']}")
        for r in inner_diff["changed_ranges"][:5]:
            parts = [f"    offset {r['offset_hex']}  len={r['length']}"]
            if r["as_uint32_le"]: parts.append(f"uint32={r['as_uint32_le']}")
            if r["as_float32"]:   parts.append(f"float32={r['as_float32']}")
            if r["as_string"]:    parts.append(f"near='{r['as_string']}'")
            print("  ".join(parts))
        if inner_diff["num_changed_ranges"] > 5:
            print(f"    ... +{inner_diff['num_changed_ranges'] - 5} more")

    append_entry(research_json, label, env, outer_diff, inner_diff)

    # Remind to push
    print(f"\n  To share your findings:")
    print(f"    git add {research_json}")
    print(f"    git commit -m 'research: {label}'")
    print(f"    git push")


def cmd_batch(folder: str):
    """Process all .band files in a folder. Baseline must be named 'baseline.band'."""
    folder_p   = Path(folder)
    baseline_p = folder_p / "baseline.band"

    if not baseline_p.exists():
        print(f"ERROR: No baseline.band found in {folder}")
        print("Copy baseline.band from the repo root into your experiments folder:")
        print(f"  cp -r baseline.band {folder}")
        sys.exit(1)

    # Always verify baseline before batch processing
    valid = cmd_verify_baseline(str(baseline_p))
    if not valid:
        print("\nERROR: Baseline verification failed. Fix the issue above before continuing.")
        sys.exit(1)
    print()

    band_files = sorted(p for p in folder_p.glob("*.band") if p.stem != "baseline")

    if not band_files:
        print(f"No experiment .band files found in {folder} (excluding baseline.band)")
        return

    print(f"Baseline: {baseline_p}")
    print(f"Found {len(band_files)} experiment files\n")

    for band_file in band_files:
        try:
            cmd_diff(str(baseline_p), str(band_file))
            print()
        except Exception as e:
            print(f"  ERROR: {band_file.name}: {e}\n")

    print("✓ Batch complete.")
    cmd_report(folder)


def cmd_report(folder: str = "."):
    folder_p = Path(folder)

    # Find the right research.json
    # Either we're given a versioned research folder directly, or a band folder
    research_json = None
    if (folder_p / "research.json").exists():
        research_json = folder_p / "research.json"
    else:
        # Try to find via the folder structure
        band_files = list(folder_p.glob("*.band"))
        if band_files:
            _, research_json, _, _ = resolve_research_paths(band_files[0])

    if not research_json or not research_json.exists():
        print("No research.json found. Run some diffs first.")
        return

    report = generate_report(research_json)
    print(report)

    report_txt = research_json.parent / "report.txt"
    report_txt.write_text(report)
    print(f"\n✓ Report saved → {report_txt}")


def cmd_status(folder: str = "."):
    folder_p = Path(folder)
    band_files = list(folder_p.glob("*.band"))
    if not band_files:
        # Try looking in research/ subdirectories
        research_files = list(folder_p.glob("research/*/research.json"))
        if not research_files:
            print("No research data found here.")
            return
        for rf in research_files:
            entries = load_research(rf)
            done    = {e["label"] for e in entries}
            todo    = [l for l in CANONICAL_EXPERIMENTS if l not in done]
            print(f"\n{rf.parent.name}: {len(done)}/{len(CANONICAL_EXPERIMENTS)} done")
            if todo:
                for label in todo[:3]:
                    print(f"  ○  {label}")
                if len(todo) > 3:
                    print(f"  ... and {len(todo)-3} more")
        return

    _, research_json, _, env = resolve_research_paths(band_files[0])
    entries = load_research(research_json)
    done    = {e["label"] for e in entries}
    todo    = [l for l in CANONICAL_EXPERIMENTS if l not in done]

    print(f"\nGarageBand {env.get('garageband_version','?')} "
          f"({env.get('architecture','?')})")
    print(f"Progress: {len(done)}/{len(CANONICAL_EXPERIMENTS)} experiments\n")

    for label in CANONICAL_EXPERIMENTS:
        tick = "✓" if label in done else "○"
        print(f"  {tick}  {label}")

    if todo:
        print(f"\nNext up:  {todo[0]}")
        print(f"  {CANONICAL_EXPERIMENTS[todo[0]]}")


def cmd_list():
    """Print canonical experiment labels and instructions."""
    print("\nCanonical experiment labels")
    print("Use these exact names when saving your changed .band files.\n")
    for label, desc in CANONICAL_EXPERIMENTS.items():
        print(f"  {label:<30}  {desc}")
    print(f"\n{len(CANONICAL_EXPERIMENTS)} total experiments")
    print("\nSave each file as:  <label>.band")
    print("e.g.  add-audio-track.band,  change-tempo-1bpm.band")


def cmd_contribute(folder: str = "."):
    """Stage research.json and print contribution instructions."""
    folder_p   = Path(folder)
    band_files = list(folder_p.glob("*.band"))

    if not band_files:
        print("Run this from your research folder (where your .band files are).")
        return

    _, research_json, _, env = resolve_research_paths(band_files[0])

    if not research_json.exists():
        print("No research.json found yet. Run some diffs first.")
        return

    entries = load_research(research_json)
    done    = {e["label"] for e in entries}

    print(f"\nReady to contribute:")
    print(f"  GarageBand {env.get('garageband_version','?')} "
          f"({env.get('architecture','?')}) on macOS {env.get('macos_version','?')}")
    print(f"  {len(done)} experiments completed\n")

    print("Steps:")
    print(f"  1. git add {research_json}")
    print(f"  2. git commit -m 'research: {folder_name_for_env(env)} "
          f"— {len(done)} experiments'")
    print(f"  3. git push")
    print(f"  4. Open a Pull Request on GitHub")
    print(f"\nSee CONTRIBUTING.md for full instructions.")


def print_usage():
    print(__doc__)
    print("COMMANDS:")
    print("  diff <baseline.band> <changed.band> [label]")
    print("  batch <folder/>")
    print("  report [folder/]")
    print("  status [folder/]")
    print("  list")
    print("  contribute [folder/]")
    print("  verify-baseline <baseline.band>")
    print("  generate-baseline-hash <baseline.band>   (repo maintainer only)")


# ════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print_usage()
        sys.exit(0)

    cmd = args[0]

    if cmd == "diff":
        if len(args) < 3:
            print("Usage: band_cartographer.py diff <baseline.band> <changed.band> [label]")
            sys.exit(1)
        label = args[3] if len(args) > 3 else None
        cmd_diff(args[1], args[2], label)

    elif cmd == "batch":
        if len(args) < 2:
            print("Usage: band_cartographer.py batch <folder/>")
            sys.exit(1)
        cmd_batch(args[1])

    elif cmd == "report":
        cmd_report(args[1] if len(args) > 1 else ".")

    elif cmd == "status":
        cmd_status(args[1] if len(args) > 1 else ".")

    elif cmd == "list":
        cmd_list()

    elif cmd == "contribute":
        cmd_contribute(args[1] if len(args) > 1 else ".")

    elif cmd == "verify-baseline":
        if len(args) < 2:
            print("Usage: band_cartographer.py verify-baseline <baseline.band>")
            sys.exit(1)
        ok = cmd_verify_baseline(args[1])
        sys.exit(0 if ok else 1)

    elif cmd == "generate-baseline-hash":
        if len(args) < 2:
            print("Usage: band_cartographer.py generate-baseline-hash <baseline.band>")
            sys.exit(1)
        cmd_generate_baseline_hash(args[1])

    else:
        print(f"Unknown command: {cmd}")
        print_usage()
        sys.exit(1)
