import requests
import base64
import os
import time
from json import dumps, loads
from typing import List, Dict
from .dtypes import *
from datetime import datetime, timedelta
from google.cloud import bigquery
from fastapi.responses import JSONResponse
from urllib.error import HTTPError
from common.logging.logging_config import get_logger
import pandas as pd


logger = get_logger('iterable.wp_api')


class WordPressAuthManager:
    """Handles WordPress authentication and credential management"""

    def __init__(self, site_nm: str):
        self.site_nm = site_nm
        self._setup_credentials()

    def _setup_credentials(self):
        """Setup authentication credentials for WordPress API"""
        _PW = loads(os.environ['WP_APP_PW'])[self.site_nm]
        _CREDS = f'{os.environ["WP_APP_USER"]}:{_PW}'
        self._encoded_creds = base64.b64encode(_CREDS.encode()).decode('utf-8')

    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests"""
        return {
            'Authorization': f'Basic {self._encoded_creds}',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
        }


class WordPressURLBuilder:
    """Handles URL construction for different WordPress sites"""

    DFP_ZONE_URLS = {
        'physiciansweekly': '/pw/v1/posts-by-dfp-zone',
        'bloodcancerstoday': '/bct/v1/posts-by-dfp-zone',
        'cancernursingtoday': '/cnt/v1/posts-by-dfp-zone',
        'cardiocaretoday': '/cct/v1/posts-by-dfp-zone',
        'docwirenews': '/dwnews/v1/posts-by-dfp-zone',
        'prodgionc': '/gionc/v1/posts-by-dfp-zone',
        'guoncologynow': '/guonc/v1/posts-by-dfp-zone',
        'lungcancerstoday': '/lucst/v1/posts-by-dfp-zone',
        'urbanhealthtoday': '/uht/v1/posts-by-dfp-zone'
    }


    def __init__(self, site_nm: str):
        self.site_nm = site_nm
        self.base_url = self._build_base_url()

    def _build_base_url(self) -> str:
        """Build base URL for WordPress API based on site"""
        if self.site_nm == 'prodgionc':
            return 'http://prodgionc.wpenginepowered.com/wp-json'
        return f'https://cms.{self.site_nm}.com/wp-json'

    def get_categories_url(self) -> str:
        """Get URL for categories endpoint"""
        return f'{self.base_url}/wp/v2/categories'

    def get_posts_url(self) -> str:
        """Get URL for posts endpoint"""
        return f'{self.base_url}/wp/v2/posts'

    def get_wallboard_url(self) -> str:
        """Get URL for wallboard endpoint"""
        return f'{self.base_url}/pw/v1/wallboard'

    def get_dfp_zone_url(self) -> str:
        """Get URL for DFP zone posts"""
        return self._build_base_url() + self.DFP_ZONE_URLS.get(self.site_nm)


class WordPressHTTPClient:
    """Handles HTTP communication with WordPress API"""

    def __init__(self, auth_manager: WordPressAuthManager):
        self.session = requests.Session()
        self.headers = auth_manager.get_headers()

    def send_request(self, method='GET', endpoint=None, data=None, headers=None, parameters=None):
        """Send HTTP request to WordPress API with detailed logging"""
        logger.info('WordPress API request',
                   method=method,
                   endpoint=endpoint,
                   parameters=parameters)

        try:
            headers = headers or self.headers
            start_time = time.time()

            response = self.session.request(
                method=method,
                url=endpoint,
                headers=headers,
                json=data,
                params=parameters,
                timeout=30
            )

            duration_ms = (time.time() - start_time) * 1000

            logger.info('WordPress API response',
                       method=method,
                       endpoint=endpoint,
                       status_code=response.status_code,
                       response_time_ms=round(duration_ms, 2),
                       response_size_bytes=len(response.content))

            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            logger.error('WordPress API timeout',
                        method=method,
                        endpoint=endpoint,
                        timeout_seconds=30)
            raise

        except requests.exceptions.HTTPError as e:
            logger.error('WordPress API HTTP error',
                        method=method,
                        endpoint=endpoint,
                        status_code=e.response.status_code,
                        response_body=e.response.text[:500])
            raise

        except requests.exceptions.RequestException:
            logger.error('WordPress API request failed',
                        method=method,
                        endpoint=endpoint)
            raise

    def close(self):
        """Close HTTP session"""
        self.session.close()


class CategoryRepository:
    """Repository for WordPress category operations"""

    def __init__(self, http_client: WordPressHTTPClient, url_builder: WordPressURLBuilder):
        self.http_client = http_client
        self.url_builder = url_builder

    def get_all_categories(self, cats: list[str] = [], page: int = 1) -> list[str]:
        """Fetch all categories from WordPress API recursively"""
        querystring = {
            'per_page': 100,
            'page': page
        }
        cats_metadata = self.http_client.send_request(
            endpoint=self.url_builder.get_categories_url(),
            parameters=querystring
        )
        categories = cats + [d['slug'] for d in cats_metadata]

        if len(cats_metadata) > 0:
            return self.get_all_categories(categories, page=page+1)
        else:
            return sorted(categories)

    def get_category_ids(self, cats: list[str], excludes: list[str]) -> List[WPCategories]:
        """Get category IDs for given category slugs"""
        all_cats = cats + excludes
        querystring = {
            'slug': f'[{",".join(all_cats)}]'
        }
        cats_resp = self.http_client.send_request(
            endpoint=self.url_builder.get_categories_url(),
            parameters=querystring
        )
        return [{'id': d['id'], 'slug': d['slug']} for d in cats_resp]

    def get_category_text(self, cats: list[int]) -> List[WPCategories]:
        """Get category text for given category IDs"""
        querystring = {
            'include': ','.join(map(str, cats))
        }
        cats_metadata = self.http_client.send_request(
            endpoint=self.url_builder.get_categories_url(),
            parameters=querystring
        )
        return [{'id': d['id'], 'slug': d['slug']} for d in cats_metadata]


class MediaRepository:
    """Repository for WordPress media operations"""

    def __init__(self, http_client: WordPressHTTPClient):
        self.http_client = http_client

    def get_featured_images(self, target_url: str) -> dict:
        """Get featured images from media URL"""
        resp = self.http_client.send_request(endpoint=target_url)
        return resp['media_details']['sizes']


class PostProcessor:
    """Processes and transforms post data"""

    def __init__(self, category_repo: CategoryRepository = None, media_repo: MediaRepository = None):
        self.category_repo = category_repo
        self.media_repo = media_repo

    def process_post_categories(self, post: dict) -> list[str]:
        """Extract and process category names from post"""
        if 'class_list' in post:
            return [d.replace('category-', '') for d in post['class_list'] if d.startswith('category-')]
        else:
            categories = self.category_repo.get_category_text(post['categories'])
            return [x['slug'] for x in categories]

    def process_featured_images(self, post: dict):
        """Add featured images to post if available"""
        if 'wp:featuredmedia' in post['_links']:
            post['images'] = self.media_repo.get_featured_images(
                post['_links']['wp:featuredmedia'][0]['href']
            )

    def is_featured_post(self, post: dict, featured_cat: str) -> bool:
        """Check if post is featured based on category"""
        return featured_cat in post.get('category_names', [])

    def is_within_date_range(self, post: dict, featured_in_last: int) -> bool:
        """Check if post is within the specified date range"""
        if not featured_in_last:
            return True

        today = datetime.now().date()
        post_date = datetime.strptime(post['date'], '%Y-%m-%dT%H:%M:%S').date()
        return post_date >= today - timedelta(days=featured_in_last)


class PostRepository:
    """Repository for WordPress post operations"""

    def __init__(self, http_client: WordPressHTTPClient, url_builder: WordPressURLBuilder,
                post_processor: PostProcessor):
        self.http_client = http_client
        self.url_builder = url_builder
        self.post_processor = post_processor
        self.primary_cat = None

    def get_posts(self, site: str, category: int, exclude_cats: List[int] = None,
                featured_in_last: int = None, limit: int=20) -> List[Post]:
        """Get posts with category filtering and featured post handling"""
        querystring = {
            'categories': category,
            'per_page': limit
        }

        if exclude_cats and len(exclude_cats) > 0:
            querystring['categories_exclude'] = f'{",".join(map(str, exclude_cats))}'

        posts = self.http_client.send_request(
            endpoint=self.url_builder.get_posts_url(),
            parameters=querystring
        )

        if len(posts) == 0:
            raise HTTPError(
                code=404,
                content={'error': 'No content was found.'}
            )

        processed_posts = self._process_posts(posts, featured_in_last)
        return processed_posts[0:10]

    def _process_posts(self, posts: list, featured_in_last: int) -> list:
        """Process posts with category names, images, and featured handling"""
        featured_items = []
        featured_cat = f'{self.primary_cat}-featured'

        for i, post in enumerate(posts):
            post['category_names'] = self.post_processor.process_post_categories(post)
            post['specialty'] = self.primary_cat

            self.post_processor.process_featured_images(post)

            if not self.post_processor.is_within_date_range(post, featured_in_last):
                continue

            if self.post_processor.is_featured_post(post, featured_cat):
                featured_items.append({'index': i, 'item': post})

        return self._handle_featured_posts(posts, featured_items)

    def _handle_featured_posts(self, posts: list, featured_items: list) -> list:
        """Handle featured post sorting and positioning"""
        if not featured_items:
            return posts

        for feat in featured_items:
            posts = [obj for obj in posts if obj['title'] != feat['item']['title']]

        sorted_features = sorted(
            featured_items,
            key=lambda feat: datetime.strptime(feat['item']['date'], '%Y-%m-%dT%H:%M:%S'),
            reverse=True
        )
        feats = [d['item'] for d in sorted_features]

        return feats + posts

    def get_posts_by_dfp_zone(self, site: str, dfp_zone: int) -> List[SponsoredPosts]:
        """Get posts filtered by DFP zone"""
        querystring = {'dfp_zone': dfp_zone}
        endpoint = self.url_builder.get_dfp_zone_url()
        posts = self.http_client.send_request(endpoint=endpoint, parameters=querystring)
        posts = posts['posts']
        posts = sorted(posts, key=lambda post: post['date'], reverse=True)
        return self._transform_sponsored_posts(posts)

    def _transform_sponsored_posts(self, posts: list) -> List[SponsoredPosts]:
        """Transform raw sponsored posts to structured format"""
        out = [{
            'url': d['link'],
            'title': d['title']['rendered'],
            'post_content': d['acf']['post_content'],
            'post_excerpt': d['acf']['post_excerpt'],
            'date': d['date'],
            'slug': d['slug'],
            'modified': d['modified'],
            'featured_image': d['featured_image'],
            'is_video': d['acf']['is_video'],
            'email_subject_line': d['email_subject_line'] if 'email_subject_line' in d else None,
            'email_preheader': d['email_preheader'] if 'email_preheader' in d else None,
        } for d in posts if d['type'] == 'post']

        if not out:
            raise Exception('No content found')

        page = [d['link'] for d in posts if d['type'] == 'page' or d['type'] == 'conferences']

        if page and len(page) == 1:
            out.insert(0,page[0])
        elif len(page) == 0:
            raise Exception('No collection URL found')
        else:
            raise Exception('Multiple collection URLs found')

        return out[0:10]


class WallboardRepository:
    """Repository for wallboard-specific operations"""

    def __init__(self, http_client: WordPressHTTPClient, url_builder: WordPressURLBuilder):
        self.http_client = http_client
        self.url_builder = url_builder

    def get_wallboard_data(self, category_slug_id: int) -> JSONResponse:
        """Get wallboard data and transform for specific format"""
        querystring = {'dfp_zone': category_slug_id}

        resp_json = self.http_client.send_request(
            endpoint=self.url_builder.get_wallboard_url(),
            parameters=querystring
        )

        filtered_data = self._transform_wallboard_data(resp_json, category_slug_id)

        return JSONResponse(
            status_code=200,
            content={'items': filtered_data}
        )

    def _transform_wallboard_data(self, resp_json: dict, category_slug_id: int) -> list:
        """Transform wallboard response data"""
        filtered_data = resp_json['posts'] if 'posts' in resp_json else []

        for i, d in enumerate(filtered_data):
            if i == 1:
                d['content:boosterPdfImage'] = resp_json.get('pdf_img')
                d['content:boosterPdfFile'] = resp_json.get('pdf_link')

            d['title'] = d['post_title']
            d['link'] = self._build_wallboard_link(d)
            d['content:postId'] = d['ID']
            d['content:packageId'] = category_slug_id

        return filtered_data

    def _build_wallboard_link(self, post_data: dict) -> str:
        """Build appropriate link based on post type"""
        if 'podcast' in post_data['post_type']:
            return f'https://www.physiciansweekly.com/podcast/{post_data["slug"]}'
        else:
            return f'https://www.physiciansweekly.com/post/{post_data["slug"]}'


class BoostrRepositoryError(Exception):
    """Custom exception for BoostrRepository operations"""
    pass


class BoostrRepository:
    """Repository for Boostr/BigQuery operations"""

    def __init__(self):
        try:
            self.bq_client = bigquery.Client()
        except Exception as e:
            raise BoostrRepositoryError(f"Failed to initialize BigQuery client: {e}")

    def get_package_id(self, boostr_line_item_id: int) -> BoostrInfo:
        """Lookup Boostr package ID from BigQuery with error handling"""
        logger.info('Querying BigQuery for package ID', line_item_id=boostr_line_item_id)

        # Validate input
        if not isinstance(boostr_line_item_id, int) or boostr_line_item_id <= 0:
            logger.warning('Invalid line item ID provided',
                          line_item_id=boostr_line_item_id,
                          line_item_type=type(boostr_line_item_id).__name__)
            raise BoostrRepositoryError(f"Invalid line item ID: {boostr_line_item_id}. Must be a positive integer.")

        # Use parameterized query to prevent SQL injection
        sql = """
            SELECT
                package_id AS dfp_zone,
                product_id,
                product_full_name AS product_full_name,
                custom_fields_site AS site,
                @line_item_id AS line_item_id

            FROM
                `pw-datahub.dwh_physweekly_data.boostr_io_line_items`

            WHERE
                id = @line_item_id

            GROUP BY 1,2,3,4
        """

        try:
            # Configure query with parameters
            config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter('line_item_id', 'INT64', boostr_line_item_id)
                ]
            )

            # Execute query
            start_time = time.time()
            job = self.bq_client.query_and_wait(sql, job_config=config)
            duration_ms = (time.time() - start_time) * 1000
            rows = [dict(row) for row in job]

            logger.info('BigQuery query completed',
                       line_item_id=boostr_line_item_id,
                       duration_ms=round(duration_ms, 2),
                       rows_returned=len(rows),
                       job_id=job.job_id)

            # Check if any results were returned
            if len(rows) == 0:
                logger.warning('No package found in BigQuery', line_item_id=boostr_line_item_id)
                raise BoostrRepositoryError(f'No package found for line item ID: {boostr_line_item_id}')

            if not rows:
                raise BoostrRepositoryError(f'No valid data found for line item ID: {boostr_line_item_id}')

            # Validate required fields are present
            record = rows[0]
            required_fields = ['dfp_zone', 'product_id', 'product_full_name', 'site']
            missing_fields = [field for field in required_fields if record.get(field) is None]

            if 'site' in missing_fields:
                logger.warning('Site not specified in BigQuery result', line_item_id=boostr_line_item_id)
                raise BoostrRepositoryError(f'Site is not specified for line item ID: {boostr_line_item_id}')

            if missing_fields:
                logger.warning('Missing required fields in BigQuery result',
                             line_item_id=boostr_line_item_id,
                             missing_fields=missing_fields)
                raise BoostrRepositoryError(f'Missing required fields: {missing_fields} for line item ID: {boostr_line_item_id}')

            return record

        except bigquery.exceptions.BigQueryError as e:
            logger.error('BigQuery error',
                        line_item_id=boostr_line_item_id,
                        error_code=getattr(e, 'code', None))
            raise BoostrRepositoryError(f'BigQuery error while fetching package ID: {e}')
        except Exception as e:
            logger.error('Unexpected error querying BigQuery',
                        line_item_id=boostr_line_item_id,
                        error_type=type(e).__name__)
            raise BoostrRepositoryError(f'Unexpected error while fetching package ID: {e}')
        finally:
            if self.bq_client:
                self.bq_client.close()


class WordPressAPI:
    """Main WordPress API facade that coordinates all operations"""

    def __init__(self, site_nm: str):
        self.site_nm = site_nm
        self.auth_manager = WordPressAuthManager(site_nm)
        self.url_builder = WordPressURLBuilder(site_nm)
        self.http_client = WordPressHTTPClient(self.auth_manager)

        self.category_repo = CategoryRepository(self.http_client, self.url_builder)
        self.media_repo = MediaRepository(self.http_client)
        self.post_processor = PostProcessor(self.category_repo, self.media_repo)
        self.post_repo = PostRepository(self.http_client, self.url_builder, self.post_processor)
        self.wallboard_repo = WallboardRepository(self.http_client, self.url_builder)
        self.boostr_repo = BoostrRepository()

        self.primary_cat = None

    def close_conn(self):
        """Close all connections"""
        self.http_client.close()

    def get_categories(self, cats: list[str] = [], page: int = 1) -> list[str]:
        """Get all categories"""
        return self.category_repo.get_all_categories(cats, page)

    def get_category_ids(self, cats: list[str] = None, excludes: list[str] = None) -> List[WPCategories]:
        """Get category IDs"""
        if cats:
            self.primary_cat = cats[0]
            self.post_repo.primary_cat = self.primary_cat
        return self.category_repo.get_category_ids(cats, excludes)

    def get_category_text(self, cats: list[int]) -> List[WPCategories]:
        """Get category text"""
        return self.category_repo.get_category_text(cats)

    def get_posts(self, category: int, exclude_cats: List[int] = None,
                featured_in_last: int = None) -> List[Post]:
        """Get posts with filtering"""
        return self.post_repo.get_posts(self.site_nm, category, exclude_cats, featured_in_last)

    def get_posts_by_dfp_zone(self, dfp_zone: int) -> List[SponsoredPosts]:
        """Get posts by DFP zone"""
        return self.post_repo.get_posts_by_dfp_zone(self.site_nm, dfp_zone)

    def get_wallboard_data(self, category_slug_id: int) -> JSONResponse:
        """Get wallboard data"""
        return self.wallboard_repo.get_wallboard_data(category_slug_id)

    # def get_package_id(self, boostr_line_item_id: int) -> BoostrInfo:
    #     """Get package ID from Boostr"""
    #     return self.boostr_repo.get_package_id(boostr_line_item_id)



class BQContentError(Exception):
    """Custom exception for BQContent operations"""
    pass


class BQContent():
    def __init__(self, site: str, category: str, exclude_cats: List[str] = None,
            featured_in_last: int = None, limit: int = 10):
        self.site = site
        self.category = category
        self.exclude_cats = exclude_cats
        self.featured_in_last = featured_in_last
        self.limit = limit
        self.boostr_repo = BoostrRepository()

        try:
            self.bq_client = bigquery.Client()
        except Exception as e:
            raise BQContentError(f"Failed to initialize BigQuery client: {e}")

    def get_posts(self): # add output type
        logger.info('Querying BigQuery for Wordpress posts', category=self.category)
        datasets = {
            'cardiocaretoday': 'wp_cardiocaretoda',
            'physiciansweekly': 'wp_physiciansweek',
            'bloodcancerstoday': 'wp_prodbctoday',
            'docwirenews': 'wp_proddwnews',
            'gioncologynow': 'wp_prodgionc',
            'guoncologynow': 'wp_prodguonc',
            'lungcancerstoday': 'wp_prodlctoday',
            'urbanhealthtoday': 'wp_produht',
            'cancernursingtoday': 'wp_cntprod'
        }
        dataset = datasets[self.site]
        sql = f"""
            WITH post_ids AS (
                SELECT
                    t_rel.object_id AS post_id

                FROM
                    `formedics-prod.{dataset}.wp_term_relationships` AS t_rel

                    JOIN `formedics-prod.{dataset}.wp_term_taxonomy` AS t_tax
                        ON t_rel.term_taxonomy_id = t_tax.term_taxonomy_id

                    JOIN `formedics-prod.{dataset}.wp_terms` AS terms
                        ON t_tax.term_id = terms.term_id

                WHERE
                    t_tax.taxonomy = 'category'
                    AND terms.slug = @category
            ),

            pre_data AS (
                SELECT
                    a.ID AS id,
                    a.post_date AS `date`,
                    a.post_date_gmt AS date_gmt,
                    STRUCT(a.guid AS rendered) AS guid,
                    a.post_modified AS modified,
                    a.post_modified_gmt AS modified_gmt,
                    a.post_name AS slug,
                    a.post_status AS status,
                    a.post_type AS type,
                    STRUCT(a.post_title AS rendered) AS title,
                    STRUCT('' AS rendered, FALSE AS protected) AS content,
                    STRUCT('' AS rendered, FALSE AS protected) AS excerpt,
                    SAFE_CAST(a.post_author AS INT64) AS author,
                    MAX(IF(b.meta_key = '_thumbnail_id', SAFE_CAST(b.meta_value AS INT64), NULL)) AS featured_media,
                    a.comment_status,
                    a.ping_status,
                    FALSE AS sticky,  -- hardcoding for now, should be in wp_options table
                    MAX(IF(b.meta_key = '_wp_page_template', b.meta_value, "")) AS template,
                    'standard' AS format,  -- hardcoding for now
                    STRUCT(FALSE AS _acf_changed, '' AS footnotes) AS meta,  -- hardcoding for now
                    ARRAY_AGG(DISTINCT(SAFE_CAST(IF(d.taxonomy = 'category', d.term_id, NULL) AS INT64)) IGNORE NULLS) AS categories,
                    ARRAY_AGG(DISTINCT(SAFE_CAST(IF(d.taxonomy = 'post_tag', d.term_id, NULL) AS INT64)) IGNORE NULLS) AS tags,
                    [
                        CONCAT('post-', a.ID), a.post_type, CONCAT('type-', a.post_type),
                        CONCAT('status-', a.post_status), 'format-standard',  -- hardcoded
                        'has-post-thumbnail',  -- hardcoded
                        'hentry'  -- hardcoded
                    ] AS class_list1,
                    ARRAY_AGG(DISTINCT(IF(d.taxonomy = 'category', CONCAT('category-', e.slug), NULL)) IGNORE NULLS) AS class_list2,
                    ARRAY_AGG(DISTINCT(IF(d.taxonomy = 'post_tag', CONCAT('tag-', e.slug), NULL)) IGNORE NULLS) AS class_list3,
                    STRUCT(
                        LTRIM(
                            MAX(
                            IF(
                                b.meta_key = 'post_content',
                                REGEXP_REPLACE(
                                b.meta_value,
                                r'\[zeus_brightcove[^]]*]',
                                ''
                                ),
                                NULL
                            )
                            )
                        ) AS post_content,
                        MAX(IF(b.meta_key = 'post_excerpt', b.meta_value, NULL)) AS post_excerpt,
                        REGEXP_EXTRACT_ALL(MAX(IF(b.meta_key = 'custom_author', b.meta_value, '')), r'"(\d+)"') AS custom_author,
                        MAX(IF(b.meta_key = 'is_video', SAFE_CAST(SAFE_CAST(b.meta_value AS INT64) AS BOOL), NULL)) AS is_video,
                        MAX(IF(b.meta_key = 'youtube_url', b.meta_value, '')) AS youtube_url,
                        MAX(IF(b.meta_key = 'vimeo_url', b.meta_value, '')) AS vimeo_url,
                        MAX(IF(b.meta_key = 'mongodb_search', b.meta_value, '')) AS mongodb_search,
                        MAX(IF(b.meta_key = 'mongodb_id', b.meta_value, '')) AS mongodb_id,
                        MAX(IF(b.meta_key = 'mongo_return_message', b.meta_value, '')) AS mongo_return_message
                    ) AS acf,
                    MAX(IF(b.meta_key = 'email_subject_line', b.meta_value, NULL)) AS email_subject_line,
                    MAX(IF(b.meta_key = 'email_preheader', b.meta_value, NULL)) AS email_preheader,
                    ARRAY_AGG(DISTINCT(IF(d.taxonomy = 'category', e.slug, NULL)) IGNORE NULLS) AS category_names

                FROM
                    `formedics-prod.{dataset}.wp_posts` AS a

                    INNER JOIN post_ids AS h
                        ON a.ID = h.post_id

                    LEFT JOIN `formedics-prod.{dataset}.wp_postmeta` AS b
                        ON a.ID = b.post_id

                    LEFT JOIN `formedics-prod.{dataset}.wp_term_relationships` AS c
                        ON a.ID = c.object_id

                    LEFT JOIN `formedics-prod.{dataset}.wp_term_taxonomy` AS d
                        ON c.term_taxonomy_id = d.term_taxonomy_id

                    LEFT JOIN `formedics-prod.{dataset}.wp_terms` AS e
                        ON d.term_id = e.term_id

                WHERE
                    post_type = 'post'

                GROUP BY
                    a.ID, a.post_date, a.post_date_gmt, a.guid, a.post_modified,
                    a.post_modified_gmt, a.post_name, a.post_status, a.post_type,
                    a.post_title, a.post_author, a.comment_status, a.ping_status
            )

            SELECT
                SAFE_CAST(p.id AS INT64) AS id,
                p.date,
                p.date_gmt,
                p.guid,
                p.modified,
                p.modified_gmt,
                p.slug,
                p.status,
                p.type,
                CONCAT('https://www.', @site, '.com/', p.type,'/', p.slug) AS link,
                p.title,
                p.content,
                p.excerpt,
                p.author,
                p.featured_media,
                p.comment_status,
                p.ping_status,
                p.sticky,
                p.template,
                p.format,
                p.meta,
                p.categories,
                p.tags,
                ARRAY_CONCAT(
                    IFNULL(p.class_list1, []),
                    IFNULL(p.class_list2, []),
                    IFNULL(p.class_list3, []))
                    AS class_list,
                p.acf,
                IF(@site = 'physiciansweekly', CONCAT('https://cdn.', @site, '.com/wp-content/uploads/',img_url.meta_value), feat_img.guid) AS featured_image,
                CASE
                    WHEN (p.email_subject_line = '' OR p.email_subject_line IS NULL)
                    THEN p.title.rendered
                    ELSE p.email_subject_line
                    END AS email_subject_line,
                CASE
                    WHEN (p.email_preheader = '' OR p.email_preheader IS NULL)
                    THEN p.acf.post_excerpt
                    ELSE p.email_preheader
                    END AS email_preheader,
                p.category_names,
                @category AS specialty

            FROM
                pre_data AS p

                LEFT JOIN `formedics-prod.{dataset}.wp_posts` AS feat_img
                    ON p.featured_media = feat_img.ID AND feat_img.post_type = 'attachment'

                LEFT JOIN `formedics-prod.{dataset}.wp_postmeta` AS img_url
                    ON feat_img.ID = img_url.post_id
                    AND img_url.meta_key = '_wp_attached_file'

            ORDER BY p.date DESC
            LIMIT @limit;
        """

        try:
            config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter('site', 'STRING', self.site),
                    bigquery.ScalarQueryParameter('category', 'STRING', self.category),
                    bigquery.ScalarQueryParameter('limit', 'INT64', self.limit)
                ]
            )

            start_time = time.time()
            job = self.bq_client.query(sql, job_config=config)
            results = job.result()
            df = results.to_dataframe()
            rows = df.to_json(orient='records', date_format='iso')
            duration_ms = (time.time() - start_time) * 1000

            logger.info('BigQuery query completed',
                       duration_ms=round(duration_ms, 2),
                       rows_returned=len(rows),
                       bytes_processed=job.total_bytes_processed,
                       job_id=job.job_id)

            if len(rows) == 0:
                logger.warning('No posts found in BigQuery', category=self.category)
                raise BQContentError(f'No posts found for category: {self.category}')

            if not rows:
                raise BQContentError(f'No posts found for category: {self.category}')

            return self._process_posts(loads(rows))

        except bigquery.exceptions.BigQueryError as e:
            logger.error('BigQuery error',
                        category=self.category,
                        error_code=getattr(e, 'code', None))
            raise BQContentError(f'BigQuery error while retrieving posts for category {self.category}: {e}')
        except Exception as e:
            logger.error('Unexpected error querying BigQuery',
                        category=self.category,
                        error_type=type(e).__name__)
            raise BQContentError(f'BigQuery error while retrieving posts for category {self.category}: {e}')
        finally:
            if self.bq_client:
                self.bq_client.close()

    def _is_featured_post(self, post: dict, featured_cat: str) -> bool:
        """Check if post is featured based on category"""
        return featured_cat in post.get('category_names', [])

    def _is_within_date_range(self, post: dict) -> bool:
        """Check if post is within the specified date range"""
        if not self.featured_in_last:
            return True

        today = datetime.now().date()
        post_date = datetime.strptime(post['date'], '%Y-%m-%dT%H:%M:%S.000').date()

        return post_date >= today - timedelta(days=self.featured_in_last)

    def _handle_featured_posts(self, posts: list, featured_items: list) -> list:
        """Handle featured post sorting and positioning"""
        if not featured_items:
            return posts

        for feat in featured_items:
            posts = [obj for obj in posts if obj['title'] != feat['item']['title']]

        sorted_features = sorted(
            featured_items,
            key=lambda feat: datetime.strptime(feat['item']['date'], '%Y-%m-%dT%H:%M:%S.000'),
            reverse=True
        )
        feats = [d['item'] for d in sorted_features]

        return feats + posts

    def _process_posts(self, posts: list) -> list:
        """Process posts with category names, images, and featured handling"""
        featured_items = []
        featured_cat = f'{self.category}-featured'

        for i, post in enumerate(posts):
            if not self._is_within_date_range(post):
                continue

            if self._is_featured_post(post, featured_cat):
                featured_items.append({'index': i, 'item': post})

        return self._handle_featured_posts(posts, featured_items)


class BQSponsoredContent:
    def __init__(self, site: str, dfp_zone: str):
        self.site = site
        self.dfp_zone = dfp_zone

        try:
            self.bq_client = bigquery.Client()
        except Exception as e:
            raise BQContentError(f"Failed to initialize BigQuery client: {e}")

    def get_sponsored_posts(self) -> List[SponsoredPosts]:
        """Get posts filtered by DFP zone"""
        datasets = {
            'cardiocaretoday': 'wp_cardiocaretoda',
            'physiciansweekly': 'wp_physiciansweek',
            'bloodcancerstoday': 'wp_prodbctoday',
            'docwirenews': 'wp_proddwnews',
            'gioncologynow': 'wp_prodgionc',
            'guoncologynow': 'wp_prodguonc',
            'lungcancerstoday': 'wp_prodlctoday',
            'urbanhealthtoday': 'wp_produht',
            'cancernursingtoday': ''
        }
        dataset = datasets[self.site]
        query = f"""WITH distinct_posts AS (
            SELECT
                DISTINCT post_id

            FROM
                `formedics-prod.{dataset}.wp_postmeta`

            WHERE
                meta_key = 'dfp_zone'
                AND meta_value = @dfp_zone
        ),

        pre_data AS (
            SELECT
                a.ID AS id,
                a.post_date AS `date`,
                a.post_modified AS modified,
                a.post_name AS slug,
                a.post_type AS type,
                a.post_title AS title,
                MAX(IF(b.meta_key = '_thumbnail_id', SAFE_CAST(b.meta_value AS INT64), NULL)) AS featured_media,
                MAX(IF(b.meta_key = 'post_content', b.meta_value, NULL)) AS post_content,
                MAX(IF(b.meta_key = 'post_excerpt', b.meta_value, NULL)) AS post_excerpt,
                MAX(IF(b.meta_key = 'is_video', SAFE_CAST(SAFE_CAST(b.meta_value AS INT64) AS BOOL), NULL)) AS is_video,
                MAX(IF(b.meta_key = 'email_subject_line', b.meta_value, NULL)) AS email_subject_line,
                MAX(IF(b.meta_key = 'email_preheader', b.meta_value, NULL)) AS email_preheader

            FROM
                `formedics-prod.{dataset}.wp_posts` AS a

                INNER JOIN distinct_posts AS h
                    ON a.ID = h.post_id

                LEFT JOIN `formedics-prod.{dataset}.wp_postmeta` AS b
                    ON a.ID = b.post_id

            WHERE
                post_type <> 'revision'

            GROUP BY
                a.ID, a.post_date, a.post_date_gmt, a.guid, a.post_modified,
                a.post_modified_gmt, a.post_name, a.post_status, a.post_type,
                a.post_title, a.post_author, a.comment_status, a.ping_status
        )

        SELECT
            CONCAT('https://www.', @site, '.com/', p.type,'/', p.slug) AS link,
            p.title,
            p.post_content,
            p.post_excerpt,
            p.date,
            p.slug,
            p.modified,
            IF(@site = 'physiciansweekly', CONCAT('https://cdn.', @site, '.com/wp-content/uploads/',img_url.meta_value), feat_img.guid) AS featured_image,
            p.is_video,
            p.type,
            CASE
                WHEN (p.email_subject_line = '' OR p.email_subject_line IS NULL)
                THEN p.title
                ELSE p.email_subject_line
                END AS email_subject_line,
            CASE
                WHEN (p.email_preheader = '' OR p.email_preheader IS NULL)
                THEN p.post_excerpt
                ELSE p.email_preheader
                END AS email_preheader

        FROM
            pre_data AS p

            LEFT JOIN `formedics-prod.{dataset}.wp_posts` AS feat_img
                ON p.featured_media = feat_img.ID AND feat_img.post_type = 'attachment'

            LEFT JOIN `formedics-prod.{dataset}.wp_postmeta` AS img_url
                ON feat_img.ID = img_url.post_id
                AND img_url.meta_key = '_wp_attached_file'

        ORDER BY p.date DESC;"""

        try:
            config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter('site', 'STRING', self.site),
                    bigquery.ScalarQueryParameter('dfp_zone', 'STRING', self.dfp_zone),
                ]
            )

            start_time = time.time()
            job = self.bq_client.query(query, job_config=config)
            results = job.result()
            df = results.to_dataframe()
            rows = df.to_json(orient='records', date_format='iso')
            duration_ms = (time.time() - start_time) * 1000

            logger.info('BigQuery query completed',
                       duration_ms=round(duration_ms, 2),
                       rows_returned=len(rows),
                       bytes_processed=job.total_bytes_processed,
                       job_id=job.job_id)

            if len(rows) == 0:
                logger.warning('No posts found in BigQuery for dfp_zone', dfp_zone=self.dfp_zone)
                raise BQContentError(f'No posts found for dfp_zone: {self.dfp_zone}')

            if not rows:
                raise BQContentError(f'No posts found for dfp_zone: {self.dfp_zone}')

            return self._transform_sponsored_posts(loads(rows))

        except bigquery.exceptions.BigQueryError as e:
            logger.error('BigQuery error',
                        dfp_zone=self.dfp_zone,
                        error_code=getattr(e, 'code', None))
            raise BQContentError(f'BigQuery error while retrieving posts for dfp_zone {self.dfp_zone}: {e}')
        except Exception as e:
            logger.error('Unexpected error querying BigQuery',
                        dfp_zone=self.dfp_zone,
                        error_type=type(e).__name__)
            raise BQContentError(f'BigQuery error while retrieving posts for dfp_zone {self.dfp_zone}: {e}')
        finally:
            if self.bq_client:
                self.bq_client.close()

    def _transform_sponsored_posts(self, posts: list) -> List[SponsoredPosts]:
        """Transform raw sponsored posts to structured format"""
        out = [{
            'url': d['link'],
            'title': d['title'],
            'post_content': d['post_content'],
            'post_excerpt': d['post_excerpt'],
            'date': d['date'],
            'slug': d['slug'],
            'modified': d['modified'],
            'featured_image': d['featured_image'],
            'is_video': d['is_video'],
            'email_subject_line': d['email_subject_line'],
            'email_preheader': d['email_preheader']
        } for d in posts if d['type'] == 'post']

        if not out:
            raise Exception('No content found')

        page = [d['link'] for d in posts if d['type'] == 'page' or d['type'] == 'conferences']

        if page and len(page) == 1:
            out.insert(0,page[0])
        elif len(page) == 0:
            raise Exception('No collection URL found')
        else:
            raise Exception('Multiple collection URLs found')

        return out[0:10]
