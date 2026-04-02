import requests
from typing import Callable
from fastapi.responses import JSONResponse
import re
from .wp_api import WordPressAPI, BoostrRepository, BoostrRepositoryError, BQContent, BQSponsoredContent
from urllib.parse import unquote
from .dtypes import *
from .campaign_builder import get_utm_params
from bs4 import BeautifulSoup
import html
from common.logging.logging_config import get_logger


logger = get_logger('iterable.services')

class MashupService:
    """Service for handling Mashup Media API operations"""

    BASE_URL = 'https://www.mashupmd.com/wp-json/api/v1/iterable'

    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'Content-Type': 'application/json',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
        }

    def get_expert_articles(self, author: str) -> dict:
        """Fetch and process articles by expert"""
        logger.info('Fetching expert articles', author=author)
        target = f'{self.BASE_URL}/by-expert/{author}/'

        try:
            resp = self.session.request(
                method='GET',
                url=target,
                headers=self.headers,
                timeout=30
            )

            logger.info('Mashup API response received',
                        author=author,
                        status_code=resp.status_code,
                        response_time_ms=round(resp.elapsed.total_seconds() * 1000, 2))

            if not resp.ok:
                logger.warning('Mashup API returned error',
                                author=author,
                                status_code=resp.status_code,
                                response_body=resp.text[:500])
                return JSONResponse(
                    status_code=resp.status_code,
                    content=resp.json()
                )

            return self._process_response(resp.json(), 'expert')

        except requests.exceptions.Timeout:
            logger.error('Mashup API timeout',
                        author=author,
                        target_url=target,
                        timeout_seconds=30)
            raise
        except requests.exceptions.RequestException:
            logger.error('Mashup API request failed',
                        author=author,
                        target_url=target)
            raise

    def get_collection_articles(self, collection_slug: str) -> dict:
        """Fetch and process articles by collection"""
        logger.info('Fetching collection articles', collection_slug=collection_slug)
        target = f'{self.BASE_URL}/by-collection/{collection_slug}'

        try:
            resp = self.session.request(
                method='GET',
                url=target,
                headers=self.headers,
                timeout=30
            )

            logger.info('Mashup API response received',
                        collection_slug=collection_slug,
                        status_code=resp.status_code,
                        response_time_ms=round(resp.elapsed.total_seconds() * 1000, 2))

            if not resp.ok:
                logger.warning('Mashup API returned error',
                                collection_slug=collection_slug,
                                status_code=resp.status_code,
                                response_body=resp.text[:500])
                return JSONResponse(
                    status_code=resp.status_code,
                    content=resp.json()
                )

            return self._process_response(resp.json(), 'collection')

        except requests.exceptions.Timeout:
            logger.error('Mashup API timeout',
                        collection_slug=collection_slug,
                        target_url=target,
                        timeout_seconds=30)
            raise
        except requests.exceptions.RequestException:
            logger.error('Mashup API request failed',
                        collection_slug=collection_slug,
                        target_url=target)
            raise
    
    def _process_response(self, resp_json: dict, resp_type: str) -> dict:
        """Process collection articles response"""
        preprocess_map: dict[str, Callable[[dict], str]] = {
            'collection': lambda d: d.get('description', '').replace('\n', ''),
            'expert': lambda d: (
                d.get('html', '')
                .replace('<li ', '<li style="list-style: none;" ')
                .replace('\n', '')
            ),
        }

        field_map: dict[str, dict[str, str]] = {
            'collection': {'link': 'link', 'html_description': 'description'},
            'expert': {'title_link': 'title_link', 'html': 'html'},
        }

        raw_articles = resp_json.get("articles", [])
        articles = []

        for d in raw_articles:
            cust_html = html.unescape(preprocess_map.get(resp_type, lambda _: '')(d))
            clean_desc = (
                self._remove_html_tags_regex(cust_html)
                if '<ul>' not in cust_html
                else cust_html
            )
            article = {
                'title': d.get('title', ''),
                'clean_description': clean_desc,
            }

            for out_key, in_key in field_map.get(resp_type, {}).items():
                article[out_key] = cust_html if 'html' in out_key else d.get(in_key, '')

            articles.append(article)

        if resp_type == 'collection':
            return {
                'items': {
                    'expert': resp_json.get('expert', []),
                    'collection': resp_json.get('collection', []),
                    'articles': articles
                }
            }

        return {**resp_json, 'articles': articles}

    def _remove_html_tags_regex(self, text: str):
        clean = BeautifulSoup(text, 'html.parser')
        return clean.get_text().strip()


class WordPressService:
    """Service for handling WordPress API operations"""

    def get_categories(self, site: AnnotatedSiteParam) -> JSONResponse:
        """Get all categories for a WordPress site"""
        site_value = 'prodgionc' if site.value == 'gioncologynow' else site.value
        logger.info('Fetching WordPress categories', site=site_value)

        try:
            wp = WordPressAPI(site_value)
            categories = wp.get_categories()
            logger.info('WordPress categories retrieved',
                       site=site_value,
                       category_count=len(categories))
            return JSONResponse(status_code=200, content=categories)
        except requests.exceptions.HTTPError as e:
            logger.error('WordPress API error fetching categories',
                        site=site_value,
                        status_code=e.response.status_code)
            return JSONResponse(
                status_code=e.response.status_code,
                content=e.response.json()
            )

    def get_feed_items(self, params: GeneralIterableFeedParams) -> JSONResponse:
        """Get feed items with category filtering"""
        site = 'prodgionc' if params.site == 'gioncologynow' else params.site
        logger.info('Fetching feed items',
                    site=site,
                    category=params.category,
                    exclude=params.exclude,
                    featured_in_last=params.featured_in_last)

        try:
            wp = WordPressAPI(site)
            excludeCats = params.exclude.split(',') if params.exclude else []
            cats = [params.category] if params.category != '*' else []
            categories_data = wp.get_category_ids(cats, excludeCats)
            validation_result = self._validate_categories(categories_data, cats, excludeCats)

            if validation_result:
                logger.warning('Category validation failed',
                                site=site,
                                category=params.category,
                                exclude_cats=excludeCats)
                return validation_result

            specialty = next((item['id'] for item in categories_data if item['slug'] == params.category), None)
            excludes = [next((item['id'] for item in categories_data if item['slug'] == exclude_cat), None) for exclude_cat in excludeCats]

            posts = wp.get_posts(specialty, excludes, params.featured_in_last)
            wp.close_conn()

            logger.info('Feed items retrieved',
                        site=site,
                        category=params.category,
                        post_count=len(posts))

            return JSONResponse(status_code=200, content={'items': posts})
        except requests.exceptions.HTTPError as e:
            logger.error('WordPress API error fetching feed items',
                        site=site,
                        category=params.category,
                        status_code=e.response.status_code)
            return JSONResponse(
                status_code=e.response.status_code,
                content=e.response.json()
            )

    def _validate_categories(self, categories_data: list, cats: list, excludeCats: list) -> JSONResponse:
        """Validate that all categories exist"""
        if not categories_data:
            return JSONResponse(
                status_code=404,
                content={'error': 'No content was found.'}
            )

        category_slugs = {item['slug'] for item in categories_data}
        all_exist_cats = all(slug in category_slugs for slug in cats + excludeCats)

        if not all_exist_cats:
            return JSONResponse(
                status_code=404,
                content={'error': 'One or more of the primary category and the excluded categories do not exist. Use the /v2/categories/{site}/ endpoint to get a list of valid categories.'}
            )
        return None


class WordPressServiceBQ:
    """Service for handling WordPress API operations"""

    def get_feed_items(self, params: GeneralIterableFeedParams) -> JSONResponse:
        """Get feed items with category filtering"""
        site = 'prodgionc' if params.site == 'gioncologynow' else params.site
        logger.info('Fetching feed items',
                    site=site,
                    category=params.category,
                    exclude=params.exclude,
                    featured_in_last=params.featured_in_last)

        try:
            excludeCats = params.exclude.split(',') if params.exclude else []
            bq = BQContent(params.site, params.category, excludeCats, params.featured_in_last)
            posts = bq.get_posts()

            logger.info('Feed items retrieved',
                        site=site,
                        category=params.category,
                        post_count=len(posts))

            return JSONResponse(status_code=200, content={'items': posts})
        except requests.exceptions.HTTPError as e:
            logger.error('WordPress API error fetching feed items',
                        site=site,
                        category=params.category,
                        status_code=e.response.status_code)
            return JSONResponse(
                status_code=e.response.status_code,
                content=e.response.json()
            )


class SponsoredContentService:
    """Service for handling sponsored content operations"""
    def __init__(self):
        self._BOOSTER_WP_SITE_MAP = {
            "Blood Cancers Today": "bloodcancerstoday",
            "Breast Cancers Today": "docwirenews",
            "Nursing Today": "cancernursingtoday",
            "Docwire News": "docwirenews",
            "Figure 1": None,
            "GI Oncology Now": "prodgionc",
            "GU Oncology Now": "guoncologynow",
            "Heme Today": "docwirenews",
            "Lung Cancers Today": "lungcancerstoday",
            "Mashup MD": None,
            "Metabolic Care Today": "docwirenews",
            "Nephrology Times": "docwirenews",
            "Physician's Weekly": "physiciansweekly",
            "Urban Health Today": "urbanhealthtoday",
            "Cardio Care Today": "cardiocaretoday",
        }

    def get_sponsored_items(self, template_name: str) -> JSONResponse:
        """Get sponsored content items"""
        logger.info('Fetching sponsored items', template_name=template_name)

        line_item_id = self._extract_line_item_id(template_name)
        line_item_id = int(line_item_id)

        if len(str(line_item_id)) != 7:
            logger.warning('Invalid line item ID length',
                            line_item_id=line_item_id,
                            length=len(str(line_item_id)))
            return JSONResponse(
                status_code=400,
                content={'error': 'Line item IDs must be 7 digits'}
            )

        if not line_item_id:
            logger.warning('No line item ID found in template name',
                            template_name=template_name)
            return JSONResponse(
                status_code=400,
                content={'error': 'No valid line_item_id found inside brackets'}
            )

        try:
            boostr_info = BoostrRepository().get_package_id(line_item_id)
            site_nm = self._BOOSTER_WP_SITE_MAP[boostr_info['site']]

            logger.info('Retrieved Boostr info',
                        line_item_id=line_item_id,
                        site=site_nm,
                        dfp_zone=boostr_info['dfp_zone'])

            wp = WordPressAPI(site_nm)
            posts_data = wp.get_posts_by_dfp_zone(dfp_zone=boostr_info['dfp_zone'])

            wp.close_conn()
            if isinstance(posts_data[0], str):
                boostr_info['collection_url'] = posts_data[0]
                boostr_info['items'] = posts_data[1:]
            else:
                boostr_info['items'] = posts_data

            logger.info('Sponsored items retrieved',
                        line_item_id=line_item_id,
                        item_count=len(boostr_info['items']))

            return JSONResponse(status_code=200, content=boostr_info)
        except requests.exceptions.HTTPError as e:
            logger.error('WordPress API error fetching sponsored items',
                        line_item_id=line_item_id,
                        status_code=e.response.status_code)
            return JSONResponse(
                status_code=e.response.status_code,
                content=e.response.json()
            )
        except BoostrRepositoryError as e:
            logger.error('Boostr repository error',
                        line_item_id=line_item_id,
                        error=str(e))
            return JSONResponse(
                status_code=404 if 'Site is not specified for line item ID' in str(e) else 400,
                content=str(e)
            )
        except Exception as e:
            logger.error('Unexpected error fetching sponsored items',
                        line_item_id=line_item_id,
                        error_type=type(e).__name__)
            return JSONResponse(
                status_code=404 if 'No content found' in str(e) else 400,
                content={
                    'error': str(e),
                    'detail': boostr_info if 'boostr_info' in locals() else None
                }
            )

    def _extract_line_item_id(self, template_name: str) -> str:
        """Extract line item ID from template name"""
        match = re.search(r'\[(\d+)\]', template_name)
        return match.group(1) if match else None


class SponsoredContentServiceBQ:
    """Service for handling sponsored content operations from BigQuery"""
    def __init__(self):
        self._BOOSTER_WP_SITE_MAP = {
            "Blood Cancers Today": "bloodcancerstoday",
            "Breast Cancers Today": "docwirenews",
            "Nursing Today": "cancernursingtoday",
            "Docwire News": "docwirenews",
            "Figure 1": None,
            "GI Oncology Now": "prodgionc",
            "GU Oncology Now": "guoncologynow",
            "Heme Today": "docwirenews",
            "Lung Cancers Today": "lungcancerstoday",
            "Mashup MD": None,
            "Metabolic Care Today": "docwirenews",
            "Nephrology Times": "docwirenews",
            "Physician's Weekly": "physiciansweekly",
            "Urban Health Today": "urbanhealthtoday",
            "Cardio Care Today": "cardiocaretoday",
        }

    def get_sponsored_items(self, template_name: str) -> JSONResponse:
        """Get sponsored content items"""
        logger.info('Fetching sponsored items', template_name=template_name)

        line_item_id = self._extract_line_item_id(template_name)
        line_item_id = int(line_item_id)

        if len(str(line_item_id)) != 7:
            logger.warning('Invalid line item ID length',
                            line_item_id=line_item_id,
                            length=len(str(line_item_id)))
            return JSONResponse(
                status_code=400,
                content={'error': 'Line item IDs must be 7 digits'}
            )

        if not line_item_id:
            logger.warning('No line item ID found in template name',
                            template_name=template_name)
            return JSONResponse(
                status_code=400,
                content={'error': 'No valid line_item_id found inside brackets'}
            )

        try:
            boostr_info = BoostrRepository().get_package_id(line_item_id)
            site_nm = self._BOOSTER_WP_SITE_MAP[boostr_info['site']]

            logger.info('Retrieved Boostr info',
                        line_item_id=line_item_id,
                        site=site_nm,
                        dfp_zone=boostr_info['dfp_zone'])

            bq = BQSponsoredContent(site_nm, dfp_zone=f"{boostr_info['dfp_zone']}")
            posts_data = bq.get_sponsored_posts()

            if isinstance(posts_data[0], str):
                boostr_info['collection_url'] = posts_data[0]
                boostr_info['items'] = posts_data[1:]
            else:
                boostr_info['items'] = posts_data

            logger.info('Sponsored items retrieved',
                        line_item_id=line_item_id,
                        item_count=len(boostr_info['items']))

            return JSONResponse(status_code=200, content=boostr_info)
        except requests.exceptions.HTTPError as e:
            logger.error('BigQuery error fetching sponsored items',
                        line_item_id=line_item_id,
                        status_code=e.response.status_code)
            return JSONResponse(
                status_code=e.response.status_code,
                content=e.response.json()
            )
        except BoostrRepositoryError as e:
            logger.error('Boostr repository error',
                        line_item_id=line_item_id,
                        error=str(e))
            return JSONResponse(
                status_code=404 if 'Site is not specified for line item ID' in str(e) else 400,
                content=str(e)
            )
        except Exception as e:
            logger.error('Unexpected error fetching sponsored items',
                        line_item_id=line_item_id,
                        error_type=type(e).__name__)
            return JSONResponse(
                status_code=404 if 'No content found' in str(e) else 400,
                content={
                    'error': str(e),
                    'detail': boostr_info if 'boostr_info' in locals() else None
                }
            )

    def _extract_line_item_id(self, template_name: str) -> str:
        """Extract line item ID from template name"""
        match = re.search(r'\[(\d+)\]', template_name)
        return match.group(1) if match else None


class CampaignBuilderService:
    """Service for handling campaign builder operations"""

    def get_campaign_feed(self, campaign_name: str) -> JSONResponse:
        """Get campaign builder feed data"""
        logger.info('Fetching campaign feed', campaign_name=campaign_name)

        try:
            line_item_id = self._extract_line_item_id(campaign_name)

            if not line_item_id:
                logger.warning('No line item ID found in campaign name',
                                campaign_name=campaign_name)
                return JSONResponse(
                    status_code=400,
                    content={'error': 'No valid line_item_id found inside brackets'}
                )

            items = get_utm_params(line_item_id)

            if len(items) == 0:
                logger.warning('No campaign records found',
                                line_item_id=line_item_id)
                return JSONResponse(
                    status_code=404,
                    content={'error': 'No valid records found for specified line_item_id'}
                )

            logger.info('Campaign feed retrieved',
                        line_item_id=line_item_id,
                        item_count=len(items))

            return JSONResponse(status_code=200, content={'items': items})
        except Exception as e:
            logger.error('Failed to fetch campaign feed',
                        campaign_name=campaign_name,
                        error_type=type(e).__name__)
            return JSONResponse(
                    status_code=500,
                    content={'error': str(e)}
                )

    def _extract_line_item_id(self, campaign_name: str) -> str:
        """Extract line item ID from campaign name"""
        match = re.search(r'\[(\d{7})\]', campaign_name)
        return match.group(1) if match else None


class WallboardService:
    """Service for handling wallboard operations"""

    def get_wallboard_feed(self, template_name: str) -> JSONResponse:
        """Get wallboard feed data"""
        template_name = unquote(template_name)
        category_slug = self._extract_category_slug(template_name)

        logger.info('Fetching wallboard feed',
                    template_name=template_name,
                    category_slug=category_slug)

        if not category_slug:
            logger.warning('No category slug found in template name',
                            template_name=template_name)
            return JSONResponse(
                status_code=400,
                content={'error': 'No valid category_slug found inside brackets'}
            )

        try:
            wp = WordPressAPI('physiciansweekly')
            posts = wp.get_wallboard_data(category_slug)

            logger.info('Wallboard feed retrieved',
                        category_slug=category_slug)

            return posts
        except requests.exceptions.HTTPError as e:
            logger.error('WordPress API error fetching wallboard feed',
                        category_slug=category_slug,
                        status_code=e.response.status_code)
            return JSONResponse(
                status_code=e.response.status_code,
                content=e.response.json() if e.response.status_code < 500 else 'Wordpress server error'
            )

    def _extract_category_slug(self, template_name: str) -> str:
        """Extract category slug from template name"""
        match = re.search(r'\[category_slug=(.*?)\]', template_name)
        return match.group(1) if match else None
