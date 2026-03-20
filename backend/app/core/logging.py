from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from pathlib import Path


request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def setup_logging(level: str, output: str = "stdout", file_path: str = "logs/backend.log") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level.upper())

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    output_normalized = (output or "stdout").strip().lower()
    use_stdout = output_normalized in {"stdout", "both"}
    use_file = output_normalized in {"file", "both"}

    if use_stdout:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(level.upper())
        stream_handler.addFilter(RequestIdFilter())
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    if use_file:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setLevel(level.upper())
        file_handler.addFilter(RequestIdFilter())
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
