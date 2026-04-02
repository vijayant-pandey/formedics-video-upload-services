from video_upload_service.core.secrets import get_secret
from video_upload_service.core.config import settings

class BrightcoveOAuthClient:

    def __init__(self):
        # secrets loaded here , not at the top of the file
        self.client_id = get_secret("BRIGHTCOVE_CLIENT_ID")
        self.client_secret = get_secret("BRIGHTCOVE_CLIENT_SECRET")

    def get_access_token(self):
        import base64
        import requests

        url = "https://oauth.brightcove.com/v4/access_token"

        # Build Basic Auth header
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {
            "grant_type": "client_credentials"
        }
        # debugging output - can be removed in production
        # print("ACCOUNT_ID:", settings.BRIGHTCOVE_ACCOUNT_ID)

        response = requests.post(url, headers=headers, data=data)

        try:

            from video_upload_service.core.logger import logger
            logger.info(f"BRIGHTCOVE_OAUTH_STATUS: {response.status_code}")

            # debugging output - can be removed in production
            # print("BRIGHTCOVE_OAUTH_STATUS:", response.status_code)
            # print("BRIGHTCOVE_OAUTH_RESPONSE:", response.text)
            response.raise_for_status()
        except Exception as e:

            # logging the error for debugging - can be removed in production
            from video_upload_service.core.logger import logger
            logger.error(f"BRIGHTCOVE_OAUTH_ERROR: {str(e)}")
            # print("BRIGHTCOVE_OAUTH_ERROR:", str(e))
            raise

        token = response.json().get("access_token")

        if not token:
            raise Exception("Brightcove OAuth failed: no access token returned")

        return token