class BrightcoveMapper:

    # def build_cms_payload(self, session):

    #     meta = session.metadata or {}

    #     payload = {
    #         "name": meta.get("title") or "API Uploaded Video",
    #         "reference_id": session.id,
    #         "description": meta.get("description"),
    #         "tags": meta.get("tags", []),
    #         "custom_fields": {
    #             "language": meta.get("language"),
    #             "content_type": meta.get("content_type"),
    #             "campaign_id": meta.get("campaign_id"),
    #             "content_owner": meta.get("content_owner"),
    #             "is_sponsored": str(meta.get("is_sponsored", False)).lower(),
    #             "boostr_id": meta.get("boostr_id"),
    #             "specialty": meta.get("specialty"),
    #             "property": meta.get("property")
    #         }
    #     }

    #     # remove None values
    #     payload["custom_fields"] = {
    #         k: v for k, v in payload["custom_fields"].items() if v is not None
    #     }

    #     return payload
    def build_cms_payload(self, session):
        meta = session.metadata or {}

        return {
            "name": meta.get("title") or session.file_name,
            "reference_id": session.id,
            "description": meta.get("description") or ""
        }


# Metadata must be versioned, extensible, validated per content_type. SO when client adds new content type or new field, it should not break existing integrations. This also allows us to enforce different rules for different content types (eg. for live streams we may want to enforce presence of start time and end time fields, but for on demand videos these fields would be irrelevant). Versioning allows us to make non breaking changes to metadata schema in future (eg. adding new optional fields) without breaking existing clients.required_fields = ["title", "content_type", "language"] etc. SO EVERSIONING WILL BE ADDED LATER IF ASKING FOR NEW TICKETS RAISED IN THIS CASE.
