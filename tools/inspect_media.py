"""Read-only, recursive inventory; no model-based transcription or take selection."""
import argparse
import json
import os
from pathlib import Path
from video_common import entry, local, probe, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.path).resolve(strict=True)
    output = local(args.output, Path.cwd(), existing=False)
    if root == output or root in output.parents:
        raise ValueError("Inventory output must be outside the source tree")
    if root.is_file():
        paths = [root]
    elif root.is_dir():
        paths = [Path(folder) / name for folder, _, names in os.walk(root) for name in names]
    else:
        raise ValueError("Expected a file or directory")
    items = []
    for path in sorted(paths, key=lambda p: p.relative_to(root.parent if root.is_file() else root).as_posix()):
        item = {"path": str(path), "relative_path": path.name if root.is_file() else path.relative_to(root).as_posix()}
        try:
            if path.is_symlink() or not path.is_file():
                raise ValueError("Skipped symlink or non-regular file")
            item.update(bytes=path.stat().st_size, sha256=sha256(path))
            metadata = probe(path)
            streams = metadata.get("streams", [])
            item.update(format=metadata.get("format", {}), streams=streams,
                        has_audio=any(s["codec_type"] == "audio" for s in streams),
                        rotation=[{"stream_index": s["index"], "tag": s.get("tags", {}).get("rotate"),
                                   "side_data": s.get("side_data_list", [])} for s in streams if s["codec_type"] == "video"])
        except (ValueError, OSError) as error:
            item["error"] = str(error)
        items.append(item)
    with output.open("x", encoding="utf-8") as handle:
        json.dump({"root": str(root), "files": items}, handle, indent=2)
        handle.write("\n")
    print("{} files inventoried: {}".format(len(items), output))


if __name__ == "__main__":
    entry(main)
