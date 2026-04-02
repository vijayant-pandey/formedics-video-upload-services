import json
import os
from pathlib import Path
from typing import Any
import time
import random
from video_upload_service.core.logger import logger
from google.cloud import storage
from video_upload_service.core.config import settings

BASE_DIR = Path("local_metadata")

# mock upload added 24/02/2026
OBJECT_BASE_DIR = Path("local_objects")

class StorageService:

    def _ensure_dir(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)




    # =========DO NOT DELETE -- ACTIVE CODE FOR LOCAL FILESYSTEM STORAGE =========================
    # Active code when session.json files are stored in local filesystem (dev mode) -- 05/03/2026
    # def _write_json_internal(self, path: str, data: Any, expected_generation: int = None):

    #     full_path = BASE_DIR / path
    #     self._ensure_dir(full_path.parent)

    #     if expected_generation is not None and full_path.exists():
    #         existing = self.read_json(path)
    #         if existing.get("_generation") != expected_generation:
    #             raise Exception("Generation conflict")

    #     generation = 1
    #     if full_path.exists():
    #         existing = self.read_json(path)
    #         generation = existing.get("_generation", 0) + 1

    #     data["_generation"] = generation

    #     with open(full_path, "w", encoding="utf-8") as f:
    #         json.dump(data, f, default=str, indent=2)

    #     return generation
    # ============DO NOT DELETE , ACTIVE CODE  ========================================




    # As per instructions to store the sessoin.json files in GCS, the following code is active in prod mode -- 05/03/2026
    def _write_json_internal(self, path: str, data: Any, expected_generation: int = None):

    # DEV MODE → write locally (current behavior)
        if settings.ENV != "prod":

            full_path = BASE_DIR / path
            self._ensure_dir(full_path.parent)

            if expected_generation is not None and full_path.exists():
                existing = self.read_json(path)
                if existing.get("_generation") != expected_generation:
                    raise Exception("Generation conflict")

            generation = 1
            if full_path.exists():
                existing = self.read_json(path)
                generation = existing.get("_generation", 0) + 1

            data["_generation"] = generation

            with open(full_path, "w", encoding="utf-8") as f:
                json.dump(data, f, default=str, indent=2)

            return generation


        # PROD MODE → write to GCS
        client = storage.Client()
        bucket = client.bucket(settings.GCS_STAGING_BUCKET)

        object_path = path.replace("uploads/", "staging/")
        blob = bucket.blob(object_path)

        generation = 1
        try:
            if blob.exists():
                existing = json.loads(blob.download_as_text())
                generation = existing.get("_generation", 0) + 1
        except Exception:
            generation = 1

        data["_generation"] = generation

        blob.upload_from_string(
            json.dumps(data, default=str, indent=2),
            content_type="application/json"
        )

        return generation






    def write_json(self, path: str, data: Any, expected_generation: int = None):
        MAX_WRITE_RETRIES = 3

        for attempt in range(MAX_WRITE_RETRIES):

            try:
                return self._write_json_internal(
                    path,
                    data,
                    expected_generation=expected_generation
                )

            except Exception as e:

                if attempt == MAX_WRITE_RETRIES - 1:
                    logger.info(f"ALERT json_write_failed path={path}")
                    raise

                logger.info(
                    f"JSON_WRITE_RETRY attempt={attempt+1} path={path}"
                )
                # time.sleep(0.2)
                # retry jitter to preven race situation if multiple cloud run instances write the same session.json
                jitter = random.uniform(0.05, 0.15)
                time.sleep(jitter)




    # def read_json(self, path: str):
    #     full_path = BASE_DIR / path
    #     with open(full_path, "r", encoding="utf-8") as f:
    #         return json.load(f)
    

    def read_json(self, path: str):

        # DEV MODE → read locally
        if settings.ENV != "prod":
            full_path = BASE_DIR / path
            with open(full_path, "r", encoding="utf-8") as f:
                return json.load(f)

        # PROD MODE → read from GCS
        client = storage.Client()
        bucket = client.bucket(settings.GCS_STAGING_BUCKET)

        object_path = path.replace("uploads/", "staging/")
        blob = bucket.blob(object_path)

        if not blob.exists():
            raise Exception(f"Metadata not found in GCS: {object_path}")

        return json.loads(blob.download_as_text())

    def object_exists(self, object_path: str):
        # local dev mode 25/02/2026
        full_path = OBJECT_BASE_DIR / object_path
        if full_path.exists():
            return True

        # reak GCS checking 25/02/2026
        try:
            client = storage.Client()
            bucket = client.bucket(settings.GCS_STAGING_BUCKET)
            blob = bucket.blob(object_path)
            return blob.exists()
        except Exception:
            return False
        

    def get_object_metadata(self, object_path: str):
        #  local dev mode -- 25/02/2026
        full_path = OBJECT_BASE_DIR / object_path

        if full_path.exists():
            size = full_path.stat().st_size
            return {
                "size": size,
                "crc32c": None
            }

        # real GCS mode -- 25/02/2026
        try:
            client = storage.Client()
            bucket = client.bucket(settings.GCS_STAGING_BUCKET)
            blob = bucket.blob(object_path)

            if not blob.exists():
                return None

            blob.reload()

            return {
                "size": blob.size,
                "crc32c": blob.crc32c
            }

        except Exception:
            return None

    
    # fake gcp upload --> 24/02/2026
    def write_binary(self, object_path: str, content: bytes):
        full_path = OBJECT_BASE_DIR / object_path
        self._ensure_dir(full_path.parent)

        with open(full_path, "wb") as f:
            f.write(content)

        logger.info(f"DEV_BINARY_WRITTEN path={object_path}")


    # Upload to GCP using Python cloud libraries 
    def upload_to_gcs(self, bucket_name: str, object_path: str, file_bytes: bytes, content_type: str):

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_path)

        blob.upload_from_string(
            file_bytes,
            content_type=content_type
        )

        logger.info(f"GCS_UPLOAD_SUCCESS bucket={bucket_name} path={object_path}")