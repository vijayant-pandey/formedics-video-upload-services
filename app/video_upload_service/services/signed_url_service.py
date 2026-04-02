from datetime import datetime, timedelta
from video_upload_service.core.config import settings
from google.cloud import storage
from video_upload_service.core.logger import logger

# For local-fake uploads testing-- 
class SignedURLService:

    def generate_upload_url(self, bucket: str, object_path: str, content_type: str = "video/mp4"):

        # local dev mode (no service account key)

        if settings.ENV == "dev":
            return {
                "upload_url": f"https://fake-upload-url.local/{bucket}/{object_path}",
                "expires_at": "1h"
            }
        
        if settings.ENV == "prod":
            try:
                client = storage.Client()
                bucket_obj = client.bucket(bucket)
                blob = bucket_obj.blob(object_path)

                # Try generating signed URL (will work in Cloud Run)
                signed_url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(minutes=15),
                    method="PUT",
                    content_type=content_type,
                )

                logger.info(
                    f"SIGNED_UPLOAD_URL_GENERATED bucket={bucket} path={object_path} url={signed_url}"
                )

                return {
                    "upload_url": signed_url,
                    "expires_at": "15m"
                }

            # except Exception:
            #     # Fallback for local PROD testing
            #     return {
            #         "upload_url": None,
            #         "expires_at": None,
            #         "local_direct_upload": True
            #     }            
            except Exception as e:

                logger.info(
                    f"SIGNED_URL_FALLBACK_LOCAL bucket={bucket} path={object_path} reason={str(e)}"
                )

                return {
                    # "upload_url": None,
                    "upload_url": f"gs://{bucket}/{object_path}",
                    "expires_at": None,
                    "local_direct_upload": True
                }

    def generate_read_url(self, bucket: str, object_path: str):

    # dev mode- no signing (client policy)
        if settings.ENV == "dev":
            return {
                "read_url": f"https://fake-read-url.local/{bucket}/{object_path}",
                "expires_at": "1h"
            }

        # cloud run real signing
        try:

            client = storage.Client()
            bucket_obj = client.bucket(bucket)
            blob = bucket_obj.blob(object_path)

            read_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(hours=1),
                method="GET"
            )

            logger.info(
                f"SIGNED_READ_URL_GENERATED bucket={bucket} path={object_path} url={read_url}"
            )

            return {
                "read_url": read_url,
                "expires_at": "1h"
            }
        
        except Exception:
            # Fallback for local PROD testing withot Keys
            return {
                # "read_url": f"gs://{bucket}/{object_path}",
                "read_url": f"https://storage.googleapis.com/{bucket}/{object_path}",
                "expires_at": None,
            }
