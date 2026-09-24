"""Source checkout launcher. Installed users can run `alder`."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "src"))
from alder.launcher import main

if __name__ == "__main__":
    sys.exit(main())
