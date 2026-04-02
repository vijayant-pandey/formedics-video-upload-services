from fastapi import APIRouter
import requests
from video_upload_service.core.config import settings

router = APIRouter(prefix="/v1/debug", tags=["Debug"])


def get_access_token():
    url = "https://oauth.brightcove.com/v4/access_token"

    response = requests.post(
        url,
        auth=(settings.BRIGHTCOVE_CLIENT_ID, settings.BRIGHTCOVE_CLIENT_SECRET),
        data={"grant_type": "client_credentials"}
    )

    return response.json()["access_token"]


@router.get("/brightcove/{video_id}")
def check_brightcove_video(video_id: str):

    token = get_access_token()

    url = f"https://cms.api.brightcove.com/v1/accounts/{settings.BRIGHTCOVE_ACCOUNT_ID}/videos/{video_id}"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        return {
            "status": "error",
            "brightcove_response": res.text
        }

    data = res.json()

    sources = data.get("sources", [])
    poster = data.get("poster")
    thumbnail = data.get("thumbnail")
    duration = data.get("duration")
    state = data.get("state")

    playable = False
    if sources and duration:
        playable = True

    account_id = settings.BRIGHTCOVE_ACCOUNT_ID

    playback_url = None

    if playable:
        playback_url = f"https://players.brightcove.net/{account_id}/default_default/index.html?videoId={video_id}"

    return {
        "video_id": data.get("id"),
        "name": data.get("name"),
        "state": state,
        "duration": duration,
        "sources_count": len(sources),
        "playable": playable,
        "playback_url": playback_url,
        "poster": poster,
        "thumbnail": thumbnail,
        "sources": sources,
        "full_response": data
    }