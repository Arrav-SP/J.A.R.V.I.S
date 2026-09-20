"""Root launcher for JARVIS.

Allows starting JARVIS directly via `python main.py`.
"""

import sys
from app.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
