import os
from google.cloud import secretmanager
from video_upload_service.core.config import settings

# Local .env usage
# For Prod test in locally --> follow this approach
def get_secret(secret_name: str, fallback: str | None = None):

    # dev mode → use local env
    if settings.ENV == "dev":
        return os.getenv(secret_name, fallback)

    # prod mode
    try:
        client = secretmanager.SecretManagerServiceClient()

        project_id = os.getenv("GCP_PROJECT")
        name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"

        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")

    except Exception:
        # Fallback to environment variable if Secret Manager fails
        value = os.getenv(secret_name, fallback)
        if value:
            return value

        raise Exception(
            f"Secret '{secret_name}' not found in Secret Manager "
            f"and not present in environment variables."
        )