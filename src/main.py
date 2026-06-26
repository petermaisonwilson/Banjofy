from __future__ import annotations

import sys
from pathlib import Path

# Allow running from source without installing as a package.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from banjofy.app import run


if __name__ == "__main__":
    raise SystemExit(run())
