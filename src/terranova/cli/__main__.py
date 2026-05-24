"""``python -m terranova.cli`` entry point — mirrors the installed ``terranova`` script."""

from __future__ import annotations

import sys

from .main import main

if __name__ == "__main__":
    sys.exit(main())
