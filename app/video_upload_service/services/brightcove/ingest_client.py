from uuid import UUID, uuid4
from video_upload_service.core.secrets import get_secret

class BrightcoveIngestClient:

    def __init__(self):
        self.account_id = get_secret("BRIGHTCOVE_ACCOUNT_ID")

    def submit_ingest(self, video_id: str, payload: dict, access_token: str):
        import requests

        url = f"https://ingest.api.brightcove.com/v1/accounts/{self.account_id}/videos/{video_id}/ingest-requests"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        return {
            "job_id": data.get("id")
        }