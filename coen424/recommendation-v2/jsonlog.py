"""One JSON object per log line, in the same shape as v1's logs.

Extra fields passed as `extra={"fields": {...}}` are merged into the line, so a
request log can carry latency, validity, tokens, etc. as searchable fields.
"""

import json
import logging
import sys
import time


class JsonFormatter(logging.Formatter):
    def format(self, record):
        line = {
            "timestamp": time.time(),
            "severity": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        line.update(getattr(record, "fields", {}))
        return json.dumps(line)


def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
