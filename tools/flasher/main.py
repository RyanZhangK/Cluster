"""Entry point for the Cluster Firmware Flasher."""

import sys

from PySide6.QtWidgets import QApplication

from tools.flasher.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Cluster Flasher")
    app.setOrganizationName("Cluster")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
