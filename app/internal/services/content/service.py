from .dtypes import *
from google.cloud import bigquery, vision
import time
from common.logging.logging_config import get_logger


logger = get_logger('internal.content.services')

class F1ContentError(Exception):
    """Custom exception for F1Content operations"""
    pass


class F1ContentService:
    """Repository for F1Content/BigQuery operations"""

    def __init__(self):
        try:
            self.bq_client = bigquery.Client()
        except Exception as e:
            raise F1ContentError(f"Failed to initialize BigQuery client: {e}")

    def get_content(self, site: str, case_ids: str) -> F1ContentOutput:
        """Lookup F1 Content using supplied case IDs from BigQuery with error handling"""
        case_ids = case_ids.split(',')
        logger.info('Fetching F1 content from BigQuery',
                   site=site,
                   case_count=len(case_ids))

        # Use parameterized query to prevent SQL injection
        sql = """
            SELECT
                a.case_uuid AS case_id,
                title,
                ARRAY_AGG(DISTINCT CONCAT('https://figure1-pro-prod.imgix.net/cases/images/', filename) IGNORE NULLS) AS image_url,
                caption AS teaser,
                CONCAT(
                    CONCAT('https://app.figure1.com/case-detail/', a.case_uuid),
                    CONCAT(
                        CONCAT('?auth=ezpass&utm_source=', @site_name),
                        CONCAT('&utm_medium=widget&utm_campaign=f1_case_acquisition&utm_content=', a.case_uuid)
                    )
                ) AS cta_url

            FROM
                `pw-datahub.dwh_figure1_data.c_case` a

                JOIN `pw-datahub.dwh_figure1_data.c_content` b
                    ON a.case_uuid = b.case_uuid

                LEFT JOIN `pw-datahub.dwh_figure1_data.c_media` c
                    ON b.content_uuid = c.content_uuid

            WHERE
                a.case_uuid IN UNNEST(@case_ids)

            GROUP BY 1,2,4,5
        """

        try:
            # Configure query with parameters
            config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter('site_name', 'STRING', site),
                    bigquery.ArrayQueryParameter('case_ids', 'STRING', case_ids),
                ]
            )

            # Execute query
            start_time = time.time()
            job = self.bq_client.query_and_wait(sql, job_config=config)
            duration_ms = (time.time() - start_time) * 1000
            rows:List[F1ContentOutputBase] = [dict(row) for row in job]
            image_processor = SafeImageDetection()

            for row in rows:
                row['image_results'] = [
                    {
                        'image': image,
                        'is_safe': (is_safe := image_processor.is_image_safe(uri=image))[0],
                        'is_safe_results': is_safe[1],
                    }
                    for image in row['image_url']
                ]

            logger.info('BigQuery query completed for F1 content',
                       site=site,
                       case_count=len(case_ids),
                       rows_returned=len(rows),
                       duration_ms=round(duration_ms, 2),
                       job_id=job.job_id)

            # Check if any results were returned
            if len(rows) == 0:
                logger.warning('No F1 content found', site=site, case_ids=case_ids)
                raise F1ContentError(f'No F1 content found for case ID(s): {case_ids}')

            if not rows:
                raise F1ContentError(f'No F1 content found for case ID(s): {case_ids}')

            output:F1ContentOutput = { 'cases': rows }
            return output

        except bigquery.exceptions.BigQueryError as e:
            logger.error('BigQuery error fetching F1 content',
                        site=site,
                        case_count=len(case_ids),
                        error_code=getattr(e, 'code', None))
            raise F1ContentError(f'BigQuery error while fetching F1 content for case ID(s): {case_ids}. {e}')
        except Exception as e:
            logger.error('Unexpected error fetching F1 content',
                        site=site,
                        case_count=len(case_ids),
                        error_type=type(e).__name__)
            raise F1ContentError(f'Unexpected error while fetching F1 content for case ID(s): {case_ids}. {e}')
        finally:
            if self.bq_client:
                self.bq_client.close()


class SafeImageDetectionError(Exception):
    """Custom exception for SafeImageDetection operations"""
    pass


class SafeImageDetection:
    def __init__(self):
        self.client = vision.ImageAnnotatorClient()
        self.likelihood = vision.Likelihood._member_names_
        self.LIKELIHOOD_THRESHOLD = {
            'UNKNOWN': 0,
            'VERY_UNLIKELY': 1,
            'UNLIKELY': 2,
            'POSSIBLE': 3,
            'LIKELY': 4,
            'VERY_LIKELY': 5
        }

    def is_image_safe(self, path: str=None, uri: str=None, max_level: str='POSSIBLE') -> tuple[bool, dict]:
        """
        Checks if an image is safe to display.

        Args:
            path: Local path for an image, either path or uri is required, path takes priority
            uri: URI of an image, either path or uri is required, path takes priority
            max_level: Likelihood level, default is POSSIBLE meaning anything 'LIKELY' or higher gets flagged as unsafe

        Returns:
            Tuple of (is_safe, details_dict)

        Fields
            adult: Represents the adult content likelihood for the image. Adult content may contain elements such as nudity, pornographic images or cartoons, or sexual activities.
            spoof: The likelihood that a modification was made to the image's canonical version to make it appear funny or offensive.
            medical: Likelihood that this is a medical image.
            violence: Likelihood that this image contains violent content. Violent content may include death, serious harm, or injury to individuals or groups of individuals.
            racy: Likelihood that the request image contains racy content. Racy content may include (but is not limited to) skimpy or sheer clothing, strategically covered nudity, lewd or provocative poses, or close-ups of sensitive body areas.
        """
        try:
            if not path and not uri:
                raise SafeImageDetectionError('The "path" or "uri" argument is required.')

            image = vision.Image()

            if path:
                with open(path, 'rb') as f:
                    image.content = f.read()
            elif uri:
                image.source.image_uri = uri

            response = self.client.safe_search_detection(image=image)
            safe = response.safe_search_annotation
            results = {
                'adult': self.likelihood[safe.adult],
                'violence': self.likelihood[safe.violence],
                # 'racy': self.likelihood[safe.racy],
                # 'medical': self.likelihood[safe.medical],
            }

            threshold = self.LIKELIHOOD_THRESHOLD[max_level]
            is_safe = all(
                self.LIKELIHOOD_THRESHOLD[level] <= threshold
                for level in results.values()
            )
        except Exception as e:
            logger.warning(f'Failed to process image through Vision API: {e}')
            is_safe = False
            results = {
                'adult': 'UNKNOWN',
                'violence': 'UNKNOWN',
                # 'racy': 'UNKNOWN',
                # 'medical': 'UNKNOWN',
            }

        return is_safe, results
