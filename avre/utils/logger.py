
import logging
import sys
from avre.database import log_event

class DatabaseHandler(logging.Handler):
    def __init__(self, session_id):
        super().__init__()
        self.session_id = session_id

    def emit(self, record):
        msg = self.format(record)
        log_event(self.session_id, record.levelname, msg)

def get_logger(name: str, session_id: str = None):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        # Console Handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # Database Handler (if session_id provided)
        if session_id:
            db_handler = DatabaseHandler(session_id)
            db_handler.setLevel(logging.INFO)
            db_handler.setFormatter(formatter)
            logger.addHandler(db_handler)
    
    return logger
