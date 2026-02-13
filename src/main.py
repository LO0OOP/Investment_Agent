from src.common.config import settings
from src.common.logger import get_logger, setup_logging


logger = get_logger(__name__)

def main():
    setup_logging(level=settings.app["log_level"])
    logger.info("App starting")
    logger.info(f"Env: {settings.env}")
    logger.info(f"LLM model: {settings.llm['model']}")

if __name__ == "__main__":
    main()

