from fastapi import HTTPException

REQUIRED_FIELDS = [
    "title",
    "content_type",
    "language"
]

OPTIONAL_FIELDS = [
    "description",
    "tags",
    "specialty",
    "property",
    "campaign_id",
    "content_owner",
    "date",
    "is_sponsored",
    "boostr_id",
    "hcp_names",
    "compliance_flags",
    "embargo_date",
    "ad_enabled"
]

class VideoMetadataV1:

    def validate(self, metadata: dict):

        # required fields validation
        for field in REQUIRED_FIELDS:
            if field not in metadata:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required metadata field: {field}"
                )

        # allowed fields validation
        allowed = set(REQUIRED_FIELDS + OPTIONAL_FIELDS + ["version"])

        for key in metadata.keys():
            if key not in allowed:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported metadata field: {key}"
                )