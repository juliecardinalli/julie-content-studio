"""Reviewed EDL -> local rough cut. Read-only dry run unless --execute is supplied."""
import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from doctor import check
from video_common import entry, keys, local, number, probe, run

BASE = ["ffmpeg", "-hide_banner", "-nostdin", "-n", "-loglevel", "warning",
        "-filter_threads", "1", "-filter_complex_threads", "1"]
VIDEO = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-threads", "2"]


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def interval(obj, maximum):
    start, end = number(obj["start"], "start"), number(obj["end"], "end")
    if not start < end <= maximum:
        raise ValueError("Invalid trim/timeline bounds: {}..{}; maximum {}".format(start, end, maximum))
    return start, end


def prepare(edl, output):
    data = json.loads(edl.read_text(encoding="utf-8-sig"), object_pairs_hook=unique)
    keys(data, ("version", "clips"), ("overlays", "subtitles"))
    if type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("Only EDL version 1 is supported")
    if not isinstance(data["clips"], list) or not data["clips"]:
        raise ValueError("clips must be a nonempty array")
    clips, total = [], 0
    for clip in data["clips"]:
        keys(clip, ("source", "start", "end"))
        source = local(clip["source"], edl.parent)
        if source.suffix.lower() not in (".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts", ".m2ts"):
            raise ValueError("Unsupported video container: " + str(source))
        meta = probe(source)
        videos = [s for s in meta["streams"] if s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")]
        if not videos:
            raise ValueError("No video stream: " + str(source))
        video = videos[0]
        if video.get("duration") not in (None, "N/A"):
            duration = float(video["duration"])
        else:
            packets = json.loads(run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
                                      "-select_streams", str(video["index"]), "-show_packets",
                                      "-show_entries", "packet=pts_time,duration_time", "-of", "json", source]))["packets"]
            times = [(float(p["pts_time"]), float(p.get("duration_time", 0))) for p in packets if "pts_time" in p]
            duration = max((t + d for t, d in times), default=0) - min((t for t, _ in times), default=0)
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Cannot validate video duration: " + str(source))
        start, end = interval(clip, duration)
        frames = max(1, math.ceil(round((end - start) * 30, 9)))
        clips.append(dict(source=str(source), start=start, end=end, frames=frames, video=video["index"],
                          audio=next((s["index"] for s in meta["streams"] if s["codec_type"] == "audio"), None)))
        total += frames
    overlays = data.get("overlays", [])
    if not isinstance(overlays, list):
        raise ValueError("overlays must be an array")
    for overlay in overlays:
        keys(overlay, ("source", "x", "y", "width", "start", "end"))
        source = local(overlay["source"], edl.parent)
        if source.suffix.lower() not in (".png", ".jpg", ".jpeg", ".bmp"):
            raise ValueError("Overlay must be a static PNG, JPEG, or BMP")
        image = probe(source)["streams"][0]
        if image.get("codec_name") not in ("png", "mjpeg", "bmp"):
            raise ValueError("Animated/unsupported overlay")
        for field in ("x", "y", "width"):
            if type(overlay[field]) is not int or overlay[field] < (1 if field == "width" else 0):
                raise ValueError(field + " must be a nonnegative integer (width > 0)")
        if overlay["x"] + overlay["width"] > 1080 or overlay["y"] + math.ceil(overlay["width"] * image["height"] / image["width"]) > 1920:
            raise ValueError("Overlay must fit entirely inside 1080x1920")
        interval(overlay, total / 30)
        overlay["source"] = str(source)
    subtitles = local(data["subtitles"], edl.parent) if "subtitles" in data else None
    if subtitles and (subtitles.suffix.lower() != ".srt" or not subtitles.read_text(encoding="utf-8-sig").strip()):
        raise ValueError("subtitles must be a nonempty UTF-8 .srt file")
    target = local(output, edl.parent, existing=False)
    if target.suffix.lower() != ".mp4":
        raise ValueError("Output must end in .mp4")
    readiness = check(bool(subtitles))
    if not readiness["render_ready"]:
        raise ValueError("Rendering unavailable; run tools/doctor.py: " + json.dumps(readiness))
    return dict(clips=clips, overlays=overlays, subtitles=str(subtitles) if subtitles else None,
                output=str(target), duration_seconds=total / 30, frames=total,
                format="1080x1920 contain/pad; 30fps H.264; stereo AAC 48kHz; loudnorm I=-16 TP=-1.5 LRA=11")


def execute(plan):
    output = Path(plan["output"])
    temp = Path(tempfile.mkdtemp(prefix=".julie-render-", dir=output.parent))
    def ff(args):
        with (temp / "ffmpeg.log").open("a", encoding="utf-8") as log:
            log.write(json.dumps(BASE + [str(a) for a in args]) + "\n")
            log.flush()
            result = subprocess.run(BASE + [str(a) for a in args], cwd=temp, stdout=log, stderr=log)
        if result.returncode:
            raise ValueError("ffmpeg failed; read " + str(temp / "ffmpeg.log"))
    try:
        segments = []
        for i, clip in enumerate(plan["clips"]):
            duration = clip["frames"] / 30
            inputs = ["-protocol_whitelist", "file,pipe", "-ss", str(clip["start"]), "-noaccurate_seek", "-t",
                      str(clip["end"] - clip["start"]), "-i", clip["source"]]
            audio = "0:{}".format(clip["audio"])
            if clip["audio"] is None:
                inputs += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
                audio = "1:a"
            graph = "[0:{}]scale=w='max(2,trunc(min(1080,1920*dar)/2)*2)':h='max(2,trunc(min(1920,1080/dar)/2)*2)',setsar=1,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,tpad=stop_mode=clone:stop_duration=1,fps=30:start_time=0,trim=end_frame={},setpts=PTS-STARTPTS[v];[{}]aresample=48000:async=1:first_pts=0,aformat=sample_fmts=s16:channel_layouts=stereo,apad,atrim=duration={},asetpts=PTS-STARTPTS[a]".format(clip["video"], clip["frames"], audio, duration)
            name = "clip-{:05d}.mov".format(i)
            ff(inputs + ["-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-t", str(duration),
                         *VIDEO, "-c:a", "pcm_s16le", "-ar", "48000", "-map_metadata", "-1", name])
            segments.append("file '{}'\nduration {:.12f}\n".format(name, duration))
        (temp / "concat.txt").write_text("".join(segments), encoding="utf-8")
        inputs = ["-protocol_whitelist", "file,pipe", "-f", "concat", "-safe", "1", "-i", "concat.txt"]
        graph, video = [], "0:v"
        for i, overlay in enumerate(plan["overlays"], 1):
            inputs += ["-protocol_whitelist", "file,pipe", "-f", "image2", "-pattern_type", "none",
                       "-loop", "1", "-framerate", "30", "-i", overlay["source"]]
            graph.append("[{}:v]scale={}:-1,setsar=1[o{}];[{}][o{}]overlay={}:{}:enable='gte(t,{})*lt(t,{})'[v{}]".format(
                i, overlay["width"], i, video, i, overlay["x"], overlay["y"], overlay["start"], overlay["end"], i))
            video = "v{}".format(i)
        if plan["subtitles"]:
            shutil.copyfile(plan["subtitles"], temp / "captions.srt")
            style = "PlayResX=384,PlayResY=288,FontName=DejaVu Sans,FontSize=10,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=0.6,Shadow=0,Alignment=2,MarginV=48,MarginL=24,MarginR=24"
            graph.append("[{}]subtitles=filename=captions.srt:force_style='{}'[captioned]".format(video, style))
            video = "captioned"
        graph.append("[{}]fps=30,format=yuv420p[final]".format(video))
        graph.append("[0:a]apad=whole_dur=3,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[audio]")
        ff(inputs + ["-filter_complex", ";".join(graph), "-map", "[final]", "-map", "[audio]",
                     "-t", str(plan["duration_seconds"]), *VIDEO, "-c:a", "aac", "-b:a", "192k",
                     "-ar", "48000", "-ac", "2", "-map_metadata", "-1", "-movflags", "+faststart", "result.mp4"])
        if probe(temp / "result.mp4")["streams"][0].get("nb_frames") != str(plan["frames"]):
            raise ValueError("Final frame count differs from the plan; inspect preserved intermediates")
        with (temp / "result.mp4").open("rb") as source, output.open("xb") as target:
            shutil.copyfileobj(source, target)
    except BaseException:
        print("Intermediates preserved: " + str(temp), file=sys.stderr)
        raise
    shutil.rmtree(temp)
    print("Rough cut created; human review required: " + str(output), file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edl")
    parser.add_argument("output", help="MP4 path relative to EDL directory, not current directory")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    plan = prepare(local(args.edl, Path.cwd()), args.output)
    print(json.dumps(dict(mode="execute" if args.execute else "dry-run", **plan), indent=2))
    if args.execute:
        execute(plan)


if __name__ == "__main__":
    entry(main)
