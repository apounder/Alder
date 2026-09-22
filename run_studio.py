"""Source checkout launcher. Installed users can run `molecule-studio`."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "src"))
from molecule_studio.launcher import main

if __name__ == "__main__":
    sys.exit(main())
