"""Enable ``python -m netlist_modifications ...``."""

import sys

from .insert_modification.cli import main

if __name__ == "__main__":
    sys.exit(main())
