"""Launch the desktop, or use `python -m alder setup` in a terminal."""
import sys

if sys.argv[1:2] == ['setup']:
    from .setup_cli import main
    raise SystemExit(main(sys.argv[2:]))

from .launcher import main
raise SystemExit(main())
