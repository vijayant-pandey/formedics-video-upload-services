from datetime import datetime

from video_upload_service.services.upload_service import UploadService
from video_upload_service.models.upload_session import UploadStatus


class PollingWorker:

    def __init__(self):
        self.upload_service = UploadService()

    def poll_status(self, session_id: str):

        # load session
        session = self.upload_service.get_session(session_id)

        # Only poll ingesting sessions
        if session.status != UploadStatus.INGESTING:
            return
        
        # part 6 watchdog --> ingest_stuck alert
        from datetime import timedelta
        from video_upload_service.core.logger import logger

        if session.status == UploadStatus.INGESTING and \
        datetime.utcnow() - session.updated_at > timedelta(minutes=30):
            logger.info(f"ALERT ingest_stuck session_id={session.id}")

        # Only poll ingesting sessions
        if session.status != UploadStatus.INGESTING:
            return

        # placeholder for real brightcove status api 
        # Later this will call Dynamic Ingest Status endpoint
        # For now simulate result

        # ingest_complete = False  # keep False for temporary fix

        # if ingest_complete:

        #     session.status = UploadStatus.COMPLETE
        #     session.updated_at = datetime.utcnow()

        #     # -------- CONCURRENCY SAFE WRITE --------
        #     self.upload_service.storage.write_json(
        #         f"uploads/{session_id}/session.json",
        #         session.model_dump(),
        #         expected_generation=session._generation
        #     )

        #     # -------- AUDIT EVENT --------
        #     self.upload_service.event_service.write_event(
        #         session_id,
        #         "INGEST_POLLED_COMPLETE",
        #         {}
        #     )
        ingest_state = "finished"

        if ingest_state == "finished":
            session.status = UploadStatus.COMPLETE

        elif ingest_state == "failed":
            session.status = UploadStatus.FAILED

        session.updated_at = datetime.utcnow()

        self.upload_service.storage.write_json(
            f"uploads/{session_id}/session.json",
            session.model_dump(),
            expected_generation=session._generation
        )

        self.upload_service.event_service.write_event(
            session_id,
            "POLLING_STATUS_UPDATE",
            {"state": ingest_state}
        )
