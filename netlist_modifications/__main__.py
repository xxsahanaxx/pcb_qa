"""Enable ``python -m netlist_trojans ...``."""

import sys

from .insert_trojan.cli import main

if __name__ == "__main__":
    sys.exit(main())
