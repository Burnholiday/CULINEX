from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from ingredient_usage_analyzer.config import APP_NAME, AppPaths
from ingredient_usage_analyzer.controllers.app_controller import AppController
from ingredient_usage_analyzer.db.database import Database
from ingredient_usage_analyzer.ui.main_window import MainWindow


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> int:
    configure_logging()
    paths = AppPaths.default()
    paths.ensure()
    database = Database(paths.database_path)
    database.initialize()
    controller = AppController(database, paths)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = MainWindow(controller)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
