import requests
from datetime import datetime, timedelta, timezone
import os
from .dtypes import BlueconicTokenResponse


class BlueconicAPIException(Exception):
    """Custom exception for Blueconci REST API operations"""
    pass


class BlueconicAPI:
    def __init__(self): #, line_item_id:int, creative_id:int):
        self.session = requests.Session()
        self._token = None
        self._token_exp = None
        self._base_url = 'https://physiciansweekly.blueconic.net/rest/v2'
        self.segments = []
        # self.filtered_segments = []
        # self.line_item_id = line_item_id
        # self.creative_id = creative_id

    def _check_token_exp(self) -> bool:
        if not self._token:
            return True
        
        now = datetime.now(timezone.utc)
        return now > self._token_exp

    def _send_request(self, endpoint:str, headers: dict | None = None, method:str = 'GET', data:dict | None = None, json:dict | None = None):
        if headers is None:
            headers = {}

        try:
            url = f'{self._base_url}/{endpoint}'
            resp = self.session.request(
                        method=method,
                        url=url,
                        headers=headers,
                        data=data,
                        json=json
                    )
            resp.raise_for_status()
        
            return resp.json()
        except requests.exceptions.HTTPError as e:
            raise BlueconicAPIException(f'Error retrieving Bearer Token: {str(e)}')
        except Exception as e:
            raise BlueconicAPIException(f'Error retrieving Bearer Token: {str(e)}')

    def _get_token(self) -> BlueconicTokenResponse:
        try:
            resp = self._send_request(
                endpoint='oauth/token',
                method='POST',
                data={
                    'grant_type': 'client_credentials',
                    'client_id': os.environ.get('BLUECONIC_CLIENT_ID'),
                    'client_secret': os.environ.get('BLUECONIC_CLIENT_SECRET')
                }
            )

            if not resp.get('access_token'):
                raise BlueconicAPIException(f'Error retrieving Bearer Token: {str(e)}')
            now = datetime.now(timezone.utc)
            self._token_exp = now + timedelta(hours=1)
            
            return resp
        except Exception as e:
            raise BlueconicAPIException('Exception retrieving Bearer Token: ', str(e))
        
    def get_data(self, start:int=0, count:int=50):
        if self._check_token_exp():
            self._token = self._get_token()

        if not self._token:
            raise RuntimeError('_get_token() returned None or empty token')
        
        try:
            bearer_token_value = self._token.get('access_token')
            if bearer_token_value is None:
                raise KeyError('access_token key not found in self._token')

            resp = self._send_request(
                endpoint=f'segments?startIndex={start}&count={count}',
                headers={
                    'Authorization': f'Bearer {bearer_token_value}'
                },
                method='GET'
            )

            self.segments = self.segments + resp.get('segments')

            # for segment in resp.get('segments'):
            #     parse_desc = parse_kv_string(segment.get('description'))
            #     if parse_desc.get('line_item_id') == self.line_item_id \
            #         and parse_desc.get('creative_id') == self.creative_id:
            #         self.filtered_segments.append(segment)
            start += 50

            if start < resp.get('totalResults'):
                self.get_data(start=start)

            self.session.close()
            return self.segments
            # return self._validate_segment()
        except Exception as e:
            raise BlueconicAPIException(f'Error retrieving Blueconic segments: {str(e)}')

    # def _validate_segment(self) -> BlueconicValidationResponse:
    #     segments = self.filtered_segments

    #     if len(self.filtered_segments) == 0:
    #         return {
    #             'status': 'invalid',
    #             'errors': [f'No segments found for line_item_id: {self.line_item_id} and creative_id: {self.creative_id}'],
    #             'segments': segments
    #         }
    #     elif len(self.filtered_segments) > 1:
    #         return {
    #             'status': 'invalid',
    #             'errors': ['Too many segments detected'],
    #             'segments': segments
    #         }

    #     if self.filtered_segments[0].get('profileCount') == 0:
    #         return {
    #             'status': 'invalid',
    #             'errors': ['Zero profiles associated with segment, log in to Blueconic to redefine the segment.'],
    #             'segments': segments
    #         }

    #     return {
    #         'status': 'valid',
    #         'errors': None,
    #         'segments': segments
    #     }


# if __name__ == '__main__':
#     client = BlueconicAPI(creative_id=1,line_item_id=4264388)
#     validation = client.get_data()
#     print(dumps(validation, indent=4))
#     client.session.close()


