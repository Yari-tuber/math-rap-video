"""旧入口，保留给老教程用：现在检查环境请用 mrv.py doctor（它还会告诉你怎么修）。"""
import subprocess
import sys
from pathlib import Path

sys.exit(subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "mrv.py"), "doctor", *sys.argv[1:]]).returncode)
