import logging
import sys
import json
from datetime import datetime

class StructuredFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers if logger is retrieved multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        # Use structured formatter in production, readable in development
        formatter = StructuredFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger
