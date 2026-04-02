import json
from google.cloud import tasks_v2
from video_upload_service.core.config import settings


class CloudTasksService:

    def __init__(self):

        from video_upload_service.core.config import settings
        self.dev_mode = settings.ENV == "dev"

        # dev mode — do NOT initialize GCP client
        if self.dev_mode:
            self.client = None
            self.parent = None
            return
        
        # retry mode for cloud exponential backof
        self.retry_config = {
            "max_attempts": 5,
            "min_backoff": "5s",
            "nmax_backoff": "300s"
        }

        # prod mode — real Cloud Tasks client
        self.client = tasks_v2.CloudTasksClient()

        self.parent = self.client.queue_path(
            settings.GCP_PROJECT_ID,
            settings.GCP_LOCATION,
            settings.GCP_QUEUE_NAME,
        )

    def enqueue_ingest_job(self, session_id: str):

        # dev mode (local testing)
        if self.dev_mode:

            from video_upload_service.core.logger import logger
            logger.info(f"CLOUD_TASK_DEV_EXECUTE session_id={session_id}")
            
            # print statement for debugging - can be removed in production
            # print(f"CLOUD_TASK_DEV_EXECUTE session_id={session_id}")

            # simulate push execution
            from video_upload_service.workers.ingest_worker import IngestWorker

            worker = IngestWorker()
            worker.process(session_id)

            return

        # prod mode (real cloud tasks)
        url = f"{settings.CLOUD_RUN_WORKER_URL}/{session_id}"

        payload = json.dumps({
            "session_id": session_id
        }).encode()

        # Zero Trust Cloud Run Push AUth with OIDC Authentication to Cloud Run Worker
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": settings.CLOUD_RUN_WORKER_URL,
                "headers": {
                    "Content-Type": "application/json"
                },
                "oidc_token": {
                    "service_account_email": settings.CLOUD_RUN_WORKER_SERVICE_ACCOUNT,
                    "audience": settings.CLOUD_RUN_WORKER_AUDIENCE,
                },
                "body": payload,
            }
        }

        # Added to check direct upload by using google python client library to upload to GCS, bypassing the need for signed URLs and allowing for larger file uploads without hitting URL size limits. This is only allowed in PROD mode and requires admin role.
        try:
            response = self.client.create_task(
                request={"parent": self.parent, "task": task}
            )

            # print(f"CLOUD_TASK_CREATED {response.name}")

            from video_upload_service.core.logger import logger
            logger.info(
                f"CLOUD_TASK_CREATED name={response.name} retry_policy={self.retry_config}"
            )

        except Exception as e:
            # Local PROD fallback — execute worker directly
            from video_upload_service.core.logger import logger
            logger.info(f"CLOUD_TASK_FALLBACK_LOCAL_EXECUTION reason={str(e)}")

            from video_upload_service.workers.ingest_worker import IngestWorker
            worker = IngestWorker()
            worker.process(session_id)

