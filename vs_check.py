#!/usr/bin/env python3
import os, sys, importlib.util, platform, subprocess

def sh(cmd):
    try:
        out = subprocess.check_output(cmd, shell=True, text=True).strip()
        return out if out else "(not found)"
    except Exception:
        return "(error)"

print(f"OS: {platform.platform()}")
print(f"Python: {sys.executable}  ({sys.version.split()[0]})")

# Python module path
try:
    spec = importlib.util.find_spec("vapoursynth")
    origin = spec.origin if spec else None
    print(f"vapoursynth module: {origin or '(not importable)'}")
except Exception as e:
    print(f"vapoursynth module: (error: {e})")

# Common Homebrew locations
for p in [
    "/opt/homebrew/Frameworks/VapourSynth.framework",
    "/usr/local/Frameworks/VapourSynth.framework",
    "/opt/homebrew/lib/vapoursynth",
    os.path.expanduser("~/Library/VapourSynth/plugins"),
]:
    print(f"{p}: {'exists' if os.path.exists(p) else 'missing'}")

print("brew --prefix vapoursynth:", sh("brew --prefix vapoursynth"))
print("vspipe:", sh("command -v vspipe"))
