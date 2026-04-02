import os
import base64
import hashlib
import hmac
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from json import dumps
import requests
from .dtypes import *
import logging


class IterableAPIException(Exception):
    """Custom exception for Iterable REST API operations"""
    pass


class IterableAPI:
    BASE_URL = 'https://api.iterable.com/api'
    CONTENT_TYPE = 'application/json'

    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'Content-Type': self.CONTENT_TYPE,
            'Api_Key': os.environ['ITERABLE_API_KEY'],
        }
        self.lists = []

    def close_conn(self):
        self.session.close()

    def _send_request(self, method='GET', endpoint=None, data=None, headers=None):
        try:
            headers = headers or self.headers
            response = self.session.request(
                method=method,
                url=f'{self.BASE_URL}/{endpoint}',
                headers=headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logging.error(f'Error during request to {endpoint}: {str(e)}')
            raise IterableAPIException(f'Error during request to {endpoint}: {str(e)}')

    def _generate_jwt_header(self, user_id):
        try:
            now = datetime.now(timezone.utc)
            expires = now + timedelta(hours=1)
            encoding = 'utf-8'

            jwt_header = dumps({'alg': 'HS256', 'typ': 'JWT'}, 
                            separators=(',', ':')).encode(encoding)
            jwt_payload = dumps({
                                'userId': user_id,
                                'iat': int(now.timestamp()) - 1000,
                                'exp': int(expires.timestamp())
                                },
                                separators=(',', ':')).encode(encoding)

            def encode_base64url(data):
                return base64.urlsafe_b64encode(data).replace(b'=', b'')

            secret = os.environ['ITERABLE_MOBILE_JWT_SECRET'].encode(encoding)
            header_b64 = encode_base64url(jwt_header)
            payload_b64 = encode_base64url(jwt_payload)
            signature = hmac.digest(secret, b'.'.join([header_b64, payload_b64]), hashlib.sha256)
            signature_b64 = encode_base64url(signature)

            token = f'{header_b64.decode()}.{payload_b64.decode()}.{signature_b64.decode()}'
            headers = deepcopy(self.headers)
            headers['Api_Key'] = os.environ['ITERABLE_MOBILE_API_KEY']
            headers['Authorization'] = f'Bearer {token}'
            return headers
        except Exception as e:
            logging.error(f'Error generating JWT header: {str(e)}')
            raise IterableAPIException(f'Error generating JWT header: {str(e)}')

    def get_lists(self) -> List[IterableListsResponse]:
        lists = self._send_request('GET', 'lists')
        return lists.get('lists')
    
    def get_list_size(self, list_id: int) -> int:
        list_size = self._send_request('GET', f'/lists/{list_id}/size')
        return list_size
    
    def get_campaign_details(self, campaign_id=int) -> IterableCampaignDetails:
        campaign_details:IterableCampaignDetails = self._send_request('GET', f'/campaigns/{campaign_id}')
        return campaign_details

    def create_campaign(self, campaign_details:IterableCampaignRequest) -> IterableCreateCampaignResp:
        details:IterableCreateCampaignResp = self._send_request('POST', f'/campaigns/create', data=campaign_details)
        return details.campaign_id
    
    def schedule_campaign(self, campaign_id:int, schedule:IterableScheduleCampaign) -> IterableGeneralResponse:
        # schedule = {
        #     'sendAt': send_at
        # }
        
        schedule_resp:IterableGeneralResponse = self._send_request('POST', f'/campaigns/{campaign_id}/schedule')
        return schedule_resp
    
    # def activate_campaign(self):
    # def deactivate_campaign(sefl):
