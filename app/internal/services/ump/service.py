from datetime import datetime, timezone
from .dtypes import *
from .bq_helper import _bigquery_row_to_dict, _validation_errors_to_list, _poll_metadata_table
from pydantic import ValidationError
from .firestore_helper import write_validation_batch, get_validations,get_validations_by_line_item, get_most_recent_date, get_missing_target_validations, single_upsert
from .gam_helper import _get_ad_manager_client, _fetch_line_item, _apply_targeting_update, _create_creative
from common.logging.logging_config import get_logger
from .blueconic import BlueconicAPI
from .iterable_helper import IterableAPI
from .utils import filter_list
from fastapi.responses import JSONResponse
from json import dumps


logger = get_logger('internal.ump.services')

class ValidateCampaignError(Exception):
    """Custom exception for ValidateCampaign operations"""
    pass

class ValidateCampaign:
    def __init__(self, campaign_details:ValidateRequest):
        self.now = datetime.now(timezone.utc)
        self.results = []
        self.firestore_docs = []
        self.valid_count = 0
        self.invalid_count = 0
        self.campaign_details = campaign_details

    def _process(self):
        try:
            # for raw_row in self.campaign_details.rows:
                # row_data = _bigquery_row_to_dict(self.campaign_details.schema_.fields, raw_row)
            for row_data in self.campaign_details.rows:
                errors = []
                status = 'valid'

                try:
                    CampaignMetadata(**row_data)
                except ValidationError as exc:
                    status = 'invalid'
                    errors = _validation_errors_to_list(exc)

                if status == 'valid':
                    self.valid_count += 1
                else:
                    self.invalid_count += 1

                self.firestore_docs.append({
                    'line_item_id': row_data.get('line_item_id'),
                    'creative_id': row_data.get('creative_id'),
                    'status': status,
                    'errors': errors,
                    'row_data': row_data,
                    'validated_at': self.now,
                    'dw_ingested_at': row_data.get('dw_ingested_at')
                })

                self.results.append({
                    'line_item_id': row_data.get('line_item_id'),
                    'status': status,
                    'errors': errors,
                })

            write_validation_batch(self.firestore_docs)

            return {
                'total': len(self.campaign_details.rows),
                'valid': self.valid_count,
                'invalid': self.invalid_count,
                'results': self.results,
            }
        except Exception as e:
            raise ValidateCampaignError(f'Error while running ValidateCampaign: {str(e)}')


class GetCampaigns:
    def get_campaign_list(self, limit: int) -> List[CampaignList]:
        return get_validations(limit)
    
    def get_campaign_details(self, line_item_id: int):
        return get_validations_by_line_item(line_item_id)


class GAMService:
    def update_line_item_targeting(self, params:UpdateTargetingRequest):
        """
        Update the custom targeting segment on a GAM line item (by ID).
        """
        client = _get_ad_manager_client()
        line_item = _fetch_line_item(client, line_item_name=params.line_item_name)
        return line_item
        # return _apply_targeting_update(line_item_service, line_item, body)

    def create_creative(self, line_item_id: int):
        data = GetCampaigns().get_campaign_details(line_item_id)
        campaign = CampaignMetadata(**data[0]['row_data'])
        _create_creative(campaign)



### POLLING SERVICES ###
class PollingBQError(Exception):
    """Custom exception for polling BigQuery operations"""
    pass

class PollingBlueconicError(Exception):
    """Custom exception for polling Blueconic operations"""
    pass

class PollingIterableError(Exception):
    """Custom exception for polling Iterable operations"""
    pass

class Polling:
    def poll_bq(self):
        try:
            date_filter_results = get_most_recent_date()
            date_filter = date_filter_results[0]['dw_ingested_at'] if len(date_filter_results) > 0 else None
            new_rows = _poll_metadata_table(date_filter)
            if len(new_rows) > 0:
                data = ValidateRequest(**{
                    'rows': new_rows
                })

                validatation_process = ValidateCampaign(data)
                validatation_process._process()

                # add notification
                return JSONResponse(status_code=200, content=f'{len(new_rows)} new rows captured and sent for validation.')
            else:
                return JSONResponse(status_code=404, content='No new rows/campaigns found.')
        except Exception as e:
            raise PollingBQError(f'Error running polling BigQuery operation {str(e)}')

    def poll_blueconic(self) -> None:
        try:
            missing_blueconic = get_missing_target_validations('blueconic')
            bc_client = BlueconicAPI()
            bc_segments = bc_client.get_data()
            actual_inserts = []
            missing_campaigns = []
            too_many_segments = []
            zero_profiles = []

            if len(missing_blueconic) > 0:
                for doc in missing_blueconic:
                    line_item_id = doc.get('line_item_id')
                    creative_id = doc.get('creative_id')
                    filtered_segments = filter_list(bc_segments, line_item_id, creative_id)

                    if len(filtered_segments) == 0:
                        segment_info = {
                            'status': 'invalid',
                            'errors': [f'No segments found for line_item_id: {line_item_id} and creative_id: {creative_id}'],
                            'segments': filtered_segments
                        }

                        missing_campaigns.append({ 'line_item_id': line_item_id, 'creative_id': creative_id })
                    elif len(filtered_segments) > 1:
                        segment_info = {
                            'status': 'invalid',
                            'errors': ['Too many segments detected'],
                            'segments': filtered_segments
                        }

                        too_many_segments.append({ 'line_item_id': line_item_id, 'creative_id': creative_id })
                    elif filtered_segments[0].get('profileCount') == 0:
                        segment_info = {
                            'status': 'invalid',
                            'errors': ['Zero profiles associated with segment, log in to Blueconic to redefine the segment.'],
                            'segments': filtered_segments
                        }

                        zero_profiles.append({ 'line_item_id': line_item_id, 'creative_id': creative_id })
                    else:
                        segment_info = {
                            'status': 'valid',
                            'errors': None,
                            'segments': filtered_segments
                        }

                        actual_inserts.append({ 'line_item_id': line_item_id, 'creative_id': creative_id })
                    
                    single_upsert(doc.get('id'), { 'blueconic':  segment_info })
                
                # add notification
                return JSONResponse(status_code=200, content={
                    'actual_inserts': actual_inserts,
                    'missing_campaigns': missing_campaigns,
                    'too_many_segments': too_many_segments,
                    'zero_profiles': zero_profiles,
                    'definition': {
                        'actual_inserts': 'Lists campaigns that were successfully mapped to Blueconic segments during this poll.',
                        'missing_campaigns': 'Lists campaigns that did were not successfully mapped to Blueconic segments during this poll.',
                        'too_many_segments': 'Lists campaigns that found too many Blueconic segments during this poll.',
                        'zero_profiles': 'List campaigns that successfully found Blueconic segments but have zero profiles.'
                    }
                })
            else:
                return JSONResponse(status_code=404, content='All existing campaigns have associated Blueconic segemnts defined.')
        except Exception as e:
            raise PollingBlueconicError(f'Error running polling Blueconic operation {str(e)}')

    def poll_iterable(self) -> None:
        try:
            missing_iterable = get_missing_target_validations('iterable')
            iterable_client = IterableAPI()
            iterable_lists = iterable_client.get_lists()
            found_lists = []
            no_lists = []

            if len(missing_iterable) > 0:
                for doc in missing_iterable:
                    line_item_id = doc.get('line_item_id')
                    creative_id = doc.get('creative_id')
                    filtered_list = filter_list(iterable_lists, doc.get('line_item_id'), doc.get('creative_id'))

                    if len(filtered_list) == 0:
                        iterable_info = {
                            'status': 'invalid',
                            'errors': [f'No Iterable lists found for line_item_id: {line_item_id} and creative_id: {creative_id}'],
                            'lists': None
                        }

                        no_lists.append({ 'line_item_id': line_item_id, 'creative_id': creative_id })
                    else:
                        errors = []
                        status = 'valid'
                        for itb_list in filtered_list:
                            list_id = itb_list.get('id')
                            list_size = iterable_client.get_list_size(list_id)
                            itb_list['size'] = list_size

                            if list_size == 0:
                                errors.append(f'List ID: {list_id} does not have users.') # fix this error message later
                                status = 'invalid'

                        found_lists.append({ 'line_item_id': line_item_id, 'creative_id': creative_id })
                        iterable_info = {
                            'status': status,
                            'errors': errors,
                            'lists': filtered_list
                        }
                
                    single_upsert(doc.get('id'), { 'iterable': iterable_info })

                iterable_client.close_conn()
                # add notification
                return JSONResponse(status_code=200, content={
                    'found_lists': found_lists,
                    'no_lists': no_lists,
                    'definition': {
                        'found_lists': 'Lists campaigns that were successfully mapped to Iterable lists during this poll.',
                        'no_lists': 'Lists campaigns that did were not successfully mapped to Iterable lists during this poll.',
                    }
                })
            else:
                return JSONResponse(status_code=404, content='No Iterable lists found.')
        except Exception as e:
            raise PollingIterableError(f'Error running polling Iterable operation {str(e)}')
