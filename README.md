# Julie Content Studio

A local video-editing toolkit and an AI-assisted editorial workflow for turning research and raw clips into reviewed short-form videos.

I built this around my own content-production process: keep research tied to its sources, choose takes deliberately, and automate the repetitive assembly work. The creative decisions stay reviewable; the renderer follows an explicit edit decision list.

This is the **public, code-only edition** of my working studio. It includes the reusable tools, blank production templates, and workflow—not my unpublished scripts, research archive, raw footage, or account credentials.

## What it does

- Inventories local media with stream metadata, rotation, audio presence, and SHA-256 hashes.
- Validates a JSON edit decision list before doing any rendering.
- Trims and sequences clips, fits them into a vertical frame without forced cropping, and adds timed image overlays and reviewed SRT captions.
- Exports 1080 × 1920, 30 fps H.264 video with stereo AAC audio.
- Refuses to overwrite existing output files and preserves diagnostic files when a render fails.

The Python tools use only the standard library plus FFmpeg/ffprobe. They run locally, make no API calls, and need no API keys. AI-assisted research, writing, and editorial decisions happen separately; this is not an autonomous video editor.

## Try it without supplying footage

Requirements: Python 3.10+ and FFmpeg with `libx264`, AAC, and the `subtitles` filter. Install those separately if needed; the scripts do not install anything.

```sh
git clone https://github.com/juliecardinalli/julie-content-studio.git
cd julie-content-studio
python3 tools/doctor.py
python3 -m unittest discover -s tests -v

# Creates synthetic clips, an overlay, captions, and a short rendered example.
# No personal footage or paid services are used.
test_dir=$(mktemp -d)
python3 -B tools/smoke_test.py --workdir "$test_dir"
```

The smoke test prints the output path and its checks. It exercises silent and audible clips, rotation metadata, overlay timing, caption placement, schema rejection, dry-run behavior, source integrity, and overwrite protection. Its short synthetic output is a technical demo, not a finished creative edit.

## Use your own clips

1. Put your footage in `files/raw-clips/<slug>/` and owned or licensed overlays in `files/overlays/<slug>/`. These folders are ignored by Git.
2. Create `files/edits/<slug>/` and `files/exports/`.
3. Copy [`templates/edit-decision-list.example.json`](templates/edit-decision-list.example.json) into the edit folder as `edit.json`. Replace the example paths and trim ranges; remove overlays or subtitles if you are not using them.
4. Review a dry run, then explicitly execute it:

```sh
python3 tools/inspect_media.py files/raw-clips/my-video \
  --output files/edits/my-video/inventory.json

python3 tools/render_video.py files/edits/my-video/edit.json \
  ../../exports/my-video_rough_v1.mp4

python3 tools/render_video.py files/edits/my-video/edit.json \
  ../../exports/my-video_rough_v1.mp4 --execute
```

Media paths and the output path are relative to the **edit JSON's directory**, not the shell's working directory. Watch and listen to the entire export before approving it.

See the [renderer reference](docs/local-video-tools.md) for the exact schema, timing rules, and limitations.

## Workflow and design choices

Research packet → script and shot list → take map → reviewed edit decisions → dry run → render → playback review.

The [editorial workflow](docs/workflow.md) explains the handoffs. Blank templates keep source claims, asset permissions, approvals, and unresolved questions attached to each production.

| Choice | Reason |
|---|---|
| Explicit JSON edit decisions | Cuts and timings can be inspected before execution. |
| Local processing | Footage does not need to leave the machine. |
| Dry run by default | A proposed edit is separate from a rendered output. |
| Source hashes and no-overwrite output | Originals remain traceable and existing exports are preserved. |
| Separate technical tests and human review | A valid encode does not prove the edit tells the right story. |

## Repository layout

```text
tools/       Media inspection, validation, rendering, and synthetic integration test
tests/       Unit tests for input and path validation
templates/   Blank research, script, edit-plan, EDL, and production-status files
docs/        Workflow and renderer reference
```

## Scope

Implemented: local rough-cut assembly, static overlays, supplied SRT captions, and repeatable checks.

Not implemented: automatic take selection, transcription, motion graphics, a graphical timeline, platform publishing, or fully automatic quality review. The private studio's experimental podcast and avatar work is not part of this release.

Built by [Julie Cardinalli](https://jcardinalli.work/).
