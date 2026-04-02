from fastapi import HTTPException
from fastapi.responses import JSONResponse
from mongodb import AMCMongo, MashupMongo
from .dtypes import *
from utils import convert_mongo_types, is_valid_mongo_pipeline
from datetime import datetime, timezone
import time
from common.logging.logging_config import get_logger


logger = get_logger('internal.mashupmongo.service')

class MashupMongoService:
    """Service for handling MashupMD MongoDB operations"""
    def update_website_search_article(self, payload: UpdateArticleRequest):
        """
            Updates one article in the search articles collection by website.
            """
        document_id = payload.filter["_id"]["$oid"]
        logger.info('Updating website search article',
                   collection=payload.collection,
                   document_id=document_id)

        try:
            start_time = time.time()
            mongo_client = AMCMongo()
            data_collection = payload.collection
            data_document = payload.update["$set"]

            update_article = mongo_client.update_search_article(
                data=data_document,
                collection=data_collection,
                document_id=document_id
            )

            mongo_client.__client__.close()
            duration_ms = (time.time() - start_time) * 1000

            logger.info('Article updated successfully',
                       collection=payload.collection,
                       document_id=document_id,
                       duration_ms=round(duration_ms, 2))

            return JSONResponse(status_code=200, content=update_article)
        except Exception as e:
            logger.error('Failed to update article',
                        collection=payload.collection,
                        document_id=document_id,
                        error_type=type(e).__name__)
            raise HTTPException(status_code=400, content=str(e))

    def insert_website_search_article(self, payload: InsertArticleRequest):
        """Insert one article into the search articles collection by website."""
        logger.info('Inserting website search article',
                   collection=payload.collection)

        try:
            start_time = time.time()
            mongo_client = AMCMongo()
            data_collection = payload.collection
            data_document = payload.document

            insert_article = mongo_client.insert_search_article(
                                                            data=data_document,
                                                            collection=data_collection)
            mongo_client.__client__.close()
            duration_ms = (time.time() - start_time) * 1000

            logger.info('Article inserted successfully',
                       collection=payload.collection,
                       inserted_id=str(insert_article),
                       duration_ms=round(duration_ms, 2))

            return JSONResponse(status_code=200, content={"insertedId":str(insert_article)})
        except Exception as e:
            logger.error('Failed to insert article',
                        collection=payload.collection,
                        error_type=type(e).__name__)
            raise HTTPException(status_code=400, content=str(e))

    def import_mashup_articles(self, payload):
        """Imports twitter articles from MongoDB to import to mashupmd.com"""
        pipeline = payload.pipeline
        logger.info('Importing mashup articles', has_pipeline=bool(pipeline))

        if not is_valid_mongo_pipeline(pipeline):
            logger.warning('Invalid MongoDB pipeline provided')
            raise HTTPException(status_code=400, detail='Invalid pipeline')

        mongo_client = MashupMongo()
        # Convert pipeline date format
        try:
            get_date = pipeline[0]['$match']['timestamp']['$gt'].get('$date')
            if not get_date:
                raise ValueError("Missing $date in pipeline")
            convert = datetime.fromisoformat(get_date).astimezone(timezone.utc)
            logger.info('Pipeline date parsed', date=convert.isoformat())
        except Exception as e:
            logger.error('Invalid date format in pipeline', error=str(e))
            raise HTTPException(status_code=400, detail=f'Invalid date format: {e}')

        # Update '$match' operator. This is because mashupmd.com sends the pipeline but using a slightly outdated version
        pipeline[0]['$match']['timestamp']['$gt'] = convert

        try:
            start_time = time.time()
            import_articles = mongo_client.import_articles(pipeline)

            # Convert objectIds to avoid errors
            cleaned_output = convert_mongo_types(import_articles)

            mongo_client.__client__.close()
            duration_ms = (time.time() - start_time) * 1000

            logger.info('Mashup articles imported successfully',
                       article_count=len(cleaned_output),
                       duration_ms=round(duration_ms, 2))

            return cleaned_output
        except Exception as e:
            logger.error('Failed to import mashup articles',
                        error_type=type(e).__name__)
            raise HTTPException(status_code=400, content=str(e))
