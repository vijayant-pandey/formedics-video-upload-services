
from fastapi.responses import JSONResponse
from .genai import AIContentDetection, ExtractFirstParagraph, JournalSummaryGenerator, SubjectLineGenerator
from .dtypes import *
from .els_api import ELSApi
from .embeddings import EmbeddingGenerator
from json import load, loads, dumps
import uuid
import time
import os
from datetime import datetime
from common.logging.logging_config import get_logger
from google.cloud import bigquery


logger = get_logger('ai.services')

class GenSubjLineService:
    """Service for handling automation operations"""
    def generate(self, articles:List[SubjSourceBase]):
        run_uuid = uuid.uuid4()
        logger.info('Starting subject line generation',
                   run_id=str(run_uuid),
                   article_count=len(articles))

        try:
            start_time = time.time()
            gen_subj = SubjectLineGenerator(run_uuid)
            subj_lines = gen_subj.generate(articles)
            duration_ms = (time.time() - start_time) * 1000

            logger.info('Subject line generation completed',
                       run_id=str(run_uuid),
                       article_count=len(articles),
                       duration_ms=round(duration_ms, 2))

            return JSONResponse(
                status_code=200,
                content=loads(subj_lines)
            )
        except Exception as e:
            logger.error('Subject line generation failed',
                        run_id=str(run_uuid),
                        article_count=len(articles),
                        error_type=type(e).__name__)
            return JSONResponse(
                    status_code=500,
                    content=str(e)
                )


class JournaySummaryService:
    """Service for handling automation operations"""
    # def generate(self, query, save_to_db: bool = True, save_raw_data: bool = False, source_journal: str = None, source_issn: str = None, batch_size: int = 5, save_failed_to:str = 'gcs', start_date:str = None):
    def generate(self, query, save_to_db: bool = True, source_journal: str = None, source_issn: str = None, batch_size: int = 5, save_failed_to:str = 'gcs', start_date:str = None):
        valid_options = ['local', 'gcs', 'both', 'none']
        save_failed_to_lower = save_failed_to.lower() if save_failed_to else 'gcs'
        if save_failed_to_lower not in valid_options:
            logger.error(f'Invalid save_failed_to parameter: {save_failed_to}. Must be one of: {", ".join(valid_options)}')
            return JSONResponse(
                status_code=400,
                content={'error': f'Invalid save_failed_to parameter. Must be one of: {", ".join(valid_options)}'}
            )

        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                logger.error(f'Invalid start_date format: {start_date}. Must be YYYY-MM-DD')
                return JSONResponse(
                    status_code=400,
                    content={'error': 'Invalid start_date format. Must be YYYY-MM-DD (e.g., 2024-01-15)'}
                )

        logger.info('Starting Elsevier content retrieval process',
                   query=query,
                   save_to_db=save_to_db,
                #    save_raw_data=save_raw_data,
                   source_journal=source_journal,
                   source_issn=source_issn,
                   save_failed_to=save_failed_to_lower,
                   start_date=start_date)

        try:
            start_time = time.time()
            els = ELSApi(query, source_issn=source_issn, start_date=start_date)
            data = [d for d in els.data if d.get('content')]

            logger.info('Elsevier data retrieved and filtered',
                       run_id=str(els.run_uuid),
                       total_articles=len(els.data),
                       articles_with_content=len(data))

            # with open('data/raw_articles/newest/Gastroenterology_missing.json', 'r') as file:
            #     data = load(file)
            #     # print(test_data)
            #     class testcls:
            #         run_uuid = 'testrun'
            #     els = testcls()

            if not data:
                logger.warning('No articles with content found',
                             run_id=str(els.run_uuid),
                             query=query)
                return JSONResponse(
                    status_code=404,
                    content={'error': 'No articles with content found'}
                )
            else:
                # Optionally save raw data to file before summarization
                # if save_raw_data and source_journal:
                #     try:
                #         safe_journal_name = source_journal.replace(' ', '_').replace('/', '_')
                #         timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                #         filename = f"{safe_journal_name}_{timestamp}.json"
                #         filepath = os.path.join('data', 'raw_articles', filename)

                #         os.makedirs(os.path.dirname(filepath), exist_ok=True)

                #         with open(filepath, 'w', encoding='utf-8') as f:
                #             f.write(dumps(data, indent=2, ensure_ascii=False))

                #         logger.info('Raw data saved to file',
                #                    run_id=str(els.run_uuid),
                #                    filepath=filepath,
                #                    article_count=len(data))

                #         return JSONResponse(
                #             status_code=200,
                #             content= { 'msg': 'file saved' }
                #         )
                #     except Exception as file_error:
                #         logger.error('Failed to save raw data to file, continuing with summarization',
                #                     run_id=str(els.run_uuid),
                #                     error_type=type(file_error).__name__,
                #                     error=str(file_error))

                logger.info('Starting summary generation',
                           run_id=str(els.run_uuid),
                           article_count=len(data),
                           batch_size=batch_size,
                           save_failed_to=save_failed_to_lower)

                gen_summaries = JournalSummaryGenerator(els.run_uuid, batch_size=batch_size, save_failed_to=save_failed_to_lower)

                for idx, d in enumerate(data, 1):
                    if idx % 25 == 0:
                        logger.info(f'(RUN ID: {els.run_uuid}) - Abstract generation progress: {idx}/{len(data)} articles processed')

                    if d['abstract'] == '':
                        gen_abstract = ExtractFirstParagraph(els.run_uuid)
                        d['abstract'] = loads(gen_abstract.generate(d['content'])).get('abstract')

                logger.info(f'(RUN ID: {els.run_uuid}) - Abstract generation completed')

                summaries = gen_summaries.generate(data)

                try:
                    summaries_list_raw = loads(summaries)
                except Exception as json_err:
                    if '][' in summaries:
                        logger.warning(f'(RUN ID: {els.run_uuid}) - Detected duplicate JSON arrays, extracting first array only')
                        first_array_end = summaries.find('][')
                        if first_array_end > 0:
                            summaries = summaries[:first_array_end + 1]  # Keep first array including closing ]
                            summaries_list_raw = loads(summaries)
                        else:
                            raise json_err
                    else:
                        raise json_err

                logger.debug(f'(RUN ID: {els.run_uuid}) - summaries_list_raw type: {type(summaries_list_raw)}, length: {len(summaries_list_raw) if isinstance(summaries_list_raw, list) else "N/A"}')

                if not isinstance(summaries_list_raw, list):
                    logger.error(f'(RUN ID: {els.run_uuid}) - Expected list from summaries, got {type(summaries_list_raw)}')
                    raise ValueError(f'Expected list from summaries, got {type(summaries_list_raw)}')

                summaries_list = []
                for idx, d in enumerate(summaries_list_raw, 1):
                    if idx % 25 == 0:
                        logger.info(f'(RUN ID: {els.run_uuid}) - Summary embeddings generation progress: {idx}/{len(summaries_list_raw)} articles processed')

                    if not isinstance(d, dict):
                        logger.warning(f'(RUN ID: {els.run_uuid}) - Skipping non-dict item at index {idx}: type={type(d)}, value={str(d)[:100]}')
                        continue

                    d['embedding_text'] = f"Title: {d.get('headline')}, Excerpt: {d.get('excerpt')}, Summary: {d.get('summary')}, Key Takeaways: {' '.join(d.get('key_takeaways', []))}, Study Objective: {' '.join(d.get('study_objective', []))}, Methods: {' '.join(d.get('methods', []))}, Results: {' '.join(d.get('results', []))}, Clinical {' '.join(d.get('clinical_relevance', []))}, MeSH Codes: {' '.join(d.get('meshcodes', []))}, ICD10 Codes: {' '.join(d.get('icd10_codes', []))}, Meta Description: {d.get('meta_description')}, Tags: {' '.join(d.get('tags', []))}"
                    summaries_list.append(d)

                logger.info(f'(RUN ID: {els.run_uuid}) - Filtered summaries: {len(summaries_list)} valid items out of {len(summaries_list_raw)} total')

                if save_to_db:
                    try:
                        logger.info('Saving summaries to BigQuery with embeddings',
                                   run_id=str(els.run_uuid))
                        embedding_gen = EmbeddingGenerator()
                        rows_inserted = embedding_gen.save_embeddings_to_bigquery(
                            summaries_list,
                            source_journal=source_journal,
                            source_issn=source_issn
                        )

                        logger.info('Summaries saved to BigQuery',
                                   run_id=str(els.run_uuid),
                                   rows_inserted=rows_inserted)
                    except Exception as db_error:
                        logger.error('Failed to save to BigQuery, continuing with response',
                                    run_id=str(els.run_uuid),
                                    error_type=type(db_error).__name__,
                                    error=str(db_error))

                duration_ms = (time.time() - start_time) * 1000

                logger.info('Summary generation completed',
                           run_id=str(els.run_uuid),
                           article_count=len(data),
                           duration_ms=round(duration_ms, 2))

                return JSONResponse(
                    status_code=200,
                    content=summaries_list
                )
        except Exception as e:
            logger.error('Elsevier summary generation failed',
                        query=query,
                        error_type=type(e).__name__)
            return JSONResponse(
                    status_code=500,
                    content=str(e)
                )

class AGAVectorSearchService:
    def search(self, issn:str, search_str:str):
        embedding_gen = EmbeddingGenerator()
        results = embedding_gen.search_similar(issn, search_str)

        return results


class DetectAIContent:
    def generate(self, articles:DetectionPosts):
        run_uuid = uuid.uuid4()
        logger.info('Starting AI content detection',
                   run_id=str(run_uuid),
                   article_count=len(articles))

        try:
            start_time = time.time()
            detect_ai = AIContentDetection(run_uuid)
            subj_lines = detect_ai.generate(articles['post_content'])
            duration_ms = (time.time() - start_time) * 1000

            logger.info('AI detection completed',
                       run_id=str(run_uuid),
                       article_count=len(articles),
                       duration_ms=round(duration_ms, 2))

            return JSONResponse(
                status_code=200,
                content=loads(subj_lines)
            )
        except Exception as e:
            logger.error('AI detection failed',
                        run_id=str(run_uuid),
                        article_count=len(articles),
                        error_type=type(e).__name__)
            return JSONResponse(
                    status_code=500,
                    content=str(e)
                )
