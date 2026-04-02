from pydantic import ValidationError
from .dtypes import *
from google.cloud import bigquery


INT_FIELDS = { 'line_item_id', 'boostr_deal_id', 'file_id' }

def _bigquery_row_to_dict(schema_fields: list[SchemaField], row: BigQueryRow) -> dict: # not needed anymore
    """
    Convert a BigQuery REST API row into a named dict.

    BigQuery returns rows like:
      {"f": [{"v": "123"}, {"v": "some-uuid"}, ...]}
    and field names live in a separate schema object:
      {"fields": [{"name": "line_item_id", "type": "INTEGER"}, ...]}
    """
    result = {}
    for field_meta, cell in zip(schema_fields, row.f):
        name = field_meta.name
        value = cell['v']

        if name in INT_FIELDS and value is not None:
            value = int(value)

        result[name] = value

    return result


def _validation_errors_to_list(exc: ValidationError) -> list[dict]:
    """
    Convert a Pydantic ValidationError into a simple list of dicts
    that's easy to store in Firestore and display in a frontend.
    """
    errors = []
    for err in exc.errors():
        errors.append({
            'field': '.'.join(str(part) for part in err['loc']),
            'message': err['msg'],
        })

    return errors


def _poll_metadata_table(dt_lookup:str) -> List[CampaignMetadata]:
    bq_client = bigquery.Client()
    query = 'SELECT * FROM `pw-datahubdev.vw_physweekly_data.vw_gam_creatives_metadata`'
    config = None

    if dt_lookup:
        query = f"{query} WHERE dw_ingested_at > DATETIME(CAST(@dt_lookup AS TIMESTAMP))"

        config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter('dt_lookup', 'STRING', str(dt_lookup))
                ]
            )

    job = bq_client.query_and_wait(query, job_config=config)
    rows = [dict(row) for row in job]

    return rows
