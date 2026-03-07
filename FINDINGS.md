# Findings

This is the living summary of what has been confirmed about the GarageBand binary format. It is updated as new research is contributed.

**Status: No experiments submitted yet.** See [CONTRIBUTING.md](CONTRIBUTING.md) to add yours.

---

## Format overview

A `.band` file is a macOS bundle (folder) containing:

```
MySong.band/
  projectData       ← the main file — NSKeyedArchiver plist
  Alternatives/     ← GarageBand's own internal undo/version data
  Media/            ← audio files referenced by the project
  Resources/        ← thumbnails, waveform caches
```

The `projectData` file has two layers:

**Outer layer (fully readable):** NSKeyedArchiver format, decodable with `nska_deserialize`. Contains UI state, view settings, podcast metadata. Useful but not musically meaningful.

**Inner layer (partially opaque):** The `DfLogicModelLogicSong` object contains a binary blob — a proprietary Apple format starting with the magic bytes `gnoS` (= "Song" reversed, a classic Mac resource fork convention). This is where tracks, regions, tempo, and plugin state live.

---

## Confirmed field locations

*None confirmed yet — experiments needed.*

When experiments are submitted, this section will be updated with confirmed byte offset mappings like:

| Field | Offset | Type | Notes |
|---|---|---|---|
| *(pending)* | | | |

---

## Version compatibility

*No cross-version data yet.*

Fields that are confirmed stable across GarageBand versions will be marked ✓ here. Fields that vary by version will be noted with version ranges.

---

## Methodology notes

- Each entry in `research.json` represents one isolated change in GarageBand diffed against a minimal baseline project
- Byte ranges are reported as offsets into the `DfLogicModelLogicSong` NS.data blob, not the full `projectData` file
- `size_delta` values that are consistent across multiple track-type experiments suggest per-record sizes
- Float32 values near tempo experiments are candidates for BPM storage
- Offsets that change across many experiments (especially non-musical ones) are likely timestamps or version counters and should be ignored for parsing purposes

---

## Open questions

- [ ] Is the inner blob a versioned format with its own header/magic?
- [ ] Are track records stored contiguously or as a linked structure?
- [ ] Are region positions stored as bar numbers, tick offsets, or sample positions?
- [ ] Do plugin parameters live in this blob or in separate files under `Media/`?
- [ ] Does the format differ meaningfully between GarageBand and Logic Pro?

---

*Last updated: pending first contributions*
