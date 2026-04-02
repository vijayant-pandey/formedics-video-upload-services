from typing import List, Optional
from pydantic import BaseModel, Field, RootModel
from enum import Enum


# ELS JOURNAL AUTHOR

class OpenSearchQuery(BaseModel):
    role: str = Field(alias="@role")
    search_terms: str = Field(alias="@searchTerms")
    start_page: str = Field(alias="@startPage")


class SearchLink(BaseModel):
    fa: bool = Field(alias="@_fa")
    ref: str = Field(alias="@ref")
    href: str = Field(alias="@href")
    type: str = Field(alias="@type")


class EntryLink(BaseModel):
    fa: bool = Field(alias="@_fa")
    rel: str = Field(alias="@rel")
    href: str = Field(alias="@href")


# class EntryAuthor(BaseModel):
#     name: str = Field(alias="$")


# class EntryAuthors(BaseModel):
#     author: List[EntryAuthor]


class Author(BaseModel):
    fa: str = Field(alias='@_fa')
    value: str = Field(alias='$')


class Authors(RootModel[List[Author]]):
    pass


class Entry(BaseModel):
    link: List[EntryLink]
    identifier: str = Field(alias="dc:identifier")
    url: str = Field(alias="prism:url")
    title: str = Field(alias="dc:title")
    creator: str = Field(alias="dc:creator")
    publication_name: str = Field(alias="prism:publicationName")
    cover_date: str = Field(alias="prism:coverDate")
    doi: Optional[str] = Field(alias="prism:doi", default=None)
    openaccess: str
    openaccessFlag: bool
    pii: str


class SearchResultsPayload(BaseModel):
    total_results: str = Field(alias="opensearch:totalResults")
    start_index: str = Field(alias="opensearch:startIndex")
    items_per_page: str = Field(alias="opensearch:itemsPerPage")
    query: OpenSearchQuery = Field(alias="opensearch:Query")
    link: List[SearchLink]
    entry: List[Entry]


class SearchResultsWrapper(BaseModel):
    search_results: SearchResultsPayload = Field(alias="search-results")


# ELS ARTICLE

class SimpleValue(BaseModel):
    value: str = Field(alias="$")


class Creator(SimpleValue):
    fa: Optional[bool] = Field(alias="@_fa", default=None)


class Subject(SimpleValue):
    fa: Optional[bool] = Field(alias="@_fa", default=None)


class CoreLink(BaseModel):
    fa: Optional[bool] = Field(alias="@_fa", default=None)
    rel: str = Field(alias="@rel")
    href: str = Field(alias="@href")


class MediaObject(BaseModel):
    category: Optional[str] = Field(alias="@category", default=None)
    height: Optional[int] = Field(alias="@height", default=None)
    width: Optional[int] = Field(alias="@width", default=None)
    fa: Optional[bool] = Field(alias="@_fa", default=None)
    url: str = Field(alias="$")
    multimediatype: Optional[str] = Field(alias="@multimediatype", default=None)
    type: Optional[str] = Field(alias="@type", default=None)
    size: Optional[int] = Field(alias="@size", default=None)
    ref: Optional[str] = Field(alias="@ref", default=None)
    mimetype: Optional[str] = Field(alias="@mimetype", default=None)


class Objects(BaseModel):
    object: List[MediaObject]


class CoreData(BaseModel):
    eid: str
    description: str = Field(alias="dc:description")
    open_archive_article: str = Field(alias="openArchiveArticle")
    cover_date: str = Field(alias="prism:coverDate")
    openaccess_user_license: Optional[str] = Field(alias="openaccessUserLicense", default=None)
    aggregation_type: str = Field(alias="prism:aggregationType")
    url: str = Field(alias="prism:url")
    creators: List[Creator] = Field(alias="dc:creator")
    links: List[CoreLink] = Field(alias="link")
    dc_format: str = Field(alias="dc:format")
    openaccess_type: Optional[str] = Field(alias="openaccessType", default=None)
    pii: str
    volume: Optional[str] = Field(alias="prism:volume", default=None)
    publisher: Optional[str] = Field(alias="prism:publisher", default=None)
    title: str = Field(alias="dc:title")
    copyright: Optional[str] = Field(alias="prism:copyright", default=None)
    openaccess: str
    issn: Optional[str] = Field(alias="prism:issn", default=None)
    issue_identifier: Optional[str] = Field(alias="prism:issueIdentifier", default=None)
    subjects: List[Subject] = Field(alias="dcterms:subject")
    openaccess_article: str = Field(alias="openaccessArticle")
    publication_name: str = Field(alias="prism:publicationName")
    number: Optional[str] = Field(alias="prism:number", default=None)
    openaccess_sponsor_type: Optional[str] = Field(alias="openaccessSponsorType", default=None)
    page_range: Optional[str] = Field(alias="prism:pageRange", default=None)
    ending_page: Optional[str] = Field(alias="prism:endingPage", default=None)
    pub_type: Optional[str] = Field(alias="pubType", default=None)
    cover_display_date: Optional[str] = Field(alias="prism:coverDisplayDate", default=None)
    doi: Optional[str] = Field(alias="prism:doi", default=None)
    starting_page: Optional[str] = Field(alias="prism:startingPage", default=None)
    identifier: Optional[str] = Field(alias="dc:identifier", default=None)
    openaccess_sponsor_name: Optional[str] = Field(alias="openaccessSponsorName", default=None)


class TopLink(BaseModel):
    rel: str = Field(alias="@rel")
    href: str = Field(alias="@href")


class FullTextRetrievalResponse(BaseModel):
    scopus_eid: str = Field(alias="scopus-eid")
    original_text: str = Field(alias="originalText")
    scopus_id: str = Field(alias="scopus-id")
    pubmed_id: Optional[str] = Field(alias="pubmed-id", default=None)
    coredata: CoreData
    objects: Objects
    link: TopLink


class ArticleFullText(BaseModel):
    full_text_retrieval_response: FullTextRetrievalResponse = Field(
        alias="full-text-retrieval-response"
    )


# CUSTOM ELS OUTPUT

class PreProcessedData(BaseModel):
    title: str
    url: str
    creator: str
    authors: list[str]
    abstract: str  # dc:description from coredata
    content: str  # Full article text (originalText)
    openaccess: str
    openaccessArticle: str
    pii: str
    doi: str
    publication_date: str  # Format: YYYY-MM-DD from prism:coverDate

# EXPECTED PAYLOAD

class JournalName(str, Enum):
    CELLULAR_MOLECULAR_GASTRO_HEPATOLOGY = "Cellular and Molecular Gastroenterology and Hepatology"
    CLINICAL_GASTRO_HEPATOLOGY = "Clinical Gastroenterology and Hepatology"
    GASTRO_HEP_ADVANCES = "Gastro Hep Advances"
    GASTROENTEROLOGY = "Gastroenterology"
    TECHNIQUES_INNOVATIONS_GI_ENDOSCOPY = "Techniques and Innovations in Gastrointestinal Endoscopy"

    def __str__(self):
        return self.value

    @property
    def issn(self) -> str:
        """Get the ISSN code for this journal"""
        issn_map = {
            "Cellular and Molecular Gastroenterology and Hepatology": "2352-345X",
            "Clinical Gastroenterology and Hepatology": "1542-3565",
            "Gastro Hep Advances": "2772-5723",
            "Gastroenterology": "0016-5085",
            "Techniques and Innovations in Gastrointestinal Endoscopy": "2590-0307"
        }
        return issn_map.get(self.value, "")


class ElsevierSummaryRequest(BaseModel):
    """Request model for generating Elsevier journal summaries"""
    journal: JournalName = Field(
        description="Journal/Publication name to search"
    )
    additional_queries: Optional[str] = Field(
        default=None,
        description="Additional search parameters to filter results (e.g., 'IBD', 'Crohn's disease')",
        examples=["IBD", "Crohn's disease", "ulcerative colitis"]
    )


class ArticleSummary(BaseModel):
    headline: str = Field(max_length=60)
    authors: List[str]
    excerpt: str = Field(max_length=125)
    summary: str
    abstract: str
    url: str
    openaccess: bool
    meshcodes: List[str] = Field(min_length=3, max_length=5)
    icd10_codes: List[str] = Field(min_length=1, max_length=3)
    citations: str
    key_takeaways: List[str] = Field(min_length=3, max_length=3)
    study_objective: List[str] = Field(min_length=2, max_length=2)
    methods: List[str] = Field(min_length=4, max_length=4)
    results: List[str] = Field(min_length=4, max_length=4)
    clinical_relevance: List[str] = Field(min_length=2, max_length=3)
    meta_description: str = Field(max_length=159)
    tags: List[str] = Field(max_length=6)
    pii: str
    doi: str
    publication_date: str


class ArticleSummaryListSchema(RootModel[List[ArticleSummary]]):
    root: List[ArticleSummary]


class FakeAbstract(BaseModel):
    abstract: str
