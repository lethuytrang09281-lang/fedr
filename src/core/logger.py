import sys
from loguru import logger
from src.core.config import settings

logger.remove()
logger.add(sys.stdout, level=settings.LOG_LEVEL)
logger.add("logs/app.log", rotation="50 MB", retention="10 days", level="INFO")