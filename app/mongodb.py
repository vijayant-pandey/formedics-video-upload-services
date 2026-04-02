from pymongo import MongoClient, DESCENDING
import os
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime, timedelta
import pytz
from bson import ObjectId


class MongoId(BaseModel):
    oid: str = Field(..., alias="$oid")


class Author(BaseModel):
    ID: int
    name: str
    slug: str
    type: str


class Category(BaseModel):
    ID: int
    name: str
    description: str
    slug: str
    type: str


class PostModel(BaseModel):
    # _id: MongoId
    id: int
    post_type: str
    date: str  # Could be datetime if you want stricter typing
    status: str
    url: str
    title: str
    author: List[Author]
    content: str
    featured_image: str
    categories: List[Category]
    tags: List[str]
    site_name: str
    timestamp: str  # Could be datetime with custom parsing
    mongo_status: str

MONGO_USERNAME = os.environ['MONGO_AMC_USER']
MONGO_PASSWORD = os.environ['MONGO_AMC_PASS']
MONGO_URL = os.environ['MONGO_AMC_URL']
CONNECTION_STRING = f'mongodb+srv://{MONGO_USERNAME}:{MONGO_PASSWORD}@{MONGO_URL}/'

# MashupMD specific MongoDB credentials
MASHUP_MONGO_USER = os.environ['MONGO_MASHUP_USER']
MASHUP_MONGO_PASS = os.environ['MONGO_MASHUP_PASS']
MASHUP_MONGO_URL = os.environ['MONGO_MASHUP_URL']

def connection_string(username: str, password: str, url: str) -> str:
    return f'mongodb+srv://{username}:{password}@{url}/'
 
class MashupMongo:
    def __init__(self):
        self.__client__ = MongoClient(connection_string(
            username=MASHUP_MONGO_USER,
            password=MASHUP_MONGO_PASS,
            url=MASHUP_MONGO_URL))
        self.__db__ = self.__client__['mashup_new']

    def import_articles(self, pipeline):
        col = self.__db__['v2_articlesWP']
        import_articles = col.aggregate(pipeline)
        return list(import_articles)

class AMCMongo:
    def __init__(self):
        self.__client__ = MongoClient(CONNECTION_STRING)
        self.__db__ = self.__client__['mumsitesearches']

    def insert_search_article(
            self,
            collection: str,
            data):
        col = self.__db__[f'{collection}']
        result = col.insert_one(data)
        return result.inserted_id
    
    def update_search_article(
            self,
            collection: str,
            document_id: str,
            data):
        col = self.__db__[f'{collection}']
        result = col.update_one({"_id": ObjectId(document_id)}, {"$set": data},upsert=True)
        return {
            "matchedCount": result.matched_count,
            "modifiedCount": result.modified_count,
            "upsertedId": str(result.upserted_id) if result.upserted_id else None
        }
        
    def get_articles(
            self,
            site_nm:str,
            or_categories:str = None,
            and_categories:str = None,
            newer_than:int = None,
            exclude:list = None,
            limit:int = None) -> List[PostModel]:
        col = self.__db__[f'article_{site_nm}']
        filt = {
            'status': 'publish',
            'post_type': 'post'
        }

        if newer_than:
            now = datetime.now(pytz.utc)
            last_n = now - timedelta(days=newer_than)
            filt['_date'] = { '$gte': last_n }

        if or_categories:
            or_categories_logic = or_categories.split(',')
            or_categories_logic = [{ 'categories.slug': d.strip() } for d in or_categories_logic]
            filt['$or'] = or_categories_logic

        if and_categories:
            and_categories_logic = and_categories.split(',')
            and_categories_logic = [{ 'categories.slug': d.strip() } for d in and_categories_logic]
            filt['$or'] = and_categories_logic

        pipeline = [
            {
                '$addFields': {
                    '_date': {
                        # '$cond': [
                        #     {
                        #         '$eq': [
                        #             {
                        #                 '$type': '$timdateestamp'
                        #             }, 'string'
                        #         ]
                        #     }, {
                        #         '$toDate': '$date'
                        #     }, '$date'
                        # ]
                        '$dateFromString': {
                            'dateString': "$date"
                        }
                    }
                }
            }, {
                '$match': filt
            }, {
                '$sort': {
                    '_date': -1
                }
            }, {
                '$project': {
                    '_id': 0, 
                    'id': '$id', 
                    'post_type': '$post_type', 
                    'status': '$status', 
                    'url': '$url', 
                    'title': '$title', 
                    'author': '$author', 
                    'content': '$content', 
                    'featured_image': '$featured_image', 
                    'categories': '$categories', 
                    'tags': '$tags', 
                    'site_name': '$site_name', 
                    'date': {
                        '$dateToString': {
                            'format': '%Y-%m-%d %H:%M:%S', 
                            'date': '$_date'
                        }
                    },
                    'timestamp': '$timestamp',
                    'mongo_status': '$mongo_status'
                }
            }
        ]

        if exclude:
            pipeline.append({
                '$match': {
                    'categories.slug': {
                        '$nin': exclude
                    }
                }
            })

        if limit:
            pipeline.append({
                '$limit': limit
            })
            
        articles = col.aggregate(pipeline)

        return list(articles)
