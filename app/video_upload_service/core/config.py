from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV: str = "dev"
    # Later Cloud Run will set: ENV=prod
    BRIGHTCOVE_ACCOUNT_ID: str | None = None
    BRIGHTCOVE_CLIENT_ID: str | None = None
    BRIGHTCOVE_CLIENT_SECRET: str | None = None

    BRIGHTCOVE_INGEST_PROFILE: str = "placeholder"
    BRIGHTCOVE_CALLBACK_SECRET: str = "dev_shared_secret"

    # GCS (placeholders)
    GCS_STAGING_BUCKET: str = "fm_video_uploads"
    GCS_METADATA_BUCKET: str = "placeholder"

    # Security
    CALLBACK_SHARED_SECRET: str = "placeholder"

    # Cloud Tasks
    GCP_PROJECT_ID: str | None = None
    GCP_LOCATION: str = "us-central1"
    GCP_QUEUE_NAME: str = "video-ingest-queue"
    CLOUD_RUN_WORKER_URL: str = "http://localhost:8000/v1/worker/ingest"

    # OIDC Worker Auth
    CLOUD_RUN_WORKER_SERVICE_ACCOUNT: str | None = None
    CLOUD_RUN_WORKER_AUDIENCE: str | None = None

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
