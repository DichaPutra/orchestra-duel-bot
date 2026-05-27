import sys
from pathlib import Path

from loguru import logger


class LoggerManager:
    """
    A helper class to configure and manage Loguru logging.
    """

    def __init__(self, file_path: str | Path, rotation: str = "10 MB"):
        """
        :param file_path: Name or path of the script file
        :param rotation: Log file rotation rule (e.g., "10 MB", "1 day", etc.)
        """
        self.file_path = Path(file_path).resolve()
        self.log_path = get_log_path(self.file_path)
        self.rotation = rotation
        self.logger = logger
        self.log_parent_directory = self.file_path.parent
        self._configure_logger()

    def _configure_logger(self) -> None:
        """
        Sets up the logger so that logs are always stored next to the script.
        """
        self.logger.remove()

        self.logger.add(
            self.log_path,
            rotation=self.rotation,
            enqueue=True,
            encoding="utf-8",
        )

        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")

        self.logger.add(sys.stdout)

        self.logger.info(f'Logger initialized at "{self.log_path.name}"...')

    def get_logger(self):
        """Return the configured logger."""
        return self.logger


def get_log_path(file_path: str | Path) -> Path:
    """
    Given a Python script path (usually __file__),
    return a log path in the same directory with the same basename but .log extension.

    Example:
        my_client.py -> my_client.log
    """
    script_path = Path(file_path).resolve()
    return script_path.with_suffix(".log")
