"""Check readiness without installing tools, loading models, or contacting services."""
import importlib.util
import json
import shutil
import sys
from video_common import entry, run

FILTERS = "scale setsar pad fps format tpad trim setpts aresample aformat apad atrim asetpts anullsrc overlay loudnorm".split()
ENCODERS = ["libx264", "aac", "pcm_s16le"]


def check(subtitles=False):
    report = {"python": sys.version.split()[0], "text_ready": sys.version_info >= (3, 8)}
    for tool in ("ffmpeg", "ffprobe"):
        report[tool] = shutil.which(tool)
        if report[tool]:
            report[tool + "_version"] = run([tool, "-version"]).splitlines()[0]
    missing = []
    for kind, required in (("filters", FILTERS), ("encoders", ENCODERS)):
        listing = run(["ffmpeg", "-hide_banner", "-" + kind]) if report["ffmpeg"] else ""
        names = {line.split()[1] for line in listing.splitlines() if len(line.split()) >= 2}
        missing.extend(name for name in required if name not in names)
        if kind == "filters":
            report["srt_burn_ready"] = "subtitles" in names
    report["missing_render_features"] = missing
    report["render_ready"] = bool(report["text_ready"] and report["ffprobe"] and report["ffmpeg"] and not missing)
    report["optional_transcription"] = {name: importlib.util.find_spec(name) is not None
                                         for name in ("whisper", "faster_whisper")}
    report["note"] = "Transcription is optional and not run here; missing packages do not block text work or reviewed EDL rendering."
    if subtitles and not report["srt_burn_ready"]:
        report["render_ready"] = False
    return report


def main():
    report = check()
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["render_ready"] else 1)


if __name__ == "__main__":
    entry(main)
