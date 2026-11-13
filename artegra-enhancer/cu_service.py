"""Launch the standalone service, optionally with explicitly selected packages."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = os.environ.get('CU_SITE_PACKAGES', '')
sys.path[:0] = [str(ROOT)] + ([SITE] if SITE and Path(SITE).is_dir() else [])

from service.app import main

if __name__ == '__main__':
    sys.exit(main())
