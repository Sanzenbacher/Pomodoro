"""Alle Tests, jede Datei in einem eigenen Prozess -- die Betriebsart
(lokal/gehostet) steht beim Import fest.

    python tests/run.py
"""

import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

failed = []
for path in sorted(glob.glob(os.path.join(HERE, "test_*.py"))):
    print("== %s" % os.path.basename(path), flush=True)
    if subprocess.call([sys.executable, path, "-v"], cwd=os.path.dirname(HERE)):
        failed.append(os.path.basename(path))
print("\nFehlgeschlagen: %s" % ", ".join(failed) if failed else "\nAlle Tests gruen.")
sys.exit(1 if failed else 0)
