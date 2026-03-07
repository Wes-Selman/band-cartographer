## Research submission

<!-- Fill in your environment details -->
- **GarageBand version:**
- **macOS version:**
- **Architecture:** Intel x86_64 / Apple Silicon arm64 (delete one)
- **CbVersion** (from research.json):

## Experiments completed

<!-- Check all that apply -->
- [ ] add-audio-track
- [ ] add-midi-track
- [ ] delete-track
- [ ] rename-track
- [ ] reorder-tracks
- [ ] add-region
- [ ] move-region
- [ ] resize-region
- [ ] delete-region
- [ ] duplicate-region
- [ ] change-tempo-1bpm
- [ ] change-time-sig-3-4
- [ ] add-tempo-change-bar9
- [ ] change-track-volume
- [ ] change-track-pan
- [ ] mute-track
- [ ] solo-track
- [ ] add-plugin

## Baseline verification

<!-- What did verify-baseline print? -->
- [ ] Hash matched (file unopened)
- [ ] Hash mismatch with structural check passed (file was opened in GarageBand — this is fine)
- [ ] Other (describe below)

## Notable findings

<!-- Anything interesting or unexpected in your results?
     Unusual size deltas, experiments that produced no diff, anything worth flagging. -->

## Checklist

- [ ] research.json is in `research/<version>_<arch>/research.json`
- [ ] No .band files included in this PR
- [ ] No personal audio or project files included
