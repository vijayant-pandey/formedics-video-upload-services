from typing import Annotated, Any, Dict, List, Optional, Union
from fastapi import Query, HTTPException, Path
from pydantic import BaseModel, Field, model_validator
from enum import Enum
from datetime import datetime


site_desc = 'Available sites that utilize the WordPress API.'
categories_desc = '''Filter for posts that contain the specified category. \n
Categories for each site can be found in the [read_v2_categories](/docs#/General/read_v2_categories) endpoint. \n
Use <strong>*</strong> to pull in all categories. This should be used in conjuction with the limit value.'''
exclude_categories_desc = '''A comma separated list of categories to exclude from the results. \n
Categories for each site can be found in the [read_v2_categories](/docs#/General/read_v2_categories) endpoint.'''
featured_in_last_desc = '''An integer value that determines how many days ago to search for featured content. \n
For example, a value of 10 will search for featured content between 10 days ago and today.'''
limit_desc = '''An integer that limits the final results.'''
wallboard_template_desc = '''A string that includes a *[category_slug={dfp_zone}]*.
The dfp_zone value is then parsed using regular expression. The template_name is usually provided by an Iterable email template.
For example, **Brand Notify Test [498723][category_slug=123456]**.'''

class Site(str, Enum):
    bloodcancerstoday = "bloodcancerstoday"
    cancernursingtoday = "cancernursingtoday"
    cardiocaretoday = "cardiocaretoday"
    docwirenews = "docwirenews"
    gioncologynow = "gioncologynow"
    guoncologynow = "guoncologynow"
    lungcancerstoday = "lungcancerstoday"
    physiciansweekly = "physiciansweekly"
    urbanhealthtoday = "urbanhealthtoday"

    def __str__(self):
        return self.value

AnnotatedSiteParam = Annotated[
        Site,
        Path(description='Available sites that utilize the WordPress API',
            example='docwirenews')
    ]

class GeneralIterableFeedParams(BaseModel):
    site: Site
    category: str
    exclude: Optional[str] = None
    featured_in_last: Optional[int] = None
    limit: Optional[int] = None


def build_params(
    site: Site = Path(description='Available sites that utilize the WordPress API',
                    example='docwirenews'),
    category: str = Path(description=categories_desc),
    exclude: str | None = Query(None, description=exclude_categories_desc),
    featured_in_last: int | None = Query(None, description=featured_in_last_desc),
    limit: int | None = Query(None, description=limit_desc),
) -> GeneralIterableFeedParams:

    return GeneralIterableFeedParams(
        site=site,
        category=category,
        exclude=exclude,
        featured_in_last=featured_in_last,
        limit=limit
    )


class AMCParams(BaseModel):
    site_nm: str
    or_categories: Optional[str] = Query(default=None)
    and_categories: Optional[str] = Query(default=None)
    newer_than_n_days: Optional[int] = Query(default=None)
    exclude: Optional[str] = Query(default=None)
    limit: Optional[int] = Query(default=20)
    
    @model_validator(mode='before')
    @classmethod
    def validate_at_least_one(cls, data):
        if not data.get('or_categories') and not data.get('and_categories'):
            raise HTTPException(
                status_code=422,
                detail="Either 'or_categories' or 'and_categories' must be provided."
            )
        return data
    

class F1ContentParams(BaseModel):
    limit: int = Field(default=20,
        description='Limits the number of content that will be returned. Defaults to 20 if null.')
    specialty: Union[str, None] = Field(default=None,
        description='A single specialty that is used to filter for results.')
    
AnnotatedF1Params = Annotated[F1ContentParams, Query()]


# WordPress Types
class WPCategories(BaseModel):
    id: int
    slug: str

class GUID(BaseModel):
    raw: str
    rendered: str

class Title(BaseModel):
    raw: str
    rendered: str

class Content(BaseModel):
    raw: str
    rendered: str
    block_version: int
    protected: bool

class Excerpt(BaseModel):
    raw: str
    rendered: str
    protected: bool

class Meta(BaseModel):
    _acf_changed: bool
    footnotes: str

class Post(BaseModel):
    date: datetime
    date_gmt: datetime
    guid: GUID
    id: int
    link: str
    modified: datetime
    modified_gmt: datetime
    slug: str
    status: str
    type: str
    password: str
    permalink_template: str
    generated_slug: str
    class_list: List[str]
    title: Title
    content: Content
    author: int
    excerpt: Excerpt
    featured_media: int
    comment_status: str
    ping_status: str
    format: str
    meta: Meta
    sticky: bool
    template: str
    categories: List[int]
    tags: List[int]
    category_names: List[str]

class BoostrInfo(BaseModel):
    dfp_zone: str
    product_id: int
    product_full_name: str

class SponsoredPosts(BaseModel):
    url: str
    title: str
    post_content: str
