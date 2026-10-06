"""Synthetic integration test. Keeps fixtures/results outside the export package."""
import argparse
import array
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from video_common import entry, probe, sha256
from doctor import check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", required=True, help="Existing directory outside this package")
    base = Path(parser.parse_args().workdir).resolve(strict=True)
    tools = Path(__file__).resolve().parent
    if tools.parent == base or tools.parent in base.parents:
        raise ValueError("Fixtures must be outside the export package")
    readiness = check(subtitles=True)
    if not readiness["render_ready"]:
        raise ValueError("The full smoke test requires FFmpeg/ffprobe, the base rendering features, "
                         "and the subtitles filter (libass). Run tools/doctor.py for details.")
    work = Path(tempfile.mkdtemp(prefix="video smoke ", dir=base))
    raw = work / "raw clips"
    raw.mkdir()
    def call(args, ok=True):
        result = subprocess.run([str(x) for x in args], capture_output=True, text=True,
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        assert (result.returncode == 0) == ok, result.stderr
        return result
    ff = ["ffmpeg", "-v", "error", "-nostdin", "-n", "-threads", "1"]
    call(ff + ["-f", "lavfi", "-i", "color=red:s=192x108:r=30:d=1", "-f", "lavfi", "-i",
               "sine=frequency=440:sample_rate=48000:duration=1", "-c:v", "libx264", "-threads", "1",
               "-pix_fmt", "yuv420p", "-c:a", "aac", raw / "talking head.mp4"])
    call(ff + ["-f", "lavfi", "-i", "color=blue:s=192x108:r=30:d=1", "-c:v", "libx264",
               "-threads", "1", "-pix_fmt", "yuv420p", raw / "silent clip.mp4"])
    rotation = ["-display_rotation", "90"] if "-display_rotation" in call(["ffmpeg", "-h", "full"]).stdout else []
    call(ff + rotation + ["-i", raw / "silent clip.mp4", "-c", "copy", "-metadata:s:v:0", "rotate=90", raw / "rotated clip.mp4"])
    call(ff + ["-f", "lavfi", "-i", "color=yellow:s=64x32", "-frames:v", "1", "-threads", "1", work / "overlay image.png"])
    (raw / "notes.txt").write_text("Not media; inventory must still hash it.\n", encoding="utf-8")
    caption = work / "captions '[safe],:.srt"
    caption.write_text("1\n00:00:00,133 --> 00:00:00,700\nREVIEWED\n", encoding="utf-8")
    data = {"version": 1, "clips": [{"source": "raw clips/talking head.mp4", "start": 0.1, "end": 0.5},
                                    {"source": "raw clips/silent clip.mp4", "start": 0, "end": 0.4}],
            "overlays": [{"source": "overlay image.png", "x": 100, "y": 100, "width": 200, "start": 0.1, "end": 0.6}],
            "subtitles": caption.name}
    edl = work / "edit.json"
    edl.write_text(json.dumps(data), encoding="utf-8")
    before = {p.name: sha256(p) for p in raw.iterdir()}
    call([sys.executable, "-B", tools / "inspect_media.py", raw, "--output", work / "inventory.json"])
    inventory = json.loads((work / "inventory.json").read_text())["files"]
    assert [i["relative_path"] for i in inventory] == sorted(before)
    assert all(i["sha256"] == before[i["relative_path"]] for i in inventory)
    assert not next(i for i in inventory if i["relative_path"] == "silent clip.mp4")["has_audio"]
    assert "rotation" in str(next(i for i in inventory if i["relative_path"] == "rotated clip.mp4")["rotation"])
    command = [sys.executable, "-B", tools / "render_video.py", edl, "rough cut.mp4"]
    snapshot = sorted(str(p) for p in work.rglob("*"))
    dry = call(command)
    assert json.loads(dry.stdout)["mode"] == "dry-run" and snapshot == sorted(str(p) for p in work.rglob("*"))
    call(command + ["--execute"])
    final = work / "rough cut.mp4"
    meta = probe(final)
    video, audio = meta["streams"]
    assert (video["width"], video["height"], video["codec_name"], video["r_frame_rate"]) == (1080, 1920, "h264", "30/1")
    assert audio["codec_name"] == "aac" and audio["channels"] == 2 and audio["sample_rate"] == "48000"
    assert abs(float(meta["format"]["duration"]) - 0.8) < 0.04
    def pixels(time, crop):
        return subprocess.check_output(["ffmpeg", "-v", "error", "-ss", str(time), "-i", str(final),
                                       "-vf", crop, "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
    assert min(pixels(0.2, "crop=2:2:110:110")[:2]) > 180  # yellow overlay in black pad
    assert max(pixels(0.75, "crop=2:2:110:110")) < 15  # overlay switched off
    frame = pixels(0.2, "null")
    white = [i for i, rgb in enumerate(zip(frame[0::3], frame[1::3], frame[2::3])) if min(rgb) > 180]
    bounds = [min(i % 1080 for i in white), min(i // 1080 for i in white),
              max(i % 1080 for i in white), max(i // 1080 for i in white)]
    assert 60 <= bounds[0] < bounds[2] < 1020 and 80 <= bounds[1] < bounds[3] < 1700
    assert max(pixels(0.2, "crop=1080:220:0:1700")) < 15  # bottom 220 stays clear
    assert max(pixels(0.75, "crop=1080:600:0:1320")) < 15  # captions switched off
    samples = array.array("h", subprocess.check_output(["ffmpeg", "-v", "error", "-ss", "0.6", "-i", str(final),
                                                       "-map", "0:a", "-f", "s16le", "-"]))
    assert max(abs(s) for s in samples) < 100  # absent source audio becomes silence
    audible = array.array("h", subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(final),
                                                       "-t", "0.2", "-map", "0:a", "-f", "s16le", "-"]))
    assert max(abs(s) for s in audible) > 1000
    assert "Refusing overwrite" in call(command + ["--execute"], ok=False).stderr
    assert "Refusing overwrite" in call(command[:-1] + ["raw clips/silent clip.mp4", "--execute"], ok=False).stderr
    for change in ("trim", "unknown", "boolean", "nan", "overlay"):
        bad = json.loads(json.dumps(data))
        if change == "trim": bad["clips"][0]["end"] = 99
        if change == "unknown": bad["clips"][0]["speed"] = 2
        if change == "boolean": bad["clips"][0]["start"] = True
        if change == "nan": bad["clips"][0]["end"] = float("nan")
        if change == "overlay": bad["overlays"][0]["end"] = 99
        invalid = work / ("invalid-" + change + ".json")
        invalid.write_text(json.dumps(bad), encoding="utf-8")
        call(command[:3] + [invalid, "invalid.mp4", "--execute"], ok=False)
        assert not (work / "invalid.mp4").exists()
    assert not list(work.glob(".julie-render-*"))
    assert before == {p.name: sha256(p) for p in raw.iterdir()}
    tiny = work / "tiny-silent.json"
    tiny.write_text(json.dumps({"version": 1, "clips": [{"source": "raw clips/silent clip.mp4", "start": 0.99, "end": 1}]}), encoding="utf-8")
    call(command[:3] + [tiny, "tiny-silent.mp4", "--execute"])
    assert probe(work / "tiny-silent.mp4")["streams"][0]["nb_frames"] == "1"
    (work / "broken.srt").write_text("This is not an SRT cue", encoding="utf-8")
    data["subtitles"] = "broken.srt"
    broken = work / "broken-edit.json"
    broken.write_text(json.dumps(data), encoding="utf-8")
    assert "Intermediates preserved" in call(command[:3] + [broken, "broken.mp4", "--execute"], ok=False).stderr
    assert not (work / "broken.mp4").exists() and list(work.glob(".julie-render-*/ffmpeg.log"))
    report = dict(status="PASS", workdir=str(work), final=str(final), duration_seconds=0.8, caption_bounds_xyxy=bounds,
                  checks="inventory/hash/rotation; dry-run; spaces; silent and audible audio; contain/pad; timed overlay; safe SRT path and caption safe area; H264/AAC; invalid bounds/schema/numbers; no overwrite; source integrity; success cleanup; tiny silent tail-frame render; failure preservation")
    (work / "test-results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    entry(main)
