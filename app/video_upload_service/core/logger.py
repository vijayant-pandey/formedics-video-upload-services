import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)

logger = logging.getLogger("video_upload_service")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
formatter = logging.Formatter(
    '{"time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}'
)

handler.setFormatter(formatter)
logger.addHandler(handler)
logger.propagate = False