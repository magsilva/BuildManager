import logging
import sys

__all__ = ["Error", "logger"]

class Error(Exception):
    pass

def getlogger():
    class Formatter(logging.Formatter):
        def format(self, record):
            if record.levelname == "INFO":
                record.llevelname = ""
            else:
                record.llevelname = record.levelname.lower()+": "
            return logging.Formatter.format(self, record)
    formatter = Formatter("%(llevelname)s%(message)s")
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    bm_logger = logging.getLogger("bm")
    bm_logger.addHandler(handler)
    return bm_logger

logger = getlogger()

