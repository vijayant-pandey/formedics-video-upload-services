from typing import Any, Dict, List
from pydantic import BaseModel, Field


### MashupMD Specific Types
class MashupImportPayload(BaseModel):
    dataSource: str
    database: str
    collection: str
    pipeline: List[Dict]

class InsertArticleRequest(BaseModel):
    collection: str
    document: dict

class UpdateArticleRequest(BaseModel):
    collection: str = Field(...,
                            description="MongoDB collection name")
    filter: Dict[str, Any] = Field(...,
                                   description="",
                                   json_schema_extra={"_id": {"$oid": "6702dc27e5a47fdad89083cd"}})
    update: Dict[str, Any] = Field(...,
                                   description="",
                                   json_schema_extra={"$set": {"title": "Updated title"}})
