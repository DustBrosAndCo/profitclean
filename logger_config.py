import logging
import os
from datetime import datetime

def setup_logging():
    """Configure structured logging for the application."""
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Generate log filename with current date
    log_filename = os.path.join(log_dir, f"profitclean_{datetime.now().strftime('%Y%m%d')}.log")
    
    # Configure logging format
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()  # Also log to console
        ]
    )
    
    return logging.getLogger(__name__)

# Create a module-level logger
logger = setup_logging()
