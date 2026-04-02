from datetime import datetime
from video_upload_service.services.upload_service import UploadService
from video_upload_service.services.brightcove.brightcove_service import BrightcoveService
from video_upload_service.models.upload_session import UploadSession, UploadStatus
from video_upload_service.workers.polling_worker import PollingWorker
from video_upload_service.core.metrics import metric_ingest_started
from video_upload_service.core.metrics import metric_ingest_started, ingest_timer_start


class IngestWorker:

    def __init__(self):
        self.upload_service = UploadService()
        self.brightcove = BrightcoveService()

    def process(self, session_id: str):
        path = f"uploads/{session_id}/session.json"

        # session = self.upload_service.get_session(session_id)

        #  raw jason reas (gen control) --------
        data = self.upload_service.storage.read_json(path)

        generation = data.get("_generation")

        from video_upload_service.models.upload_session import UploadSession
        session = UploadSession(**data)

        # Idempotency safeguard
        if session.status in [UploadStatus.INGESTING, UploadStatus.COMPLETE]:
            return

        # brightcove pipeline 

        # old code as working in 26/02/2026
        # result = self.brightcove.ingest_video(session)
        # from video_upload_service.core.logger import logger
        # logger.info(
        #     f"INGEST_PIPELINE_STARTED session_id={session_id} video_id={result['video_id']} job_id={result['job_id']}"
        # )


        # new code also working as to bypass the oauth fix in 26/02/2026
        # try:
        #     result = self.brightcove.ingest_video(session)
        # except Exception as e:
        #     from video_upload_service.core.logger import logger

        #     logger.info(
        #         f"BRIGHTCOVE_INGEST_SKIPPED session_id={session_id} error={str(e)}"
        #     )

        #     # Mark session as INGESTING so pipeline continues
        #     session.status = UploadStatus.INGESTING
        #     session.updated_at = datetime.utcnow()

        #     self.upload_service.storage.write_json(
        #         path,
        #         session.model_dump(),
        #         expected_generation=session._generation
        #     )

        #     return
        result = self.brightcove.ingest_video(session)
        

        metric_ingest_started(session_id)
        ingest_timer_start(session_id)

        # update session
        session.status = UploadStatus.INGESTING
        metric_ingest_started(session_id)

        session.updated_at = datetime.utcnow()

        # if not session.brightcove:
        #     session.brightcove = {}
        from video_upload_service.core.config import settings
        session.brightcove.account_id = settings.BRIGHTCOVE_ACCOUNT_ID
        session.brightcove.video_id = result["video_id"]
        session.brightcove.job_id = result["job_id"]

        # concurrency safe write
        self.upload_service.storage.write_json(
            path,
            session.model_dump(),
            expected_generation=session._generation
        )

        # write event
        self.upload_service.event_service.write_event(
            session_id,
            "INGEST_STARTED",
            result
        )

        return

        # POLLING -if bihtcove callback endpoint is not created
        # poller = PollingWorker()
        # poller.poll_status(session_id)

        

    def map_ingest_state(self, state: str):

        mapping = {
            "processing": UploadStatus.INGESTING,
            "publishing": UploadStatus.INGESTING,
            "finished": UploadStatus.COMPLETE,
            "success": UploadStatus.COMPLETE,
            "complete": UploadStatus.COMPLETE,
            "completed": UploadStatus.COMPLETE,
            "failed": UploadStatus.FAILED,
            "error": UploadStatus.FAILED
        }

        return mapping.get(state.lower(), UploadStatus.FAILED)