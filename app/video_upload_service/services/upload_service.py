import uuid
from datetime import datetime, timedelta
from fastapi import HTTPException
from video_upload_service.models.upload_session import UploadSession, UploadStatus
from video_upload_service.models.upload_request import CreateUploadRequest
from video_upload_service.services.storage_service import StorageService
from video_upload_service.services.event_service import EventService
from video_upload_service.services.metadata_validator import MetadataValidator
from video_upload_service.core.config import settings
from video_upload_service.services.signed_url_service import SignedURLService
from video_upload_service.core.logger import logger
from video_upload_service.core.metrics import metric_upload_created, metric_upload_failure
from video_upload_service.services.cloud_tasks_service import CloudTasksService

class UploadService:

    def __init__(self):
        self.storage = StorageService()
        self.event_service = EventService()
        # self.validator = MetadataValidator()
        self.signed_url_service = SignedURLService()
        self.cloud_tasks = CloudTasksService()

    def create_upload_session(self, request: CreateUploadRequest):

        # self.validator.validate(request.metadata)
        # try:
        #     self.validator.validate(request.metadata)
        # except ValueError as e:
        #     from fastapi import HTTPException
        #     raise HTTPException(status_code=400, detail=str(e))
        
        # governance - file name enforcement
        if "/" in request.file_name or "\\" in request.file_name:
            raise HTTPException(status_code=400, detail="Invalid file name")

        session_id = str(uuid.uuid4())
        now = datetime.utcnow()

        session = UploadSession(
            id=session_id,
            created_at=now,
            updated_at=now,
            created_by_user_id=request.created_by_user_id,
            source_surface=request.source_surface,
            status=UploadStatus.CREATED,
            gcs_bucket=settings.GCS_STAGING_BUCKET,
            gcs_object_path=f"staging/{session_id}/{request.file_name}",
            file_name=request.file_name,
            file_size_bytes=request.file_size_bytes,
            content_type=request.content_type,
            metadata=request.metadata,
            expires_at=now + timedelta(hours=48)
        )
        
        path = f"uploads/{session_id}/session.json"
        self.storage.write_json(path, session.model_dump())

        logger.info(f"SESSION_CREATED session_id={session_id}")
        from video_upload_service.core.metrics import metric_upload_created
        metric_upload_created(session_id)


        self.event_service.write_event(
            session_id,
            "SESSION_CREATED",
            {"file_name": request.file_name}
        )

        # return session
        signed = self.signed_url_service.generate_upload_url(
            session.gcs_bucket,
            session.gcs_object_path
        )

        return {
            "session": session,
            "upload_url": signed["upload_url"],
            "expires_at": signed["expires_at"]
        }


    def complete_upload(self, session_id: str):

        path = f"uploads/{session_id}/session.json"
        data = self.storage.read_json(path)

        session = UploadSession(**data)
        generation = data.get("_generation")


        # If not commented --> can do the real success testing via uploading the file in gCS bucket manually 

        # If commented then success testing is only possible if IAM storage access is granted else oly fialure test is possible.
        #  
        # DEV MODE SHORT-CIRCUIT (NO REAL GCS UPLOAD)
        # if settings.ENV == "dev":
        #     now = datetime.utcnow()
        #     session.status = UploadStatus.UPLOADED
        #     session.updated_at = now

        #     self.storage.write_json(
        #         path,
        #         session.model_dump(),
        #         expected_generation=session._generation
        #     )

        #     logger.info(f"DEV_MODE_UPLOAD_COMPLETED session_id={session_id}")

        #     return session

        # Idempotency safeguard
        if session.status in [
            UploadStatus.UPLOADED,
            UploadStatus.INGESTING,
            UploadStatus.COMPLETE
        ]:
            return session

        # Verify object exists (placeholder)
        # if not self.storage.object_exists(session.gcs_object_path):
        #     raise ValueError("Uploaded object not found")
        
        # verify that object exists
        # if not self.storage.object_exists(session.gcs_object_path):

        #     now = datetime.utcnow()

        #     session.status = UploadStatus.FAILED
        #     session.error = {
        #         "code": "OBJECT_NOT_FOUND",
        #         "message": "Uploaded object not found"
        #     }
        #     session.updated_at = now

        #     self.storage.write_json(
        #         path,
        #         session.model_dump(),
        #         expected_generation=session._generation
        #     )

        #     metric_upload_failure(session_id, "OBJECT_NOT_FOUND")

        #     raise HTTPException(status_code=400, detail="Uploaded object not found")

        # dev mode – Skip GCS existence check
        if settings.ENV != "dev":
            if not self.storage.object_exists(session.gcs_object_path):

                now = datetime.utcnow()

                session.status = UploadStatus.FAILED
                session.error = {
                    "code": "OBJECT_NOT_FOUND",
                    "message": "Uploaded object not found"
                }
                session.updated_at = now

                self.storage.write_json(
                    path,
                    session.model_dump(),
                    expected_generation=session._generation
                )

                metric_upload_failure(session_id, "OBJECT_NOT_FOUND")

                raise HTTPException(status_code=400, detail="Uploaded object not found")
            

        # governance - expiry enforcement
        now = datetime.utcnow()

        if session.expires_at and now > session.expires_at:
            session.status = UploadStatus.EXPIRED
            session.updated_at = now

            self.storage.write_json(
                path,
                session.model_dump(),
                expected_generation=session._generation
            )

            raise HTTPException(status_code=400, detail="Upload session expired")
        

        # governance file size validation

        # dev mode – skip all GCS validations
        if settings.ENV != "dev":

            # file size validation
            object_meta = self.storage.get_object_metadata(
                session.gcs_object_path
            )

            real_size = object_meta.get("size")

            if real_size and real_size != session.file_size_bytes:

                session.status = UploadStatus.FAILED
                session.error = {
                    "code": "SIZE_MISMATCH",
                    "message": "Uploaded file size mismatch"
                }
                session.updated_at = now

                self.storage.write_json(
                    path,
                    session.model_dump(),
                    expected_generation=session._generation
                )

                raise HTTPException(status_code=400, detail="Uploaded file size mismatch")

            # checksum validation
            if session.checksum:
                object_checksum = object_meta.get("crc32c")

                if object_checksum and object_checksum != session.checksum:

                    session.status = UploadStatus.FAILED
                    session.error = {
                        "code": "CHECKSUM_MISMATCH",
                        "message": "Checksum validation failed"
                    }
                    session.updated_at = now

                    self.storage.write_json(
                        path,
                        session.model_dump(),
                        expected_generation=session._generation
                    )

                    raise HTTPException(status_code=400, detail="Checksum validation failed")
   
        session.status = UploadStatus.UPLOADED
        session.updated_at = datetime.utcnow()

        logger.info(f"UPLOAD_COMPLETED session_id={session_id}")

        from video_upload_service.core.metrics import metric_upload_completed
        metric_upload_completed(session_id)

        self.storage.write_json(path, session.model_dump(), expected_generation=session._generation)

        self.event_service.write_event(
            session_id,
            "UPLOAD_COMPLETED",
            {"object_path": session.gcs_object_path}
        )

        # Lazy import to avoid circular dependency
        # from video_upload_service.workers.ingest_worker import IngestWorker
        # worker = IngestWorker()
        # worker.process(session_id)

        self.cloud_tasks.enqueue_ingest_job(session_id)

        return session
    

    def get_session(self, session_id: str):

        path = f"uploads/{session_id}/session.json"
        data = self.storage.read_json(path)

        return UploadSession(**data)
    

    def refresh_upload_url(self, session_id: str):

        path = f"uploads/{session_id}/session.json"
        data = self.storage.read_json(path)

        session = UploadSession(**data)

        #  state files (doc governance)
        if session.status not in [
            UploadStatus.CREATED,
            UploadStatus.UPLOADED
        ]:
            raise HTTPException(
                status_code=400,
                detail="Upload URL cannot be refreshed in current state"
            )

        # expiry check
        now = datetime.utcnow()

        if session.expires_at and now > session.expires_at:
            session.status = UploadStatus.EXPIRED
            session.updated_at = now

            self.storage.write_json(
                path,
                session.model_dump(),
                expected_generation=session._generation
            )

            metric_upload_failure(session_id, "EXPIRED")

            raise HTTPException(status_code=400, detail="Upload session expired")

        # generate new signed url
        signed = self.signed_url_service.generate_upload_url(
            session.gcs_bucket,
            session.gcs_object_path
        )

        logger.info(f"UPLOAD_URL_REFRESHED session_id={session_id}")

        return {
            "session": session,
            "upload_url": signed["upload_url"],
            "expires_at": signed["expires_at"]
        }

    
    def retry_upload(self, session_id: str):

        path = f"uploads/{session_id}/session.json"
        data = self.storage.read_json(path)

        session = UploadSession(**data)

        #  state rules (from architecture doc)
        if session.status in [UploadStatus.COMPLETE, UploadStatus.INGESTING]:
            return session

        # failed or uploaded allowed
        if session.status not in [UploadStatus.FAILED, UploadStatus.UPLOADED]:
            return session

        # reset error and move session back to ingesting to trigger re-processing
        session.error = None
        session.status = UploadStatus.INGESTING
        # session.retry_count = (session.retry_count or 0) + 1
        session.retry_count = 0
        session.updated_at = datetime.utcnow()

        # concurrency safe write
        self.storage.write_json(
            path,
            session.model_dump(),
            expected_generation=session._generation
        )

        # trigger the ingest worker
        from video_upload_service.workers.ingest_worker import IngestWorker
        worker = IngestWorker()
        worker.process(session_id)

        # audit event
        self.event_service.write_event(
            session_id,
            "RETRY_TRIGGERED",
            # {"status_before_retry": str(session.status)}
            {"new_status": str(session.status)}
        )

        # return session
        return self.get_session(session_id)