"""Allow `python3 -m installer.menu` (see README-netinstall.md)."""
import sys

from installer.menu.text_menu import main

if __name__ == "__main__":
    sys.exit(main())
