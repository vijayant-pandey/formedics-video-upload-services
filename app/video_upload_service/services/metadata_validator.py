from fastapi import HTTPException
from video_upload_service.services.metadata_rules.registry import MetadataRegistry

class MetadataValidator:

    def __init__(self):
        self.registry = MetadataRegistry()

    def validate(self, metadata: dict):

        # version auto inject
        if "version" not in metadata:
            metadata["version"] = "v1"

        # metadata version audit log
        from video_upload_service.core.logger import logger

        logger.info(
            f"METADATA_VERSION_USED content_type={metadata.get('content_type')} version={metadata.get('version')}"
        )

        content_type = metadata.get("content_type")
        version = metadata.get("version")

        if not content_type:
            raise HTTPException(status_code=400, detail="content_type missing")

        try:
            rule = self.registry.get_rule(content_type, version)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # delegate validation
        rule.validate(metadata)

        return True
