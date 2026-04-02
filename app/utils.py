import regex as re
from bs4 import BeautifulSoup
from html2text import html2text
import logging
from fastapi import Request, HTTPException
from bson import ObjectId
from datetime import datetime


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Function to verify/filter IP address when necessary.
# This should NOT be used for security checks.
# Create proper authentication for security.
def verify_ip_main(allowed_ips: set[str]):
    def verify_ip(request: Request):
        if not allowed_ips:
            raise HTTPException(status_code=400, detail={'error':'ALLOWED_IPS is empty'})
        forwarded_ip = request.headers.get("X-Forwarded-For")
        ip = forwarded_ip.split(",")[0].strip() if forwarded_ip else request.client.host
        if ip not in allowed_ips:
            logger.warning(f"IP {ip} is not allowed")
            raise HTTPException(status_code=403, detail={'error':f'IP {ip} not authorized'})
    return verify_ip


# Validate mongo pipeline - This just checks for known operators that usually exists in Mongo aggregate pipeline
def is_valid_mongo_pipeline(pipeline: list) -> bool:
    if not isinstance(pipeline, list):
        return False

    valid_operators = {
        '$match', '$project', '$group', '$sort', '$limit',
        '$skip', '$unwind', '$lookup', '$addFields',
        '$replaceRoot', '$count', '$facet', '$unset'
    }

    for stage in pipeline:
        if not isinstance(stage, dict) or len(stage) != 1:
            return False
        op = next(iter(stage))
        if op not in valid_operators:
            return False

    return True


# Fixes nested objectIds from mongodb results.
def convert_mongo_types(obj):
    if isinstance(obj, list):
        return [convert_mongo_types(i) for i in obj]
    elif isinstance(obj, dict):
        return {
            k: convert_mongo_types(v) for k, v in obj.items()
        }
    elif isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj


def rename_props(data, render_html=False):
    output = []

    for d in data:
        new_dict = {}
        for key, value in d.items():
            new_val = value
            if isinstance(value, dict):
                new_x_dict = {}
                for xkey, xvalue in value.items():
                    new_key = xkey.replace('@','').replace('#','').replace(':','').replace('-','_')
                    new_x_dict[new_key] = xvalue
                new_val = new_x_dict

            if ':' in key or '-' in key:
                if key == 'post-thumbnail':
                    new_dict['media_content'] = value
                else:
                    if key == 'content:encoded':
                        new_dict[key.replace(':', '_').replace('-','_')] = value

                        if render_html:
                            new_text = html2text(new_val)
                        else:
                            new_text = BeautifulSoup(new_val, 'html.parser').text.replace('\n', ' ').strip()
                            new_text = ' '.join(new_text.split())

                        new_dict['content_plain_txt'] = new_text
                    else:
                        new_dict[key.replace(':', '_').replace('-','_')] = new_val.strip()
            elif key == 'description':
                if value != None:
                    new_dict[key] = BeautifulSoup(value, 'html.parser').text.replace('\n', ' ')
                else:
                    new_dict[key] = value
            else:
                new_dict[key] = new_val

        output.append(new_dict)
    
    return output


def remove_last_sentence(data):
    for d in data:
        if d['description'] == None: continue

        d['original_description'] = ''.join(d['description'])

        if '[…]' in d['description']:
            d['description'] = d['description'].split('[…]')[0].strip() +  ' […]'
            continue

        sentence_boundary = r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s'
        sentences = re.split(sentence_boundary, d['description'])

        if len(sentences) < 2: continue

        d['description'] = ''.join(sentences[:-1]).strip()

    return data


def extract_first_sentence(text: str) -> str:
    # List of common abbreviations that should not be treated as sentence endings
    abbreviations = [
        "Mr", "Mrs", "Ms", "Dr", "Prof", "PhD", "MD", "NP", "Jr", "Sr", "St", "vs", "etc", "Fig", "Inc", "Ltd", "e.g", "i.e"
    ]
    
    # Create a non-capturing group of the abbreviations for use in negative lookbehind
    abbrev_pattern = '|'.join(re.escape(abbrev) for abbrev in abbreviations)

    # Regex to find the first sentence ending punctuation that is not preceded by a known abbreviation
    sentence_end_re = re.compile(
        rf"""
        # Match any character until we hit the first sentence-ending punctuation
        (
            .*?                             # non-greedy capture of characters
            (?<!\b(?:{abbrev_pattern}))     # not preceded by known abbreviations
            [.!?]                           # ends with period, exclamation, or question mark
        )
        \s+                                # followed by whitespace
        [A-Z0-9"“]                         # and a capital letter or quote (start of next sentence)
        """,
        re.VERBOSE | re.DOTALL
    )

    if text:
        match = sentence_end_re.search(text)
        if match:
            return match.group(1).strip()
        else:
            # Fallback: return the whole paragraph if no match is found
            return text.strip()
    else:
        return text


def remove_abstract_content(data):
    for d in data:
        if d['description'] == None: continue
        d['description'] = extract_first_sentence(d['description'])
            
    return data
