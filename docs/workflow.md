# From research to a reviewed edit

The studio separates editorial judgment from repeatable media processing. An assistant can help organize research, propose a script, and prepare an edit plan; a reviewed JSON file is the renderer's input.

## 1. Capture the evidence

Start with the [research packet](../templates/research-packet.md). Give claims stable IDs, keep their primary-source URLs and dates, and mark uncertainty. Imported research is not automatically current or approved.

## 2. Write for the footage you can make

Use the [script template](../templates/script.md) to connect spoken beats to claims, shot choices, and possible overlays. Keep citations in production notes rather than accidentally feeding them into spoken copy. A draft is not permission to publish.

## 3. Review takes and cuts

Use the [edit plan](../templates/edit-plan.md) to record source timestamps, selected takes, rejected alternatives, asset rights, and cuts needing approval. The tools do not watch the footage or decide which delivery is best.

Run `tools/inspect_media.py` for stream metadata and hashes. Keep the inventory outside the source directory. Translate approved choices into the example EDL, with each source path relative to the EDL's directory.

## 4. Validate, then render

`tools/render_video.py` validates file paths, the strict JSON schema, finite timestamps, clip duration bounds, and overlay placement. Without `--execute`, it prints the render plan and does not create media.

With `--execute`, it creates a vertical rough cut. Existing outputs are refused. A failed render preserves intermediates and an FFmpeg log for diagnosis. See the [renderer reference](local-video-tools.md) for details.

## 5. Review the result

Use the [production status template](../templates/production-status.md) to record which checks actually happened:

- Watch and listen end-to-end for cut quality, meaning, sync, rotation, and levels.
- Check names, claims, subtitle timing, and readability.
- Confirm asset rights and any needed disclosures.
- Preview safe areas on the intended platform.

Keep technical validation, human approval, and publication as separate states. Nothing in this public toolkit posts a video or connects a social account.
