
import os
import time
import random
import requests
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse, urlunparse, quote
from bs4 import BeautifulSoup
import uuid
from common.logging.logging_config import get_logger
from .els_types import ArticleFullText, Authors, Entry, EntryLink, PreProcessedData, SearchResultsPayload
from google.cloud import bigquery
from .genai import ExtractFirstParagraph


# Use our structured logger
logger = get_logger('ai.els_api')

RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
DEFAULT_RATE_LIMIT_DELAY = 0.5

class ELSApi:
    def __init__(self, query:str, source_issn:str = None, auto_search:bool = True, rate_limit_delay:float = DEFAULT_RATE_LIMIT_DELAY, table_id:str = 'formedics-prod.aga_summarizations.science_direct', start_date:str = None):
        """
        Initialize the ELSApi client.

        Args:
            query: Search query string (required)
            source_issn: Journal ISSN code (e.g., "0016-5085") for duplicate checking in BigQuery
            auto_search: If True, automatically executes the search in __init__.
                        If False, you must call execute_search() manually.
                        Default True for backward compatibility.
            rate_limit_delay: Delay in seconds between API requests to avoid rate limits.
                            Default 0.5 seconds.
            table_id: BigQuery table ID for duplicate checking (default: formedics-prod.aga_summarizations.science_direct)
            start_date: Filter articles published on or after this date (format: YYYY-MM-DD)

        Raises:
            ValueError: If query is empty

        Example:
            # Automatic search (default, backward compatible):
            els = ELSApi('IBD AND src("Clinical Gastroenterology and Hepatology")')

            # With duplicate checking against database:
            els = ELSApi('IBD AND src("Clinical Gastroenterology and Hepatology")', source_issn="1542-3565")

            # Manual search (better for testing):
            els = ELSApi('IBD AND src("Clinical Gastroenterology and Hepatology")', auto_search=False)
            els.execute_search()

            # Custom rate limit:
            els = ELSApi('IBD AND src("Clinical Gastroenterology and Hepatology")', rate_limit_delay=1.0)
        """
        self.run_uuid = uuid.uuid4()
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        self.source_issn = source_issn
        self.table_id = table_id
        self.bq_client = None
        self.start_date = start_date

        logger.info(f'(RUN ID: {self.run_uuid}) - Initializing ELSApi with query: {query}, rate_limit_delay: {rate_limit_delay}s, source_issn: {source_issn}, start_date: {start_date}')

        if not query:
            logger.error(f'(RUN ID: {self.run_uuid}) - No query provided')
            raise ValueError('A journal search query must be provided. eg: \'IBD AND src("Clinical Gastroenterology and Hepatology")\'')

        self.api_key = os.environ.get('ELSEVIER_API_KEY')

        if not self.api_key:
            logger.error(f'(RUN ID: {self.run_uuid}) - ELSEVIER_API_KEY environment variable not set')
            raise ValueError('ELSEVIER_API_KEY environment variable must be set')

        self.query = query
        self.base_url = 'https://api.elsevier.com'
        self.headers = {
            'X-ELS-APIKey': self.api_key,
            'Accept': 'application/json',
        }
        self.data:PreProcessedData = []
        self.journal_entries:List[Entry] = []
        self.processed_piis = set()

        # Fetch existing PIIs from database if source_issn is provided
        if self.source_issn:
            self._load_existing_piis_from_db()

        if auto_search:
            logger.info(f'(RUN ID: {self.run_uuid}) - ELSApi initialized, starting automatic search')
            self.execute_search()
        else:
            logger.info(f'(RUN ID: {self.run_uuid}) - ELSApi initialized (call execute_search() to run query)')


    def execute_search(self, start:int = 0, count:int = 25, fetch_all:bool = True) -> list:
        """
        Execute the search query that was provided during initialization.

        Args:
            start: Starting index for results (default: 0)
            count: Number of results per page (default: 25, max: 100)
            fetch_all: If True, fetches all available results using pagination (default: True)

        Returns:
            List of search results

        Raises:
            Exception: If the search fails
        """
        logger.info(f'(RUN ID: {self.run_uuid}) - Executing search with fetch_all={fetch_all}')

        if not fetch_all:
            return self._search(self.query, start, count)

        all_results = []
        page_size = min(count, 100)
        current_start = start
        total_results = None

        while True:
            logger.info(f'(RUN ID: {self.run_uuid}) - Fetching page starting at index {current_start}')
            results = self._search(self.query, current_start, page_size)

            if total_results is None:
                total_results = getattr(self, '_total_results', 0)
                logger.info(f'(RUN ID: {self.run_uuid}) - Total results available: {total_results}')

            if not results or len(results) == 0:
                logger.info(f'(RUN ID: {self.run_uuid}) - No more results, pagination complete')
                break

            all_results.extend(results)
            current_start += len(results)

            if total_results and current_start >= total_results:
                logger.info(f'(RUN ID: {self.run_uuid}) - Fetched all {total_results} results')
                break

            if len(results) < page_size:
                logger.info(f'(RUN ID: {self.run_uuid}) - Received partial page ({len(results)} < {page_size}), pagination complete')
                break

        logger.info(f'(RUN ID: {self.run_uuid}) - Pagination complete: {len(all_results)} total entries retrieved')
        return all_results


    def _send_request(
        self,
        make_request:Callable[[], requests.Response],
        max_retries:int = 5,
        base_delay:float = 1.0,
        max_delay:float = 60.0,
    ) -> Dict[str, Any]:
        """
        Call `make_request` (which should return a requests.Response) with
        exponential backoff and jitter. Raises on final failure.

        Example `make_request`:

            def make_request():
                return requests.get(url, params=params, headers=headers)
        """
        attempt = 0

        while True:
            if self.last_request_time > 0:
                time_since_last_request = time.time() - self.last_request_time
                if time_since_last_request < self.rate_limit_delay:
                    sleep_time = self.rate_limit_delay - time_since_last_request
                    logger.debug(f'(RUN ID: {self.run_uuid}) - Rate limiting: sleeping for {sleep_time:.2f}s')
                    time.sleep(sleep_time)

            try:
                logger.debug(f'(RUN ID: {self.run_uuid}) - Sending request (attempt {attempt + 1}/{max_retries + 1})')
                start_time = time.time()
                resp = make_request()
                self.last_request_time = time.time()
                elapsed_time = self.last_request_time - start_time

                logger.info(f'(RUN ID: {self.run_uuid}) - Request completed with status {resp.status_code} in {elapsed_time:.2f}s')

                if resp.ok:
                    logger.debug(f'(RUN ID: {self.run_uuid}) - Request successful, parsing JSON response')
                    try:
                        return resp.json()
                    except requests.exceptions.JSONDecodeError as e:
                        logger.error(f'(RUN ID: {self.run_uuid}) - Failed to parse JSON response: {str(e)}', exc_info=True)
                        logger.debug(f'(RUN ID: {self.run_uuid}) - Response content (first 500 chars): {resp.text[:500]}')
                        raise ValueError(f'Invalid JSON response from API: {str(e)}')

                logger.warning(f'(RUN ID: {self.run_uuid}) - Request failed with status {resp.status_code}')

                if resp.status_code not in RETRY_STATUS_CODES:
                    logger.error(f'(RUN ID: {self.run_uuid}) - Non-retryable status code {resp.status_code}, raising exception')
                    resp.raise_for_status()

                if attempt >= max_retries:
                    logger.error(f'(RUN ID: {self.run_uuid}) - Max retries ({max_retries}) exceeded for request')
                    resp.raise_for_status()

                delay = min(max_delay, base_delay * (2 ** attempt))
                delay = delay * (0.5 + random.random() / 2.0)
                logger.info(f'(RUN ID: {self.run_uuid}) - Retrying after {delay:.2f}s (attempt {attempt + 1}/{max_retries})')
                time.sleep(delay)
                attempt += 1
            except requests.exceptions.RequestException as e:
                logger.error(f'(RUN ID: {self.run_uuid}) - Request exception on attempt {attempt + 1}: {str(e)}', exc_info=True)
                if attempt >= max_retries:
                    raise
                delay = min(max_delay, base_delay * (2 ** attempt))
                delay = delay * (0.5 + random.random() / 2.0)
                logger.info(f'(RUN ID: {self.run_uuid}) - Retrying after request exception, waiting {delay:.2f}s')
                time.sleep(delay)
                attempt += 1
            except ValueError:
                raise


    def _get_content(self, pii:str) -> Optional[str]:
        """
        Retrieve the abstract (dc:description) for an article by PII.

        Args:
            pii: Publisher Item Identifier

        Returns:
            The abstract text or None if retrieval fails (article will be skipped)
        """
        if not pii:
            logger.warning(f'(RUN ID: {self.run_uuid}) - Empty PII provided to _get_content, skipping')
            return None

        try:
            logger.info(f'(RUN ID: {self.run_uuid}) - Retrieving content information for PII: {pii}')

            encoded_pii = quote(pii, safe='')
            url = f'{self.base_url}/content/article/pii/{encoded_pii}'

            logger.debug(f'(RUN ID: {self.run_uuid}) - Encoded PII URL: {url}')

            def make_request():
                return requests.get(url, headers=self.headers, timeout=30)

            resp = self._send_request(make_request)

            article_obj:ArticleFullText = resp.get('full-text-retrieval-response', {})
            original_text = article_obj.get('originalText', '')
            coredata = article_obj.get('coredata', {})
            abstract = coredata.get('dc:description', '')
            has_original_text = original_text and isinstance(original_text, str) and original_text.strip()
            has_abstract = abstract and isinstance(abstract, str) and abstract.strip()

            if not has_original_text and not has_abstract:
                logger.warning(f'(RUN ID: {self.run_uuid}) - No content found for PII {pii} (missing both originalText and dc:description)')
                logger.debug(f'(RUN ID: {self.run_uuid}) - Response structure: {list(resp.keys())}, originalText type: {type(original_text).__name__}, abstract type: {type(abstract).__name__}')
                return None

            content_source = 'originalText' if has_original_text else 'abstract'
            content_length = len(original_text) if has_original_text else len(abstract)
            logger.info(f'(RUN ID: {self.run_uuid}) - Successfully retrieved content for PII: {pii} (source: {content_source}, length: {content_length} chars)')
            return article_obj
        except requests.exceptions.RequestException as e:
            logger.error(f'(RUN ID: {self.run_uuid}) - Request failed for PII {pii}: {type(e).__name__}: {str(e)}', exc_info=True)
            return None
        except Exception as e:
            logger.error(f'(RUN ID: {self.run_uuid}) - Unexpected error retrieving content for PII {pii}: {type(e).__name__}: {str(e)}', exc_info=True)
            return None


    def _search(self, query:str, start:int = 0, count:int = 25) -> list:
        """
        Search ScienceDirect for articles matching the query.

        Args:
            query: Search query string
            start: Starting index for results (default: 0)
            count: Number of results to return (default: 25, max: 100)

        Returns:
            List of search results

        Raises:
            Exception: If the search fails
        """
        logger.info(f'(RUN ID: {self.run_uuid}) - Running Elsevier journal search with query: "{query}", start: {start}, count: {count}')

        try:
            start_time = time.time()
            url = f'{self.base_url}/content/search/scopus'
            params = {
                'query': query,
                'start': start,
                'count': min(count, 100),
            }

            logger.debug(f'(RUN ID: {self.run_uuid}) - Search URL: {url}, params: {params}')

            def make_request():
                return requests.get(url, headers=self.headers, params=params, timeout=30)

            resp = self._send_request(make_request)

            if not isinstance(resp, dict):
                logger.error(f'(RUN ID: {self.run_uuid}) - Invalid response type: expected dict, got {type(resp).__name__}')
                raise ValueError(f'Invalid API response: expected dictionary, got {type(resp).__name__}')

            search_results:SearchResultsPayload = resp.get('search-results')
            if not search_results:
                logger.warning(f'(RUN ID: {self.run_uuid}) - No search-results key in response')
                logger.debug(f'(RUN ID: {self.run_uuid}) - Response keys: {list(resp.keys())}')
                results = []
                total_results = 0
            else:
                results:List[Entry] = search_results.get('entry', [])
                total_results = search_results.get('opensearch:totalResults', 'unknown')

                if not isinstance(results, list):
                    logger.warning(f'(RUN ID: {self.run_uuid}) - Entry field is not a list: {type(results).__name__}, converting to list')
                    results = [results] if results else []

            self._total_results = int(total_results) if isinstance(total_results, (int, str)) and str(total_results).isdigit() else 0

            elapsed_time = time.time() - start_time
            logger.info(f'(RUN ID: {self.run_uuid}) - Search completed in {elapsed_time:.2f}s: {len(results)} results retrieved (total available: {total_results})')

            self.journal_entries = results

            if self.start_date:
                initial_count = len(self.journal_entries)
                self.journal_entries = [
                    entry for entry in self.journal_entries
                    if entry.get('prism:coverDate') and entry.get('prism:coverDate') >= self.start_date
                ]
                logger.info(f'(RUN ID: {self.run_uuid}) - Applied date filter on journal entries',
                           extra={
                               'start_date': self.start_date,
                               'before_filter': initial_count,
                               'after_filter': len(self.journal_entries),
                               'filtered_out': initial_count - len(self.journal_entries)
                           })

            self._format_entries()

            logger.info(f'(RUN ID: {self.run_uuid}) - Search and formatting completed successfully')
            return results
        except Exception as e:
            logger.error(f'(RUN ID: {self.run_uuid}) - Exception occurred during search: {type(e).__name__}: {str(e)}', exc_info=True)
            raise


    def _load_existing_piis_from_db(self) -> None:
        """
        Query BigQuery to fetch existing PIIs for the current journal (source_issn).
        Populates self.processed_piis with PIIs already in the database to prevent duplicates.
        """
        if not self.source_issn:
            logger.debug(f'(RUN ID: {self.run_uuid}) - No source_issn provided, skipping database duplicate check')
            return

        try:
            logger.info(f'(RUN ID: {self.run_uuid}) - Querying BigQuery for existing PIIs (source_issn: {self.source_issn})')
            start_time = time.time()
            self.bq_client = bigquery.Client(project='formedics-prod')
            query = f"""
                SELECT DISTINCT pii
                FROM `{self.table_id}`
                WHERE source_issn = @source_issn
                  AND pii IS NOT NULL
                  AND pii != ''
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter('source_issn', 'STRING', self.source_issn)
                ]
            )

            query_job = self.bq_client.query(query, job_config=job_config)
            results = query_job.result()
            existing_piis = {row.pii for row in results}
            self.processed_piis.update(existing_piis)
            duration_ms = (time.time() - start_time) * 1000

            logger.info(f'(RUN ID: {self.run_uuid}) - Loaded {len(existing_piis)} existing PIIs from database',
                       source_issn=self.source_issn,
                       duration_ms=round(duration_ms, 2),
                       bytes_processed=query_job.total_bytes_processed,
                       job_id=query_job.job_id)

        except Exception as e:
            logger.error(f'(RUN ID: {self.run_uuid}) - Failed to load existing PIIs from database: {type(e).__name__}: {str(e)}',
                        exc_info=True)
            logger.warning(f'(RUN ID: {self.run_uuid}) - Continuing without database duplicate checking')
            # Don't raise - continue processing without database duplicate checking
        finally:
            if self.bq_client:
                self.bq_client.close()
                self.bq_client = None


    def _format_entries(self) -> None:
        logger.info(f'(RUN ID: {self.run_uuid}) - Formatting {len(self.journal_entries)} journal entries')
        successful_entries = 0
        failed_entries = 0
        duplicate_entries = 0
        db_duplicates = 0
        initial_db_piis = len(self.processed_piis)

        for idx, rec in enumerate(self.journal_entries, 1):
            pii = rec.get('pii', '')
            title = rec.get('dc:title', 'Unknown').encode('utf-8')
            title_preview = str(title)[:50] if title else 'Unknown'

            logger.debug(f'(RUN ID: {self.run_uuid}) - Processing entry {idx}/{len(self.journal_entries)}: PII={pii}, Title={title_preview}...')

            if pii in self.processed_piis:
                duplicate_entries += 1

                if idx == 1 or duplicate_entries <= initial_db_piis:
                    db_duplicates += 1
                    logger.debug(f'(RUN ID: {self.run_uuid}) - Skipping duplicate PII from database: {pii} (entry {idx})')
                else:
                    logger.debug(f'(RUN ID: {self.run_uuid}) - Skipping duplicate PII in current batch: {pii} (entry {idx})')
                continue

            try:
                content = self._get_content(pii)

                if content:
                    coredata = content.get('coredata', {})
                    raw_abstract = coredata.get('dc:description', None)
                    abstract = raw_abstract if isinstance(raw_abstract, str) else ''
                    original_text = content.get('originalText', '')

                    # if raw_abstract and len(raw_abstract) > 0:
                    #     abstract = raw_abstract
                    # else:
                    #     gen_abstract = ExtractFirstParagraph(self.run_uuid)
                    #     abstract = gen_abstract.generate(original_text)

                    # if original_text and isinstance(original_text, str) and original_text.strip():
                    if len(original_text) > 0:
                        article_text = ' '.join(original_text.split())
                    else:
                        article_text = abstract
                        logger.debug(f'(RUN ID: {self.run_uuid}) - No valid originalText for PII {pii}, using abstract as content')

                    article = {
                        'title': self._remove_html_tags_regex(rec.get('dc:title', '')),
                        'url': self._get_scidir_href_no_query(coredata.get('link', [])),
                        'creator': rec.get('dc:creator', ''),
                        'authors': self._flatten_authors(coredata.get('dc:creator', [])),
                        'abstract': self._remove_html_tags_regex(abstract),
                        'content': self._remove_html_tags_regex(article_text),
                        'openaccess': rec.get('openaccess'),
                        'openaccessFlag': rec.get('openaccessFlag'),
                        'pii': pii,
                        'doi': rec.get('prism:doi'),
                        'publication_date': rec.get('prism:coverDate') # Format: YYYY-MM-DD
                    }

                    self.data.append(article)
                    self.processed_piis.add(pii)
                    successful_entries += 1
                    logger.debug(f'(RUN ID: {self.run_uuid}) - Successfully formatted entry {idx}: {title_preview}...')
                else:
                    failed_entries += 1
                    logger.warning(f'(RUN ID: {self.run_uuid}) - No content retrieved for entry {idx} (PII: {pii})')
            except Exception as e:
                failed_entries += 1
                logger.error(f'(RUN ID: {self.run_uuid}) - Failed to format entry {idx} (PII: {pii}): {type(e).__name__}: {str(e)}', exc_info=True)

        logger.info(f'(RUN ID: {self.run_uuid}) - Formatting complete: {successful_entries} successful, {failed_entries} failed, {duplicate_entries} duplicates skipped ({db_duplicates} from database, {duplicate_entries - db_duplicates} in current batch), {len(self.data)} total articles')


    def _get_scidir_href_no_query(self, links:List[EntryLink]) -> str:
        """Extract ScienceDirect URL from links array and remove query parameters."""
        if not links:
            logger.debug(f'(RUN ID: {self.run_uuid}) - No links provided to _get_scidir_href_no_query')
            return ''

        for link in links:
            if isinstance(link, dict) and link.get('@rel') == 'scidir':
                href = link.get('@href', '')
                parsed = urlparse(href)
                cleaned = urlunparse(parsed._replace(query='', fragment=''))
                logger.debug(f'(RUN ID: {self.run_uuid}) - Extracted ScienceDirect URL: {cleaned}')
                return cleaned

        logger.debug(f'(RUN ID: {self.run_uuid}) - No ScienceDirect link found in links array')
        return ''


    def _flatten_authors(self, authors:Authors) -> list[str]:
        """Flatten authors list into simple string array."""
        if not authors:
            return []

        if not isinstance(authors, list):
            authors = [authors]

        flattened = [author.get('$', '') for author in authors if isinstance(author, dict)]
        logger.debug(f'(RUN ID: {self.run_uuid}) - Flattened {len(flattened)} authors')
        return flattened


    def _remove_html_tags_regex(self, text:str) -> str:
        """Remove HTML tags from text using BeautifulSoup."""
        if not text:
            return ''

        try:
            clean = text.encode('utf-8')
            clean = BeautifulSoup(clean, 'html.parser')
            cleaned_text = clean.get_text().strip()
            return cleaned_text
        except Exception as e:
            logger.warning(f'(RUN ID: {self.run_uuid}) - Failed to remove HTML tags: {type(e).__name__}: {str(e)}')
            return text
