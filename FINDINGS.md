# Findings

This is the living summary of what has been confirmed about the GarageBand binary format. It is updated as new research is contributed.

**Status: First experiments complete — 18/18 canonical experiments, GarageBand 10.4.8 arm64.**

---

## Format overview

A `.band` file is a macOS bundle (folder) containing:

```
MySong.band/
  Alternatives/000/ProjectData   ← main file on GB 10.4+ (raw gnoS binary)
  projectData                    ← main file on older GB versions (NSKeyedArchiver plist)
  Alternatives/                  ← GarageBand's own internal undo/version data
  Media/                         ← audio files referenced by the project
  Resources/                     ← thumbnails, waveform caches
```

GarageBand 10.4+ on Apple Silicon stores `ProjectData` as a **raw binary** — there is no NSKeyedArchiver wrapper. The entire file IS the binary blob. Older versions wrap it in NSKeyedArchiver as `DfLogicModelLogicSong` → `NS.data`.

Both formats begin with the magic bytes `gnoS` (= "Song" reversed, a classic Mac resource fork convention). This is where tracks, regions, tempo, and plugin state live.

---

## Noise

GarageBand rewrites a large number of byte ranges on every save regardless of what the user changed. On our baseline (GarageBand 10.4.8, arm64), a no-op save produces **18,629 changed ranges covering 95,016 byte positions**. These are timestamps, session counters, internal checksums, and offset tables that are not semantically meaningful.

The `learn-noise` command in `band_cartographer.py` identifies and masks these automatically. All findings below are from noise-filtered diffs.

---

## Confirmed field locations

All offsets are into the raw `ProjectData` binary (gnoS format). Confirmed on GarageBand 10.4.8, arm64, macOS 26.3.1.

| Field | Offset | Type | Value / Notes |
|---|---|---|---|
| Track mixer byte (pan/mute/solo/volume marker) | `0xc5` | uint8 | Changes on pan, volume, mute, solo — likely a dirty/changed flag or mixer struct pointer |
| Tempo (global) | `0xaa`, `0x102`, `0x3be`, `0x12cc` | uint32 LE | Stored redundantly in 4 locations. Value `1210000` observed — likely microseconds per beat (µs/beat). 60,000,000 ÷ µs/beat = BPM. |
| Time signature | `0xfa`, `0x3b6` | uint32 LE | Stored in 2 locations. Value `17236483` observed for 3/4. |
| Mute state | `0x1accf` | uint8 | 1 byte changes when track is muted. Offset `0xc5` also changes (mixer flag). |
| Pan value | `0xc5` | uint8 | Only 1 byte changes for pan adjustment — very clean signal. |
| Volume value | `0xc5`, `0x1ace9` | uint8/uint16 | 2 byte ranges change for volume adjustment. |
| Region position | `0x12cb`, `0x36465` | mixed | `near='tSxT'` and `near='karT'` strings nearby suggest track/region struct tags. |

### Tag strings observed near changed offsets

These 4-byte reversed strings appear to be struct type tags (similar to Mac OS resource types):

| Tag (as found) | Reversed | Likely meaning |
|---|---|---|
| `gnoS` | `Song` | File magic / root song object |
| `qeSM` | `MSeq` | MIDI sequence or arrangement section |
| `tSxT` | `TxSt` | Text string (possibly track/region name) |
| `karT` | `TraK` | Track record |
| `OCuA` | `AuCO` | Audio content object |
| `UCuA` | `AuCU` | Audio content (variant) |
| `ivnE` | `EnvI` | Envelope / automation |

---

## Experiments with clean signal (low noise, high confidence)

These experiments produced very few changed ranges after noise filtering, making their fields high-confidence candidates:

| Experiment | Filtered ranges | Notes |
|---|---|---|
| `change-track-pan` | **1** | Single byte at `0xc5` |
| `change-track-volume` | **2** | `0xc5` + `0x1ace9` |
| `mute-track` | **2** | `0xc5` + `0x1accf` |
| `move-region` | **2** | `0x12cb` + `0x36465` |
| `change-tempo-1bpm` | **4** | Same uint32 value at 4 offsets |
| `resize-region` | **0** | Change may be entirely in appended bytes |
| `change-time-sig-3-4` | **14** | Time sig value confirmed at 2 offsets |

---

## Experiments with high range counts (structural changes)

These operations add or remove objects (tracks, regions, plugins) and produce many changed ranges even after noise filtering. The high counts are likely due to per-object UUIDs and inline data that shifts with each save.

| Experiment | Filtered ranges | Notes |
|---|---|---|
| `add-audio-track` | 11,260 | Large size delta (+116,679 bytes) — new track record |
| `add-midi-track` | 9,644 | Size delta +14,719 bytes |
| `reorder-tracks` | 9,643 | Same delta as add-midi-track — reorder may clone/rebuild track list |
| `add-plugin` | 8,370 | `near='Channel EQ'` string visible near changed offsets |
| `add-region` | 7,884 | Size delta +111,211 bytes |
| `delete-track` | 6,933 | Size delta +926 bytes (positive — possibly metadata rewritten) |
| `duplicate-region` | 5,695 | `near='UCuA'` tag visible |
| `solo-track` | 269 | Higher than expected — solo may update state across all tracks |
| `delete-region` | 309 | `near='qeSM'` and `near='karT'` visible |
| `rename-track` | 478 | `near='Track Name Change'` string visible — undo record? |
| `add-tempo-change-bar9` | 9,262 | `near='qeSM'` visible — sequence event added |

---

## Version compatibility

| Field | 10.4.8 arm64 | Other versions |
|---|---|---|
| Tempo offsets (`0xaa`, `0x102`, `0x3be`, `0x12cc`) | ✓ confirmed | Not yet tested |
| Pan/mixer byte (`0xc5`) | ✓ confirmed | Not yet tested |
| gnoS magic bytes | ✓ confirmed | Not yet tested |

Cross-version data is needed. If you are on Intel (x86_64) or a different GarageBand version, your contribution is especially valuable.

---

## Methodology notes

- All diffs are against the `ProjectData` binary after noise filtering via `learn-noise`
- A no-op save (open baseline → save immediately → diff) produces 18,629 changed ranges on GB 10.4.8 arm64 — these are masked automatically
- Byte offsets are into the raw `ProjectData` file (gnoS format), not an NSKeyedArchiver blob
- The uint32 tempo value `1210000` = 60,000,000 ÷ 49.6 BPM — needs verification with a known BPM change
- Tag strings like `karT`, `qeSM`, `tSxT` suggest a self-describing struct format with 4-byte reversed type tags

---

## Open questions

- [ ] Is the tempo uint32 value in µs/beat? Needs verification by changing to a known BPM and checking the math.
- [ ] Why does `solo-track` produce 269 changed ranges when `mute-track` produces only 2? Solo may update a global solo-active flag across all tracks.
- [ ] Are the 4-byte reversed tags (`karT`, `qeSM` etc.) a fixed struct registry or variable?
- [ ] Are track records stored contiguously or as a linked/indexed structure?
- [ ] Are region positions stored as bar numbers, tick offsets, or sample positions?
- [ ] Do plugin parameters live in this blob or in separate files under `Media/`?
- [ ] Does the format differ meaningfully between GarageBand and Logic Pro X?
- [ ] Why does `delete-track` produce a positive size delta (+926 bytes) when a track was removed?

---

*Last updated: 2026-03-07 — GarageBand 10.4.8 arm64, 18/18 canonical experiments*
