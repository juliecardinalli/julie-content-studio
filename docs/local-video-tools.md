# Local video tools

A **reviewed-EDL rough-cut engine**, not an automatic editor, full motion-graphics
system, transcription service, editorial QA system, or CapCut-native project exporter.
Python 3.10+ standard library and an already-installed ffmpeg/ffprobe are the only
dependencies. Nothing installs, downloads, authenticates, calls a model, or incurs
API charges. No music is added; do not supply copyrighted music without permission.

## Review first; render second

Run these commands from the package root. Replace `example-video` with your slug.
Raw clips and overlays must already exist locally; the template is illustrative.

```sh
python3 tools/doctor.py
mkdir -p files/edits/example-video files/exports
cp templates/edit-decision-list.example.json files/edits/example-video/edit.json
python3 tools/inspect_media.py "files/raw-clips/example-video" --output "files/edits/example-video/inventory.json"
python3 tools/render_video.py files/edits/example-video/edit.json ../../exports/example-video_rough_v1.mp4
python3 tools/render_video.py files/edits/example-video/edit.json ../../exports/example-video_rough_v1.mp4 --execute
```

Before either render command, edit `files/edits/<slug>/edit.json` to reflect actual
files and reviewed trims. Keep `files/edits/<slug>/transcript-review.md` alongside it:
record source filename, source timestamps, manually supplied/corrected transcript,
approved takes and cuts, names/facts checked, caption corrections, reviewer/date,
and unresolved questions. Review silence cuts explicitly in the EDL: **no automatic
take selection, transcription, silence detection/cutting, or editorial approval
occurs**. A `.md` transcript is review evidence, not a timed subtitle input.
Supply corrected UTF-8 SRT as `captions-reviewed.srt` only when ready.

## Exact version 1 schema

The example JSON in `templates/edit-decision-list.example.json` is the schema's
working shape (no comments). Object keys are strict; unknown/duplicate keys fail.

| Object | Required keys | Optional keys |
|---|---|---|
| Root | `version`: integer `1`; `clips`: nonempty array of clip objects | `overlays`: array (default `[]`); `subtitles`: local UTF-8 `.srt` path |
| Clip | `source`: local video path; `start`, `end`: source seconds | None |
| Overlay | `source`: static PNG/JPEG/BMP path; `x`, `y`, `width`: pixel integers; `start`, `end`: full rendered-timeline seconds | None |

All times are finite JSON numbers, not strings/booleans/null; `0 <= start < end`.
Clip ends cannot exceed the selected video stream's duration. Cuts are sampled onto
the 30fps timeline (sub-frame precision is not possible). Clip lengths round
**up to whole 30fps frames**, with the last frame held for any fractional remainder;
the dry-run reports the resulting total and per-clip frame counts. Overlay end
cannot exceed that total; start is inclusive, end exclusive. Overlay dimensions
preserve image aspect; width is positive, x/y nonnegative, and the whole image must
fit the 1080×1920 canvas. Later array entries appear above earlier ones. SRT times
are also relative to the full rendered timeline; captions appear above overlays.
Omit optional keys when unused; `null` is not a substitute.

The single default caption style uses white DejaVu Sans (local font fallback if
unavailable), black outline, no shadow, centered at the bottom with a conservative
320px vertical inset. Libass is explicitly set to 384×288 reference units:
FontSize=10 (~67px high), MarginV=48, MarginL/R=24, Outline=0.6.
The smoke test measures actual caption pixels and confirms the bottom 220px stays
clear. Keep cues short; multiline overflow, long words and platform UI still
require human preview on the target platform. This is not automatic safe-area QA.

The EDL argument itself is relative to your current directory. **Every source,
subtitle, and output-video path is resolved relative to the EDL directory** unless
absolute. `../..` is intentional for sibling `files/raw-clips`, `files/overlays`,
and `files/exports` directories. URLs, control-character paths, nonexistent inputs,
and non-regular input files are rejected. Quote shell paths containing spaces.
Inspection's input/output paths instead resolve from the current directory.

## Behavior and limitations

- `doctor.py` reports Python, binaries/versions, required filters and encoders,
  optional libass subtitle support, and optional transcription-package availability.
  Missing transcription does not block text or EDL work; no models are loaded.
  Exit 1 means base rendering is unavailable, not that text creation is blocked.
- `inspect_media.py` recursively inventories files in sorted relative-path order,
  including non-media files with hashes and probe errors. JSON includes SHA-256,
  byte size, complete stream/container metadata (durations, audio, rotation tags
  and display matrices), and audio presence. It skips symlinks and never follows
  symlink directories. Output must be new and outside the source tree.
- Dry-run probes/validates and prints a plan without creating media or temp files.
  Rendering selects the first non-cover-art video and first audio stream, honors
  ffmpeg autorotation, contains/pads in black without forced cropping, and uses
  1080×1920, square pixels, 30fps, H.264 and stereo 48kHz AAC. Supported source
  containers: MP4/MOV/M4V/MKV/WebM/AVI/MTS/M2TS. Unsupported/unverifiable inputs fail.
- Each clip is standardized; missing/short audio is padded with silence. Concatenated
  audio receives single-pass `loudnorm=I=-16:TP=-1.5:LRA=11`. These are targets, not
  measured compliance guarantees; silent material stays silent. Inputs shorter than
  3 seconds are padded for normalization, then output is limited to the planned
  duration (avoids non-finite loudnorm samples on tiny silent inputs). No color/HDR
  mastering, motion graphics, transitions, animated overlays, or music mixing.
- Subtitle paths are copied into a private temp directory under a fixed safe name,
  never interpolated into filter syntax. Source paths use argument lists, no shell.
  Normal temp files are removed on success. On failure, intermediates and
  `ffmpeg.log` remain at the printed location. Source files are never modified.
  Existing outputs (including symlinks) are refused; publishing uses exclusive
  creation to avoid race overwrites. A disk/copy failure can leave a partial new
  output: inspect it and choose a fresh output name before retrying.
- Human end-to-end review remains mandatory: meaning, takes, cuts, sync, rotation,
  levels, caption accuracy/safe areas, overlay rights/readability, and disclosure.
  Identical EDL/build settings produce the same sequence; bytes/fonts may differ
  across ffmpeg versions and machines. No native editor timeline is produced.

## Synthetic smoke test

```sh
mkdir -p /tmp/julie-video-tests
python3 -B tools/smoke_test.py --workdir /tmp/julie-video-tests
```

The test keeps tiny synthetic fixtures, a 0.8-second vertical MP4, inventory and
`test-results.json` outside the package. It checks space-containing names, rotation
metadata, absent/present audio, contain/pad, timed image visibility, SRT burning
with punctuation in its filename, dry-run, trim/schema rejection, no overwrite,
source hashes, success cleanup, and failure preservation. It deliberately retains
one failed-render temp folder for the failure-preservation assertion.

Rerun the smoke test on your machine before using real footage. FFmpeg builds differ:
base rendering can be available even when the optional `subtitles` filter is missing.
The full synthetic test requires that filter; `doctor.py` reports it as
`srt_burn_ready`. Install a build with libass support if that field is false.
The GitHub Actions workflow runs the unit tests and synthetic render on Ubuntu.
