from googleads import ad_manager
from googleads import oauth2
from .dtypes import *
from pydantic_core import Url
import os
import tempfile
from google.cloud import secretmanager
from json import dumps
from .gcs_helper import *


GAM_API_VERSION = 'v202511'
APPLICATION_NAME = 'UMP (Test)'
NETWORK_CODE = os.environ.get('GAM_NETWORK')
PROJECT_ID = os.getenv('GCP_PROJECT_ID', 'pw-datahub')
SECRET_NAME = 'datahub_gam_sa_key'
SECRET_VERSION = 'latest'


def _get_service_account_json() -> str:
    """Fetch the service account JSON from Google Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    secret_path = f'projects/{PROJECT_ID}/secrets/{SECRET_NAME}/versions/{SECRET_VERSION}'
    response = client.access_secret_version(request={'name': secret_path})
    return response.payload.data.decode('UTF-8')


def _get_ad_manager_client() -> ad_manager.AdManagerClient:
    """Load the Ad Manager client using service account from Secret Manager."""
    sa_json = _get_service_account_json()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(sa_json)
        temp_key_file = f.name

    try:
        oauth2_client = oauth2.GoogleServiceAccountClient(
            temp_key_file,
            oauth2.GetAPIScope('ad_manager')
        )
        client = ad_manager.AdManagerClient(
            oauth2_client,
            APPLICATION_NAME,
            network_code=NETWORK_CODE
        )
        return client
    finally:
        if os.path.exists(temp_key_file):
            os.unlink(temp_key_file)


def _fetch_line_item(client, line_item_id: int | None = None, line_item_name: str | None = None):
    """Fetch a single line item by ID or by exact name."""
    line_item_service = client.GetService('LineItemService', version=GAM_API_VERSION)
    if line_item_id is not None:
        statement = (
            ad_manager.StatementBuilder(version=GAM_API_VERSION)
                .Where('id = :lineItemId')
                .WithBindVariable('lineItemId', line_item_id)
                .Limit(1)
        )
        not_found_msg = f'Line item {line_item_id} not found in GAM'
    elif line_item_name is not None:
        statement = (
            ad_manager.StatementBuilder(version=GAM_API_VERSION)
                .Where('name = :name')
                .WithBindVariable('name', line_item_name)
                .Limit(2)  # fetch 2 to detect ambiguity
        )
        not_found_msg = f'Line item with name "{line_item_name}" not found in GAM'
    else:
        raise ValueError('Provide either line_item_id or name')

    response = line_item_service.getLineItemsByStatement(statement.ToStatement())

    if 'results' not in response or not response['results']:
        raise ValueError(not_found_msg)

    if line_item_name is not None and len(response['results']) > 1:
        raise ValueError(f'Multiple line items match name "{line_item_name}". Use the ID-based endpoint instead.')

    return response['results'][0]


def _apply_targeting_update(client, line_item, body: UpdateTargetingRequest) -> dict:
    """Build a CustomCriteriaSet from the request, apply it, and persist."""
    children = [
        {
            'xsi_type': 'CustomCriteria',
            'keyId': c.key_id,
            'valueIds': c.value_ids,
            'operator': c.operator,
        }
        for c in body.criteria
    ]

    new_targeting_set = {
        'xsi_type': 'CustomCriteriaSet',
        'logicalOperator': body.logical_operator,
        'children': children,
    }

    if body.mode == 'append':
        existing_targeting = line_item['targeting'].get('customTargeting')
        
        if existing_targeting:
            combined_targeting = {
                'xsi_type': 'CustomCriteriaSet',
                'logicalOperator': body.append_operator,
                'children': [existing_targeting, new_targeting_set],
            }
            line_item['targeting']['customTargeting'] = combined_targeting
        else:
            line_item['targeting']['customTargeting'] = new_targeting_set
    else:
        line_item['targeting']['customTargeting'] = new_targeting_set

    updated = client.GetService('LineItemService', version=GAM_API_VERSION).updateLineItems([line_item])
    
    if not updated:
        raise ValueError('GAM updateLineItems returned no results')

    updated_item = updated[0]

    return {
        'line_item_id': updated_item['id'],
        'name': updated_item['name'],
        'custom_targeting': updated_item['targeting']['customTargeting'],
    }


def _create_creative(client, campaign_details:CampaignMetadata) -> TemplateCreativeModel:
    # creative_service = client.GetService('CreativeService', version=GAM_API_VERSION)
    template_creative:TemplateCreativeModel = {
        'xsi_type': 'TemplateCreative',
        'name': 'My Template Creative - Campaign A',
        'advertiserId': '5023939158', # 5023939158 is a test advertiser, change this later, where is the advertiserId/companyId going to come from?
        'size': { 'width': '300', 'height': '250' },
        'creativeTemplateId': '12510473', # Brand Notify Updated Jan 2026 - https://admanager.google.com/35215761#creatives/creative_template/detail/template_id=12510473
        
        # 'creativeTemplateVariableValues': [
        #     {
        #         'xsi_type': 'StringCreativeTemplateVariableValue',
        #         'uniqueName': 'Headline',  # Must match the template variable name
        #         'value': 'Summer Sale - 50% Off!'
        #     },
        #     {
        #         # For a "URL" variable
        #         'xsi_type': 'UrlCreativeTemplateVariableValue',
        #         'uniqueName': 'ClickThroughURL',
        #         'value': 'https://example.com/sale'
        #     },
        #     {
        #         # For a "File" variable (requires a CreativeAsset)
        #         'xsi_type': 'AssetCreativeTemplateVariableValue',
        #         'uniqueName': 'MainImage',
        #         'asset': {
        #             'xsi_type': 'CreativeAsset',
        #             'assetByteArray': base64_image_data, # Bytes of your image
        #             'fileName': 'banner.png'
        #         }
        #     }
        # ]
    }

    template_vars = []

    for name, field in campaign_details.model_fields.items():
        display_name = field.alias or name 
        value = getattr(campaign_details, name)
        template_variable = {
            'uniqueName': display_name, # match the template variable name
        }

        xsi_type = 'StringCreativeTemplateVariableValue'
        if isinstance(value, int): xsi_type = 'LongCreativeTemplateVariableValue'
        if isinstance(value, Url): xsi_type = 'UrlCreativeTemplateVariableValue'
        if name == 'logo_image_url':
            bucket, blob, filename = parse_non_gcs_url(value)
            base64_image = get_base64_image(bucket, blob)
            xsi_type = 'AssetCreativeTemplateVariableValue'
            template_variable['asset'] = {
                'xsi_type': 'CreativeAsset',
                'assetByteArray': base64_image,
                'fileName': filename
            }
        else:
            template_variable['value'] = value

        template_variable['xsi_type'] = xsi_type
        template_vars.append(template_variable)

    template_creative['creativeTemplateVariableValues'] = template_vars

    print(dumps(template_creative, indent=4, default=str))
    # new_creative_resp = creative_service.createCreatives([template_creative])

    # return new_creative_resp

# def update_line_item_by_name():



#     client = _get_ad_manager_client()
#     line_item_service = client.GetService('LineItemService', version=GAM_API_VERSION)

#     # Fetch the line item by ID
#     statement = (
#         ad_manager.StatementBuilder(version=GAM_API_VERSION)
#         .Where("id = :lineItemId")
#         .WithBindVariable("lineItemId", line_item_id)
#         .Limit(1)
#     )
#     response = line_item_service.getLineItemsByStatement(statement.ToStatement())

#     if "results" not in response or not response["results"]:
#         raise HTTPException(status_code=404, detail=f"Line item {line_item_id} not found in GAM")

#     line_item = response["results"][0]

#     # Build the CustomCriteriaSet from the request body
#     children = [
#         {
#             "xsi_type": "CustomCriteria",
#             "keyId": c.key_id,
#             "valueIds": c.value_ids,
#             "operator": c.operator,
#         }
#         for c in body.criteria
#     ]

#     targeting_set = {
#         "xsi_type": "CustomCriteriaSet",
#         "logicalOperator": body.logical_operator,
#         "children": children,
#     }

#     line_item["targeting"]["customTargeting"] = targeting_set

#     # Persist the update
#     updated = line_item_service.updateLineItems([line_item])
#     if not updated:
#         raise HTTPException(status_code=500, detail="GAM updateLineItems returned no results")

#     updated_item = updated[0]
#     return {
#         "line_item_id": updated_item["id"],
#         "name": updated_item["name"],
#         "custom_targeting": updated_item["targeting"]["customTargeting"],
#     }