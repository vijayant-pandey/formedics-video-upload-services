from google.cloud import firestore
from typing import List, Literal
from .dtypes import CampaignMetadata


db = firestore.Client(database='unified-marketing-platform')
COLLECTION = 'campaign_validations_test'

def _doc_id(line_item_id, creative_id) -> str:
    """Document ID from line_item_id + creative_id."""
    return f"{line_item_id}_{creative_id}"


def write_validation_batch(documents: list[dict]) -> None:
    """
    Upsert validation documents to Firestore.

    Uses a doc ID (line_item_id + creative_id) so re-validating
    the same row overwrites the previous result instead of creating duplicates.
    """
    batch = db.batch()
    for doc_data in documents:
        doc_id = _doc_id(doc_data['line_item_id'], doc_data['creative_id'])
        doc_ref = db.collection(COLLECTION).document(doc_id)
        batch.set(doc_ref, doc_data)
    batch.commit()


def single_upsert(doc_id: str, details: dict) -> None:
    """
    Upsert documents to Firestore.

    Uses a doc ID (line_item_id + creative_id) so re-validating
    the same row overwrites the previous result instead of creating duplicates.
    """
    doc_ref = db.collection(COLLECTION).document(doc_id)
    doc_ref.set(details, merge=True)


def get_validations(limit: int=50) -> list[dict]:
    """
    Query recent validations, optionally filtered by status ('valid' | 'invalid').
    Results are ordered by validated_at descending.
    """
    query = db.collection(COLLECTION).select(['id', 'line_item_id', 'creative_id']).order_by(
        'validated_at', direction=firestore.Query.DESCENDING
    ).limit(limit)

    return [{'id': doc.id, **doc.to_dict()} for doc in query.stream()]


def get_validations_by_line_item(line_item_id: int) -> List[CampaignMetadata]:
    """Return all validation records for a given line item."""
    query = (
        db.collection(COLLECTION)
        .where(filter=firestore.FieldFilter('line_item_id', '==', line_item_id))
        .order_by('validated_at', direction=firestore.Query.DESCENDING)
    )
    return [{'id': doc.id, **doc.to_dict()} for doc in query.stream()]


def get_most_recent_date() -> str:
    """Return the last dw_ingested_at value."""
    results = (
        db.collection(COLLECTION)
        .select(['dw_ingested_at'])
        .order_by('dw_ingested_at', direction=firestore.Query.DESCENDING)
        .limit(1)
    )

    return [{'id': doc.id, **doc.to_dict()} for doc in results.stream()]


def get_missing_target_validations(target: Literal['blueconic', 'iterable'] = 'blueconic'):
    """Return the documents where the target is invalid or missing."""
    # invalid_docs = db.collection(COLLECTION).select(['line_item_id', 'creative_id']).where(
    #     filter=firestore.FieldFilter('status', '==', 'valid')).stream()
    invalid_docs = db.collection(COLLECTION).select(['line_item_id', 'creative_id']).stream()
    invalid_docs_results = []

    for doc in invalid_docs:
        data = { 'id': doc.id, **doc.to_dict() }

        if target not in data:
            invalid_docs_results.append(data)
        elif data[target].get('status') == 'invalid':
            invalid_docs_results.append(data)

    return invalid_docs_results
