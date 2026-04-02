from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from .dtypes import *
from datetime import timedelta
from google.cloud import secretmanager, storage
from google.oauth2 import service_account
from json import loads
import time
from common.logging.logging_config import get_logger


logger = get_logger('internal.ga_validation.services')

class GCSDownloadService:
    """Service for handling GA Validation operations"""

    def get_secret_value(self):
        client = secretmanager.SecretManagerServiceClient()
        name = f'projects/266841731232/secrets/profile-metadata-service-bq-json/versions/latest'
        response = client.access_secret_version(name=name)
        return response.payload.data.decode('UTF-8')

    def generate_download_signed_url(self,
                                    bucket_name: str,
                                    blob_name: str,
                                    expiration_minutes: int=15):
        """Generates a v4 signed URL for downloading a blob."""
        sa_json = self.get_secret_value()
        creds = service_account.Credentials.from_service_account_info(loads(sa_json))
        storage_client = storage.Client(credentials=creds, project='266841731232')

        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        url = blob.generate_signed_url(
            version='v4',
            expiration=timedelta(minutes=expiration_minutes),
            method='GET',
            # Optional: Force a download prompt with a specific filename
            # response_disposition=f"attachment; filename={blob_name}",
        )
        print(url)
        return url

    def download_file(self, bucket_name: str, filename: str):
        logger.info('Generating download signed URL',
                   bucket=bucket_name,
                   filename=filename)

        try:
            start_time = time.time()
            signed_url = self.generate_download_signed_url(bucket_name=bucket_name,
                                                           blob_name=f'{filename}-latest.zip',
                                                           expiration_minutes=15)
            duration_ms = (time.time() - start_time) * 1000

            logger.info('Signed URL generated successfully',
                       bucket=bucket_name,
                       filename=filename,
                       duration_ms=round(duration_ms, 2))

            return RedirectResponse(url=signed_url, status_code=303)
        except Exception as e:
            logger.error('Failed to generate signed URL',
                        bucket=bucket_name,
                        filename=filename,
                        error_type=type(e).__name__)
            raise HTTPException(status_code=500, detail='Could not generate download link')
