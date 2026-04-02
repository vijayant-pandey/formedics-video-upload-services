from typing import List, Dict, Any
from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput
from google.cloud import bigquery
import vertexai
import time
from common.logging.logging_config import get_logger
from datetime import datetime, timezone


logger = get_logger('ai.embeddings')

class EmbeddingGenerator:
    """Generate text embeddings for journal article summaries using Vertex AI."""

    def __init__(self, project_id:str = 'formedics-prod', location:str = 'us-central1'):
        """
        Initialize the embedding generator.

        Args:
            project_id: GCP project ID for Vertex AI and BigQuery
            location: GCP region for Vertex AI (default: us-central1)
        """
        self.project_id = project_id
        self.location = location

        vertexai.init(project='fm-gemini-code-sb', location=location)

        self.model = TextEmbeddingModel.from_pretrained('gemini-embedding-001')
        self.bq_client = bigquery.Client(project=project_id)

        logger.info('EmbeddingGenerator initialized',
                   project_id=project_id,
                   location=location,
                   model='gemini-embedding-001')

    def generate_embedding(self, text:str, task_type:str = 'RETRIEVAL_DOCUMENT') -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to generate embedding for
            task_type: Task type for the embedding model
                      - RETRIEVAL_DOCUMENT: For documents in your corpus
                      - RETRIEVAL_QUERY: For user search queries

        Returns:
            List of 1408 float values representing the embedding
        """
        if not text or not text.strip():
            logger.warning('Empty text provided for embedding generation')
            return [0.0] * 1408  # Return zero vector for empty text

        embeddings = self.generate_embeddings_batch([text], task_type=task_type)
        return embeddings[0]

    def generate_embeddings_batch(
        self,
        texts:List[str],
        task_type:str = 'RETRIEVAL_DOCUMENT'
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.

        Args:
            texts: List of texts to generate embeddings for
            task_type: Task type for the embedding model

        Returns:
            List of embeddings, each being a list of 768 floats
        """
        if not texts:
            return []

        try:
            logger.info('Generating embeddings in batch',
                       batch_size=len(texts))

            start_time = time.time()
            embeddings = []
            batch_size = 5

            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                truncated_batch = [
                    text[:12000] if len(text) > 12000 else text
                    for text in batch
                ]

                embedding_inputs = [
                    TextEmbeddingInput(text=text, task_type=task_type)
                    for text in truncated_batch
                ]

                batch_embeddings = self.model.get_embeddings(embedding_inputs)
                embeddings.extend([emb.values for emb in batch_embeddings])

                if i + batch_size < len(texts):
                    time.sleep(0.1)

            duration_ms = (time.time() - start_time) * 1000
            logger.info('Batch embeddings generated',
                       count=len(embeddings),
                       duration_ms=round(duration_ms, 2))

            return embeddings
        except Exception as e:
            logger.error('Failed to generate batch embeddings',
                        error_type=type(e).__name__,
                        error=str(e))
            raise

    def save_embeddings_to_bigquery(
        self,
        summaries:List[Dict[str, Any]],
        table_id:str = 'formedics-prod.aga_summarizations.science_direct',
        source_journal:str = None,
        source_issn:str = None
    ) -> int:
        """
        Generate embeddings for summaries and save to BigQuery.

        Args:
            summaries: List of summary dictionaries (output from JournalSummaryGenerator)
            table_id: BigQuery table ID
            source_journal: Journal name (e.g., "Gastroenterology")
            source_issn: Journal ISSN code (e.g., "0016-5085")

        Returns:
            Number of rows inserted
        """
        if not summaries:
            logger.warning('No summaries provided for embedding generation')
            return 0

        logger.info('Starting embedding generation and BigQuery save',
                   summary_count=len(summaries),
                   table_id=table_id,
                   source_journal=source_journal,
                   source_issn=source_issn)

        try:
            start_time = time.time()
            embedding_texts = []
            for summary in summaries:
                embedding_texts.append(summary.get('embedding_text'))
            embeddings = self.generate_embeddings_batch(embedding_texts)
            rows_to_insert = []
            current_timestamp = datetime.now(timezone.utc).isoformat()

            for summary, embedding_vector in zip(summaries, embeddings):
                row = {
                    'headline': summary.get('headline', ''),
                    'authors': summary.get('authors', []),
                    'excerpt': summary.get('excerpt', ''),
                    'summary': summary.get('summary', ''),
                    'abstract': summary.get('abstract', ''),
                    'url': summary.get('url', ''),
                    'openaccess': summary.get('openaccess', False),
                    'meshcodes': summary.get('meshcodes', []),
                    'icd10_codes': summary.get('icd10_codes', []),
                    'citations': summary.get('citations', ''),
                    'key_takeaways': summary.get('key_takeaways', []),
                    'study_objective': summary.get('study_objective', []),
                    'methods': summary.get('methods', []),
                    'results': summary.get('results', []),
                    'clinical_relevance': summary.get('clinical_relevance', []),
                    'source_journal': source_journal,
                    'source_issn': source_issn,
                    'publication_date': summary.get('publication_date'),
                    'doi': summary.get('doi'),
                    'pii': summary.get('pii'),
                    'meta_description': summary.get('meta_description', ''),
                    'tags': summary.get('tags', ''),
                    'text_embedding': embedding_vector,
                    'created_at': current_timestamp
                }
                rows_to_insert.append(row)

            job_config = bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
                schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
            )

            load_job = self.bq_client.load_table_from_json(
                rows_to_insert,
                table_id,
                job_config=job_config
            )

            load_job.result()

            duration_ms = (time.time() - start_time) * 1000

            if load_job.errors:
                logger.error('BigQuery load job errors',
                           error_count=len(load_job.errors),
                           errors=load_job.errors)
                raise Exception(f'BigQuery load failed: {load_job.errors}')

            logger.info('Embeddings saved to BigQuery successfully',
                       rows_inserted=len(rows_to_insert),
                       duration_ms=round(duration_ms, 2),
                       job_id=load_job.job_id)

            return len(rows_to_insert)
        except Exception as e:
            logger.error('Failed to save embeddings to BigQuery',
                        error_type=type(e).__name__,
                        error=str(e))
            raise

    def _create_embedding_text(self, summary:Dict[str, Any]) -> str:
        """
        Create embedding text from summary dictionary.

        Args:
            summary: Summary dictionary

        Returns:
            Concatenated text for embedding generation
        """
        parts = []

        if summary.get('headline'):
            parts.append(f"Title: {summary['headline']}")

        if summary.get('summary'):
            parts.append(f"Summary: {summary['summary']}")

        if summary.get('key_takeaways'):
            takeaways = '. '.join(summary['key_takeaways'])
            parts.append(f"Key Takeaways: {takeaways}")

        if summary.get('clinical_relevance'):
            relevance = '. '.join(summary['clinical_relevance'])
            parts.append(f"Clinical Relevance: {relevance}")

        return '. '.join(parts)

    def search_similar(
        self,
        issn:str,
        query_text:str,
        top_k:int = 50,
        table_id:str = 'formedics-prod.aga_summarizations.science_direct'
    ) -> List[Dict[str, Any]]:
        """
        Search for similar articles using vector similarity.

        Args:
            query_text: User's search query
            top_k: Number of results to return
            table_id: BigQuery table ID

        Returns:
            List of similar articles with similarity scores
        """
        logger.info('Searching for similar articles',
                   query=query_text,
                   top_k=top_k)

        try:
            start_time = time.time()
            query_embedding = self.generate_embedding(
                query_text,
                task_type="RETRIEVAL_QUERY"
            )
            query = f"""
                SELECT
                    base.headline,
                    base.authors,
                    base.excerpt,
                    base.summary,
                    base.abstract,
                    base.url,
                    base.openaccess,
                    base.citations,
                    base.key_takeaways,
                    base.study_objective,
                    base.methods,
                    base.results,
                    base.clinical_relevance,
                    base.source_journal,
                    base.publication_date,
                    base.doi,
                    base.pii,
                    base.meta_description,
                    base.tags,
                    distance

                FROM
                    VECTOR_SEARCH(
                        TABLE `{table_id}`,
                        'text_embedding',
                        (SELECT {query_embedding} AS ml_generate_embedding_result),
                        top_k => {top_k}
                    )

                WHERE
                    base.source_issn = '{issn}'

                ORDER BY distance
            """

            results = self.bq_client.query(query).result()
            articles = []

            for row in results:
                articles.append(dict(row))

            duration_ms = (time.time() - start_time) * 1000

            logger.info('Similar articles found',
                       result_count=len(articles),
                       duration_ms=round(duration_ms, 2))

            return articles
        except Exception as e:
            logger.error('Failed to search similar articles',
                        error_type=type(e).__name__,
                        error=str(e))
            raise

    def __del__(self):
        """Close BigQuery client on cleanup."""
        if hasattr(self, 'bq_client'):
            self.bq_client.close()
