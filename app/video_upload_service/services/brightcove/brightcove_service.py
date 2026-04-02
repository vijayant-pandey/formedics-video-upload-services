from video_upload_service.services.brightcove.oauth_client import BrightcoveOAuthClient
from video_upload_service.services.brightcove.cms_client import BrightcoveCMSClient
from video_upload_service.services.brightcove.ingest_client import BrightcoveIngestClient
from video_upload_service.services.brightcove_mapper import BrightcoveMapper
from video_upload_service.services.signed_url_service import SignedURLService
import time
from video_upload_service.core.logger import logger
from video_upload_service.core.config import settings


class BrightcoveService:

    def __init__(self):
        self.mapper = BrightcoveMapper()
        self.signer = SignedURLService()
        self.oauth = BrightcoveOAuthClient()
        self.cms = BrightcoveCMSClient()
        self.ingest = BrightcoveIngestClient()

    # retry wrapper brighcove 5xx exponential backoff retry
    def _retry_call(self, func, *args, **kwargs):
        MAX_RETRIES = 3
        BASE_DELAY = 1 #seconds

        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            
            except Exception as e:
                if attempt == MAX_RETRIES -1:
                    logger.info(f"BRIGHTCOVE_RETRY_FAILED error={str(e)}")
                    raise

                delay = BASE_DELAY * (2 ** attempt)
                logger.info(f"BRIGHTCOVE_RETRY attempt={attempt + 1} delay={delay}s error={str(e)}")

                time.sleep(delay)


    def build_ingest_payload(self, session):

        if settings.ENV == "dev":
            return {
                "master": {
                    "url": "https://samplelib.com/lib/preview/mp4/sample-5s.mp4"
                },
                "profile": "multi-platform-standard-static"
            }

        read = self.signer.generate_read_url(
            session.gcs_bucket,
            session.gcs_object_path
        )

        return {
            "master": {
                "url": read["read_url"]
            },
            "profile": "multi-platform-standard-static"
        }

    def ingest_video(self, session):

        # printing account id for debugging - can be removed in production
        # print("ACCOUNT_ID_FROM_SETTINGS:", settings.BRIGHTCOVE_ACCOUNT_ID)
        token = self.oauth.get_access_token()

        # Build CMS payload using mapper
        cms_payload = self.mapper.build_cms_payload(session)

        if getattr(session, "brightcove", None) and session.brightcove.video_id:
            video_id = session.brightcove.video_id
        
        else:
            video = self._retry_call(
                self.cms.create_video,
                cms_payload,
                access_token=token
            )
            video_id = video["video_id"]

        ingest_payload = self.build_ingest_payload(session)

        ingest = self._retry_call(
            self.ingest.submit_ingest,
            video_id,
            ingest_payload,
            token
        )

        return {
            "video_id": video_id,
            "job_id": ingest["job_id"]
        }
