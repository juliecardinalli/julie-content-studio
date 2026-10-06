"""Shared, local-only helpers. Python 3.8+; no third-party Python packages."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys


def run(args, cwd=None):
    result = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True)
    if result.returncode:
        raise ValueError("{} failed: {}".format(args[0], result.stderr[-3000:].strip()))
    return result.stdout


def local(value, base, existing=True):
    if not isinstance(value, str) or not value or "://" in value or any(ord(c) < 32 for c in value):
        raise ValueError("Expected a nonempty local path without control characters")
    path = Path(value)
    path = path if path.is_absolute() else base / path
    if not existing and os.path.lexists(path):
        raise ValueError("Refusing overwrite: {}".format(path))
    path = path.resolve(strict=existing)
    if existing and not path.is_file():
        raise ValueError("Not a regular file: {}".format(path))
    if not existing and not path.parent.is_dir():
        raise ValueError("Output parent must already exist: {}".format(path.parent))
    return path


def probe(path):
    return json.loads(run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
                           "-show_format", "-show_streams", "-of", "json", path]))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def number(value, label):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("{} must be a finite nonnegative number".format(label))
    return value


def keys(obj, required, optional=()):
    if not isinstance(obj, dict) or not set(required) <= obj.keys() or obj.keys() - set(required) - set(optional):
        raise ValueError("Expected keys {} (optional {})".format(required, optional))


def entry(main):
    try:
        main()
    except (ValueError, OSError, KeyboardInterrupt) as error:
        print("ERROR: {}".format(error or "Interrupted"), file=sys.stderr)
        sys.exit(1)
