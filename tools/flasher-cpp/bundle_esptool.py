"""Entry point for PyInstaller-bundled esptool."""

import sys

from esptool import main

if __name__ == "__main__":
    sys.exit(main())
