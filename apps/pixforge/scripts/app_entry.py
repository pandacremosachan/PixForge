"""Private source-checkout launcher owned by the PixForge application."""
from pathlib import Path
import os
import sys

scripts = str(Path(__file__).resolve().parent)
sys.path.insert(0, scripts)
os.environ["PYTHONPATH"] = scripts
os.environ["PYTHONIOENCODING"] = "utf-8"
from pixelforge.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
