from google.cloud import bigquery


client = bigquery.Client()

def get_utm_params(line_item_id: int):
    sql = f"""
        SELECT
            utm_campaign,
            utm_medium,
            utm_source,
            utm_content,
            utm_lineitemid,
            product_id,
            audience_product_name,
            site,
            indication

        FROM
            `pw-datahub.iterable_smart_ingest.iterable_campaign_builder` gl

        WHERE
            utm_lineitemid = @line_item_id

        GROUP BY
            utm_campaign,
            utm_medium,
            utm_source,
            utm_content,
            utm_lineitemid,
            product_id,
            audience_product_name,
            site,
            indication
    """

    try:
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter('line_item_id', 'INTEGER', line_item_id)
            ]
        )

        job = client.query_and_wait(sql, job_config=config)
        rows = [dict(row) for row in job]
        return rows
    finally:
        client.close()
