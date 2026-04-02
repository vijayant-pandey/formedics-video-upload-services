from video_upload_service.core.logger import logger
from time import time

# Upload Metrics 
def metric_upload_created(session_id: str):
    logger.info(f'METRIC upload_created session_id={session_id}')\

#  Ingest Metrics
def metric_ingest_started(session_id: str):
    logger.info(f'METRIC ingest_started session_id={session_id}')


def metric_ingest_completed(session_id: str):
    logger.info(f'METRIC ingest_success session_id={session_id}')


def metric_ingest_failed(session_id: str):
    logger.info(f'METRIC ingest_failed session_id={session_id}')


# Duration Timer
_ingest_timer = {}


def ingest_timer_start(session_id: str):
    _ingest_timer[session_id] = time()


def ingest_timer_end(session_id: str):
    start = _ingest_timer.get(session_id)
    if not start:
        return
    duration = time() - start
    logger.info(f'METRIC ingest_duration session_id={session_id} seconds={duration}')
    _ingest_timer.pop(session_id, None)

# ingest success rate tracking

_ingest_success = 0
_ingest_fail = 0


def metric_ingest_success_rate(session_id: str, success: bool):

    global _ingest_success, _ingest_fail

    if success:
        _ingest_success += 1
    else:
        _ingest_fail += 1

    total = _ingest_success + _ingest_fail
    rate = (_ingest_success / total) * 100 if total else 0

    from video_upload_service.core.logger import logger
    logger.info(
        f"METRIC ingest_success_rate={rate:.2f}% session_id={session_id}"
    )

# Upload failure metrics
_upload_failures = 0

def metric_upload_failure(session_id: str, reason: str):

    global _upload_failures
    _upload_failures += 1

    from video_upload_service.core.logger import logger
    logger.info(
        f"METRIC upload_failure count={_upload_failures} session_id={session_id} reason={reason}"
    )

def metric_upload_completed(session_id: str):
    logger.info(f"METRIC upload_completed session_id={session_id}")
