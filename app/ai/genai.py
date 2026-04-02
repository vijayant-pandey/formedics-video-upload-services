from google import genai
from google.genai import types
from google.cloud import storage
import logging
import time
from json import dump, dumps, loads, JSONDecodeError, JSONDecoder
from abc import ABC, abstractmethod
from .prompts.subject_line import MODEL_PROMPT as SUBJECT_LINE_PROMPT
from .prompts.journal_summary import MODEL_PROMPT as JOURNAL_ENTRY_PROMPT
from .prompts.fake_abstract import MODEL_PROMPT as FAKE_ABSTRACT_PROMPT
from .prompts.ai_dectection import MODEL_PROMPT as AI_DETECTION_PROMPT
from .els_types import ArticleSummaryListSchema, FakeAbstract
from .dtypes import AIDetection, GeneratedSubjectLineResp
from datetime import datetime
import traceback
import os


MODEL = 'gemini-3-flash-preview'
# MODEL = 'gemini-2.5-flash'
logging.info(f'Initializing Gemini client with model: {MODEL}')

try:
    client = genai.Client(
        vertexai=True,
        project='fm-gemini-code-sb',
        location='global'
    )
    logging.info('Gemini client initialized successfully')
except Exception as e:
    logging.error(f'Failed to initialize Gemini client: {type(e).__name__}: {str(e)}', exc_info=True)
    raise


class EmptyAPIResponseError(Exception):
    """Raised when Gemini API returns empty response"""
    pass


class BaseGenerator(ABC):
    """Base class for Gemini content generators with common functionality."""

    def __init__(self, run_uuid: str = None):
        self.run_uuid = run_uuid
        if run_uuid:
            logging.info(f'(RUN ID: {self.run_uuid}) - Initializing {self.__class__.__name__}')

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this generator."""
        pass

    @abstractmethod
    def prepare_content(self, user_payload):
        """Prepare content for Gemini API request."""
        pass

    def get_response_schema(self):
        """Return the response schema for this generator. Override in subclasses."""
        return None

    def get_config(self):
        """Configure Gemini API generation settings."""
        if self.run_uuid:
            logging.debug(f'(RUN ID: {self.run_uuid}) - Building Gemini generation config')

        try:
            response_schema = self.get_response_schema()
            tools = None if response_schema else [types.Tool(google_search=types.GoogleSearch())]
            config = types.GenerateContentConfig(
                temperature=1,
                top_p=0.95,
                max_output_tokens=65535,
                safety_settings=[
                    types.SafetySetting(
                        category="HARM_CATEGORY_HATE_SPEECH",
                        threshold="OFF"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                        threshold="OFF"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        threshold="OFF"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_HARASSMENT",
                        threshold="OFF"
                    ),
                ],
                tools=tools,
                system_instruction=[types.Part.from_text(text=self.get_system_prompt())],
                thinking_config=types.ThinkingConfig(thinking_budget=-1),
                response_mime_type="application/json",
                response_schema=response_schema
            )

            if self.run_uuid:
                logging.debug(f'(RUN ID: {self.run_uuid}) - Config built: temperature=1, top_p=0.95, max_tokens=65535')
            return config
        except Exception as e:
            if self.run_uuid:
                logging.error(f'(RUN ID: {self.run_uuid}) - Failed to build config: {type(e).__name__}: {str(e)}', exc_info=True)
            raise

    def _clean_markdown_blocks(self, text: str) -> str:
        """Remove markdown code block markers from output."""
        if not text or not text.strip():
            if self.run_uuid:
                logging.warning(f'(RUN ID: {self.run_uuid}) - Empty text provided to _clean_markdown_blocks')
            return text

        stripped = text.strip()
        original_length = len(stripped)

        if stripped.startswith("```"):
            first_newline = stripped.find('\n')
            if first_newline > 0:
                stripped = stripped[first_newline + 1:].strip()
            else:
                stripped = stripped[3:].strip()

            if self.run_uuid:
                logging.debug(f'(RUN ID: {self.run_uuid}) - Removed opening markdown code block')

        if stripped.endswith("```"):
            stripped = stripped[:-3].strip()
            if self.run_uuid:
                logging.debug(f'(RUN ID: {self.run_uuid}) - Removed closing markdown code block')

        if self.run_uuid and len(stripped) < original_length * 0.5:
            logging.warning(f'(RUN ID: {self.run_uuid}) - Markdown cleaning removed >50% of content (original: {original_length}, cleaned: {len(stripped)})')

        return stripped

    def generate(self, dataset):
        """Generate content for the provided dataset using Gemini API."""
        if self.run_uuid:
            logging.info(f'(RUN ID: {self.run_uuid}) - Starting generation with {self.__class__.__name__}')
        else:
            print(f'Generating with {self.__class__.__name__}')

        try:
            start_time = time.time()
            contents = self.prepare_content(dataset)
            config = self.get_config()

            if self.run_uuid:
                logging.info(f'(RUN ID: {self.run_uuid}) - Calling Gemini API (model: {MODEL})')

            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=config,
            )

            elapsed_time = time.time() - start_time
            full_output = response.text if response.text else ''

            if self.run_uuid:
                logging.info(f'(RUN ID: {self.run_uuid}) - API call completed in {elapsed_time:.2f}s, output length: {len(full_output)} chars')
            else:
                print(f'Completed generation in {elapsed_time:.2f}s')

            if not full_output or not full_output.strip():
                error_msg = 'Gemini API returned empty response'
                if self.run_uuid:
                    logging.error(f'(RUN ID: {self.run_uuid}) - {error_msg}')
                raise EmptyAPIResponseError(error_msg)

            if self.run_uuid:
                logging.debug(f'(RUN ID: {self.run_uuid}) - Raw output before cleaning (first 500 chars): {full_output[:500]}')
                logging.debug(f'(RUN ID: {self.run_uuid}) - Processing output to remove markdown code blocks')

            stripped = self._clean_markdown_blocks(full_output)

            if not stripped or not stripped.strip():
                error_msg = f'Output became empty after markdown cleaning (original length: {len(full_output)})'
                if self.run_uuid:
                    logging.error(f'(RUN ID: {self.run_uuid}) - {error_msg}')
                    logging.error(f'(RUN ID: {self.run_uuid}) - Original output: {full_output[:1000]}')
                raise EmptyAPIResponseError(error_msg)

            if self.run_uuid:
                logging.debug(f'(RUN ID: {self.run_uuid}) - Cleaned output (first 500 chars): {stripped[:500]}')
                logging.info(f'(RUN ID: {self.run_uuid}) - Generation completed successfully, final output: {len(stripped)} chars')

            return stripped

        except Exception as e:
            if self.run_uuid:
                logging.error(f'(RUN ID: {self.run_uuid}) - Failed to generate content: {type(e).__name__}: {str(e)}', exc_info=True)
            raise


class JournalSummaryGenerator(BaseGenerator):
    """Generator for creating medical journal summaries."""

    def __init__(self, run_uuid: str, batch_size: int = 5, save_failed_to: str = 'gcs'):
        """
        Initialize the journal summary generator.

        Args:
            run_uuid: Unique identifier for this run
            batch_size: Number of articles to process in a single batch (default: 5)
                       Lower values reduce token usage but increase API calls
            save_failed_to: Where to save failed batches - 'local', 'gcs', 'both', or 'none' (default: 'gcs')
        """
        super().__init__(run_uuid)
        self.batch_size = batch_size
        self.save_failed_to = save_failed_to.lower() if save_failed_to else 'gcs'

    def get_system_prompt(self) -> str:
        """Return the journal summary system prompt."""
        return JOURNAL_ENTRY_PROMPT

    def get_response_schema(self):
        """Return the response schema for journal summaries."""
        return ArticleSummaryListSchema

    def prepare_content(self, user_payload):
        """Prepare content for Gemini API request."""
        logging.info(f'(RUN ID: {self.run_uuid}) - Preparing content for summarization')

        try:
            payload_size = len(dumps(user_payload))
            logging.info(f'(RUN ID: {self.run_uuid}) - User payload size: {payload_size} bytes, {len(user_payload)} articles')

            gen_summary = types.Part.from_text(
                text=dumps(user_payload)
            )

            content = [types.Content(role="user", parts=[gen_summary])]
            logging.debug(f'(RUN ID: {self.run_uuid}) - Content prepared successfully')
            return content
        except Exception as e:
            logging.error(f'(RUN ID: {self.run_uuid}) - Failed to prepare content: {type(e).__name__}: {str(e)}', exc_info=True)
            raise

    def _prepare_failed_batch_data(
        self,
        batch_data: list,
        batch_num: int,
        total_batches: int,
        error_info: str
    ) -> tuple[dict, str]:
        """
        Prepare common data structure for failed batch saving.

        Args:
            batch_data: The raw article data that failed to be summarized
            batch_num: Batch number that failed
            total_batches: Total number of batches
            error_info: Error description/details

        Returns:
            Tuple of (output_data dict, timestamp string)
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_data = {
            'run_uuid': str(self.run_uuid),
            'batch_num': batch_num,
            'total_batches': total_batches,
            'article_count': len(batch_data),
            'timestamp': timestamp,
            'error': error_info,
            'batch_data': batch_data
        }
        return output_data, timestamp

    def _save_failed_batch_to_local(
        self,
        batch_data: list,
        batch_num: int,
        total_batches: int,
        error_info: str
    ) -> None:
        """
        Save failed batch data to local file for later retry or analysis.

        Args:
            batch_data: The raw article data that failed to be summarized
            batch_num: Batch number that failed
            total_batches: Total number of batches
            error_info: Error description/details
        """
        try:
            output_data, timestamp = self._prepare_failed_batch_data(
                batch_data, batch_num, total_batches, error_info
            )

            error_dir = 'data/failed_batches'
            os.makedirs(error_dir, exist_ok=True)
            error_file = os.path.join(error_dir, f'batch_{batch_num}_{timestamp}.json')

            with open(error_file, 'w', encoding='utf-8') as f:
                dump(output_data, f, indent=2, ensure_ascii=False)

            logging.info(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches}: Saved failed batch to local file',
                        file_path=error_file,
                        article_count=len(batch_data))

        except Exception as file_err:
            logging.error(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches}: Failed to save to local file: {type(file_err).__name__}: {str(file_err)}',
                         exc_info=True)
            # Don't raise - this is a best-effort save

    def _save_failed_batch_to_gcs(
        self,
        batch_data: list,
        batch_num: int,
        total_batches: int,
        error_info: str,
        bucket_name: str = 'aga_summarization',
        project_id: str = 'formedics-prod'
    ) -> None:
        """
        Save failed batch data to Google Cloud Storage for later retry or analysis.

        Args:
            batch_data: The raw article data that failed to be summarized
            batch_num: Batch number that failed
            total_batches: Total number of batches
            error_info: Error description/details
            bucket_name: GCS bucket name (default: aga_summarization)
            project_id: GCP project ID (default: formedics-prod)
        """
        try:
            output_data, timestamp = self._prepare_failed_batch_data(
                batch_data, batch_num, total_batches, error_info
            )

            gcs_client = storage.Client(project=project_id)
            bucket = gcs_client.bucket(bucket_name)
            blob_name = f'failed_batches/{self.run_uuid}/batch_{batch_num}_{timestamp}.json'

            metadata = {
                'run_uuid': str(self.run_uuid),
                'batch_num': str(batch_num),
                'total_batches': str(total_batches),
                'article_count': str(len(batch_data)),
                'timestamp': timestamp,
                'error': error_info[:500]
            }

            blob = bucket.blob(blob_name)
            blob.metadata = metadata
            blob.upload_from_string(
                dumps(output_data, indent=2, ensure_ascii=False),
                content_type='application/json'
            )

            logging.info(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches}: Saved failed batch to GCS',
                        bucket=bucket_name,
                        blob_name=blob_name,
                        article_count=len(batch_data))

        except Exception as gcs_err:
            logging.error(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches}: Failed to save to GCS: {type(gcs_err).__name__}: {str(gcs_err)}',
                         exc_info=True)
            # Don't raise - this is a best-effort save

    def _save_failed_batch(
        self,
        batch_data: list,
        batch_num: int,
        total_batches: int,
        error_info: str
    ) -> None:
        """
        Save failed batch data based on the save_failed_to configuration.

        Args:
            batch_data: The raw article data that failed to be summarized
            batch_num: Batch number that failed
            total_batches: Total number of batches
            error_info: Error description/details
        """
        if self.save_failed_to == 'none':
            logging.debug(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches}: Skipping failed batch save (save_failed_to=none)')
            return

        if self.save_failed_to in ('local', 'both'):
            self._save_failed_batch_to_local(
                batch_data=batch_data,
                batch_num=batch_num,
                total_batches=total_batches,
                error_info=error_info
            )

        if self.save_failed_to in ('gcs', 'both'):
            self._save_failed_batch_to_gcs(
                batch_data=batch_data,
                batch_num=batch_num,
                total_batches=total_batches,
                error_info=error_info
            )

    def generate(self, dataset):
        """
        Generate summaries for all articles, processing in batches if needed.

        Args:
            dataset: List of articles to summarize

        Returns:
            JSON string containing all summaries
        """
        if not dataset:
            logging.warning(f'(RUN ID: {self.run_uuid}) - Empty dataset provided')
            return '[]'

        total_articles = len(dataset)

        if total_articles <= self.batch_size:
            logging.info(f'(RUN ID: {self.run_uuid}) - Processing {total_articles} articles in single batch')
            return super().generate(dataset)

        logging.info(f'(RUN ID: {self.run_uuid}) - Processing {total_articles} articles in batches of {self.batch_size}')
        all_summaries = []

        for batch_idx in range(0, total_articles, self.batch_size):
            batch_end = min(batch_idx + self.batch_size, total_articles)
            batch = dataset[batch_idx:batch_end]
            batch_num = (batch_idx // self.batch_size) + 1
            total_batches = (total_articles + self.batch_size - 1) // self.batch_size

            logging.info(f'(RUN ID: {self.run_uuid}) - Processing batch {batch_num}/{total_batches} ({len(batch)} articles, indices {batch_idx}-{batch_end-1})')

            max_retries = 2
            retry_delay = 2.0 # seconds

            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        logging.info(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches}: Retry attempt {attempt}/{max_retries}')
                        time.sleep(retry_delay * attempt)
                    batch_result = super().generate(batch)
                    break

                except Exception as api_err:
                    if attempt < max_retries:
                        logging.warning(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches}: API error on attempt {attempt + 1}, will retry: {type(api_err).__name__}: {str(api_err)}')
                        continue
                    else:
                        logging.error(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches}: All retry attempts exhausted')
                        raise

            try:
                if not batch_result or not batch_result.strip():
                    logging.error(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches}: Empty result from API')

                    self._save_failed_batch(
                        batch_data=batch,
                        batch_num=batch_num,
                        total_batches=total_batches,
                        error_info='Empty result from API'
                    )

                    logging.warning(f'(RUN ID: {self.run_uuid}) - Skipping failed batch and continuing with remaining batches')
                    continue

                logging.debug(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches} result (first 500 chars): {batch_result[:500]}')

                try:
                    batch_summaries = loads(batch_result)
                except JSONDecodeError as json_err:
                    if self.save_failed_to in ('local', 'both'):
                        try:
                            error_dir = 'data/json_errors'
                            os.makedirs(error_dir, exist_ok=True)
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            error_file = os.path.join(error_dir, f'batch_{batch_num}_error_{timestamp}.txt')

                            with open(error_file, 'w', encoding='utf-8') as f:
                                f.write(f"Batch: {batch_num}/{total_batches}\n")
                                f.write(f"Error: {str(json_err)}\n")
                                f.write(f"Run UUID: {self.run_uuid}\n")
                                f.write(f"Output length: {len(batch_result)} characters\n")
                                f.write("=" * 80 + "\n")
                                f.write("Full raw output from API (not truncated):\n")
                                f.write("=" * 80 + "\n")
                                f.write(batch_result)

                            logging.info(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches}: Saved complete output ({len(batch_result)} chars) to {error_file}')
                        except Exception as file_err:
                            logging.warning(f'(RUN ID: {self.run_uuid}) - Failed to save error output to file: {str(file_err)}')

                    if "Extra data" in str(json_err):
                        logging.warning(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches}: Multiple JSON arrays detected, attempting to parse separately')

                        try:
                            batch_summaries = []
                            decoder = JSONDecoder()
                            idx = 0
                            while idx < len(batch_result):
                                while idx < len(batch_result) and batch_result[idx].isspace():
                                    idx += 1
                                if idx >= len(batch_result):
                                    break

                                obj, end_idx = decoder.raw_decode(batch_result, idx)
                                if isinstance(obj, list):
                                    batch_summaries.extend(obj)
                                else:
                                    batch_summaries.append(obj)
                                idx += end_idx

                            logging.info(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches}: Successfully parsed multiple JSON arrays ({len(batch_summaries)} summaries)')
                        except Exception as parse_err:
                            logging.error(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches}: Failed to parse multiple JSON arrays: {str(parse_err)}')
                            logging.error(f'(RUN ID: {self.run_uuid}) - Invalid JSON content (first 1000 chars): {batch_result[:1000]}')

                            self._save_failed_batch(
                                batch_data=batch,
                                batch_num=batch_num,
                                total_batches=total_batches,
                                error_info=f'Failed to parse multiple JSON arrays: {str(parse_err)}'
                            )

                            logging.warning(f'(RUN ID: {self.run_uuid}) - Skipping failed batch and continuing with remaining batches')
                            continue
                    else:
                        logging.error(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches}: JSON parsing failed: {str(json_err)}')
                        logging.error(f'(RUN ID: {self.run_uuid}) - Invalid JSON content (first 1000 chars): {batch_result[:1000]}')

                        self._save_failed_batch(
                            batch_data=batch,
                            batch_num=batch_num,
                            total_batches=total_batches,
                            error_info=f'JSON parsing failed: {str(json_err)}'
                        )

                        logging.warning(f'(RUN ID: {self.run_uuid}) - Skipping failed batch and continuing with remaining batches')
                        continue

                if not isinstance(batch_summaries, list):
                    logging.error(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches}: Expected list, got {type(batch_summaries).__name__}')

                    self._save_failed_batch(
                        batch_data=batch,
                        batch_num=batch_num,
                        total_batches=total_batches,
                        error_info=f'Expected list, got {type(batch_summaries).__name__}'
                    )

                    logging.warning(f'(RUN ID: {self.run_uuid}) - Skipping failed batch and continuing with remaining batches')
                    continue

                all_summaries.extend(batch_summaries)

                logging.info(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches} completed: {len(batch_summaries)} summaries generated')

            except EmptyAPIResponseError as empty_err:
                logging.error(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches}: {str(empty_err)}')

                self._save_failed_batch(
                    batch_data=batch,
                    batch_num=batch_num,
                    total_batches=total_batches,
                    error_info=str(empty_err)
                )

                logging.warning(f'(RUN ID: {self.run_uuid}) - Skipping failed batch and continuing with remaining batches')
            except Exception as e:
                logging.error(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches}: Unexpected error: {type(e).__name__}: {str(e)}', exc_info=True)

                self._save_failed_batch(
                    batch_data=batch,
                    batch_num=batch_num,
                    total_batches=total_batches,
                    error_info=f'{type(e).__name__}: {str(e)}'
                )

                if self.save_failed_to in ('local', 'both'):
                    try:
                        error_dir = 'data/json_errors'
                        os.makedirs(error_dir, exist_ok=True)
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        error_file = os.path.join(error_dir, f'batch_{batch_num}_sdk_error_{timestamp}.txt')

                        with open(error_file, 'w', encoding='utf-8') as f:
                            f.write(f"Batch: {batch_num}/{total_batches}\n")
                            f.write(f"Error Type: {type(e).__name__}\n")
                            f.write(f"Error: {str(e)}\n")
                            f.write(f"Run UUID: {self.run_uuid}\n")
                            f.write("=" * 80 + "\n")
                            f.write("Note: This error occurred during SDK streaming before any response was received.\n")
                            f.write("=" * 80 + "\n")
                            f.write("\nFull traceback:\n")
                            f.write(traceback.format_exc())
                            f.write("\n" + "=" * 80 + "\n")
                            f.write(f"Batch size: {len(batch)}\n")
                            f.write(f"Batch input summary (first article title): {batch[0].get('title', 'N/A') if batch else 'Empty batch'}\n")

                        logging.info(f'(RUN ID: {self.run_uuid}) - Batch {batch_num}/{total_batches}: Saved SDK error details to {error_file}')
                    except Exception as file_err:
                        logging.warning(f'(RUN ID: {self.run_uuid}) - Failed to save SDK error to file: {str(file_err)}')

                logging.warning(f'(RUN ID: {self.run_uuid}) - Skipping failed batch and continuing with remaining batches')

        successful_summaries = len(all_summaries)
        failed_batches = total_batches - (successful_summaries // self.batch_size if self.batch_size > 0 else 0)

        logging.info(f'(RUN ID: {self.run_uuid}) - Batch processing complete: {successful_summaries} total summaries from {total_batches} batches')

        if failed_batches > 0:
            logging.warning(f'(RUN ID: {self.run_uuid}) - {failed_batches} batch(es) failed during processing')

        if successful_summaries == 0:
            logging.error(f'(RUN ID: {self.run_uuid}) - ALL batches failed - no summaries generated')
            raise ValueError(f'All {total_batches} batches failed to generate summaries')

        return dumps(all_summaries, ensure_ascii=False)


class ExtractFirstParagraph(BaseGenerator):
    """Attempts to extract the first "real" paragraph from the provided AGA Journal Content"""

    def __init__(self, run_uuid: str):
        super().__init__(run_uuid)

    def get_system_prompt(self):
        return FAKE_ABSTRACT_PROMPT

    def get_response_schema(self):
        return FakeAbstract

    def prepare_content(self, user_payload):
        """Prepare content for Gemini API request."""
        logging.debug(f'(RUN ID: {self.run_uuid}) - Preparing content for abstract extraction')

        content_text = types.Part.from_text(text=str(user_payload))
        return [types.Content(role="user", parts=[content_text])]


class SubjectLineGenerator(BaseGenerator):
    """Generator for creating email subject lines."""

    def __init__(self, run_uuid: str):
        super().__init__(run_uuid)

    def get_system_prompt(self) -> str:
        """Return the subject line system prompt."""
        return SUBJECT_LINE_PROMPT

    def get_response_schema(self):
        """Return the response schema for subject line generation."""
        return GeneratedSubjectLineResp

    def prepare_content(self, user_payload):
        """Prepare content for Gemini API request."""
        gen_subj_prompt = types.Part.from_text(
            text=f"{user_payload}"
        )

        return [types.Content(role="user", parts=[gen_subj_prompt])]


class AIContentDetection(BaseGenerator):
    """Attempts to extract the first "real" paragraph from the provided AGA Journal Content"""

    def __init__(self, run_uuid: str):
        super().__init__(run_uuid)

    def get_system_prompt(self):
        return AI_DETECTION_PROMPT

    def get_response_schema(self):
        return AIDetection

    def prepare_content(self, user_payload):
        """Prepare content for Gemini API request."""
        logging.debug(f'(RUN ID: {self.run_uuid}) - Preparing content for AI content detection')

        content_text = types.Part.from_text(text=str(user_payload))
        return [types.Content(role="user", parts=[content_text])]
