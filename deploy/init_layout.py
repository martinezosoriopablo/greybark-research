#!/usr/bin/env python
"""
init_layout.py — Initialize Layout directory for Docker/Railway
================================================================
Copies platform files into GREYBARK_LAYOUT_DIR and seeds the database
if it doesn't exist yet.

Run once after deploy or when the volume is empty:
    python deploy/init_layout.py
"""

import os
import sys
import shutil
from pathlib import Path

LAYOUT_DIR = Path(os.environ.get("GREYBARK_LAYOUT_DIR", "/app/layout"))
CONSEJO_DIR = Path(__file__).resolve().parent.parent  # consejo_ia/

# Files to copy from the local Layout/ directory
# (these should be in the repo or mounted)
_LOCAL_LAYOUT = CONSEJO_DIR.parent.parent.parent / "Layout"


def main():
    print(f"  Layout dir: {LAYOUT_DIR}")
    LAYOUT_DIR.mkdir(parents=True, exist_ok=True)
    (LAYOUT_DIR / "output").mkdir(exist_ok=True)

    # Copy platform module
    src = _LOCAL_LAYOUT / "greybark_platform.py"
    if src.exists():
        shutil.copy2(str(src), str(LAYOUT_DIR / "greybark_platform.py"))
        print(f"  [+] greybark_platform.py")

    # Copy passwords
    src = _LOCAL_LAYOUT / "passwords.json"
    dst = LAYOUT_DIR / "passwords.json"
    if src.exists() and not dst.exists():
        shutil.copy2(str(src), str(dst))
        print(f"  [+] passwords.json")

    # Copy/seed database
    src = _LOCAL_LAYOUT / "greybark.db"
    dst = LAYOUT_DIR / "greybark.db"
    if src.exists() and not dst.exists():
        shutil.copy2(str(src), str(dst))
        print(f"  [+] greybark.db (copied)")
    elif not dst.exists():
        # Seed fresh DB
        sys.path.insert(0, str(LAYOUT_DIR))
        try:
            seed_src = _LOCAL_LAYOUT / "seed_test_clients.py"
            if seed_src.exists():
                shutil.copy2(str(seed_src), str(LAYOUT_DIR / "seed_test_clients.py"))
                os.environ["GREYBARK_DB"] = str(dst)
                import importlib.util
                _spec = importlib.util.spec_from_file_location("seed_test_clients", str(LAYOUT_DIR / "seed_test_clients.py"))
                _mod = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)
                print(f"  [+] greybark.db (seeded)")
        except Exception as e:
            print(f"  [WARN] Could not seed DB: {e}")

    # Copy sync_reports if available
    src = _LOCAL_LAYOUT / "sync_reports.py"
    if src.exists():
        shutil.copy2(str(src), str(LAYOUT_DIR / "sync_reports.py"))
        print(f"  [+] sync_reports.py")

    print(f"  Layout initialized at {LAYOUT_DIR}")


if __name__ == "__main__":
    main()
