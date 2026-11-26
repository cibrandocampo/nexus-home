"""Logging. The app's messages carry ids, never emails, names, codes or tokens; the access log keeps
the client address, method, path and status, without the query string (searches can hold emails)."""

import logging

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: str) -> None:
    configure_access_log()
    logger = logging.getLogger("app")
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(FORMAT))
        logger.addHandler(handler)
    # Records still propagate: uvicorn leaves the root logger without handlers (no duplicates), and
    # test tools such as pytest's caplog listen there.


class DropQueryString(logging.Filter):
    """uvicorn's access log record args: (client, method, path with query, http version, status)."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) == 5 and isinstance(args[2], str):
            record.args = (args[0], args[1], args[2].split("?", 1)[0], args[3], args[4])
        return True


def configure_access_log() -> None:
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, DropQueryString) for f in access.filters):
        access.addFilter(DropQueryString())
