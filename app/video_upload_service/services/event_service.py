import uuid
from datetime import datetime
from video_upload_service.models.event import UploadEvent
from video_upload_service.services.storage_service import StorageService


class EventService:

    def __init__(self):
        self.storage = StorageService()

    def write_event(self, session_id: str, event_type: str, payload: dict):

        event_id = str(uuid.uuid4())

        event = UploadEvent(
            id=event_id,
            session_id=session_id,
            timestamp=datetime.utcnow(),
            event_type=event_type,
            payload=payload
        )

        path = f"uploads/{session_id}/events/{event_id}.json"
        self.storage.write_json(path, event.model_dump())

        return event
