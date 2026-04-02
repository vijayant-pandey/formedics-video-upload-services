from video_upload_service.services.metadata_rules.video_v1 import VideoMetadataV1

class MetadataRegistry:

    def __init__(self):

        self.rules = {
            ("video", "v1"): VideoMetadataV1(),
        }

    def get_rule(self, content_type: str, version: str):

        key = (content_type, version)

        if key not in self.rules:
            raise ValueError(f"No metadata rule registered for {key}")

        return self.rules[key]
