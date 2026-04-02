import re


def parse_kv_string(s: str) -> dict:
    pairs = re.split(r'[\n, ]+', s.strip())
    return {
        k.lower().replace('-', '_'): v
        for pair in pairs if '=' in pair
        for k, v in [pair.split('=', 1)]
    }


def filter_list(target_list: dict, line_item_id: int, creative_id: int):
    filtered_list = []
    for list in target_list:
        if list.get('description'):
            parse_desc = parse_kv_string(list.get('description'))
            if parse_desc.get('line_item_id') == line_item_id \
                and parse_desc.get('creative_id') == creative_id:
                filtered_list.append(list)
           
    return filtered_list
