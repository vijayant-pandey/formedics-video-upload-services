uuid_pattern = {
    "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    "description": "Must be a valid UUID string"
}

generic_int_pattern = {
    "type": "number",
    "description": "Must be a number"
}

generic_str_pattern = {
    "type": "string",
    "description": "Must be a string"
}

generic_url_pattern = {
    "pattern": "^https?://",
    "description": "Must be a valid URL starting with http:// or https://"
}

generic_float_pattern = {
    "pattern": "^\d*\.?\d+$",
    "description": "Must be a decimal number"
}

video_parameters = {
    "bc_id": uuid_pattern,
    "line_item_id": generic_int_pattern,
    "vguid": uuid_pattern,
    "video_account": generic_int_pattern,
    "video_destination": generic_url_pattern,
    "video_duration": generic_float_pattern,
    "video_id": generic_int_pattern,
    "video_milestones": generic_int_pattern,
    "video_name": generic_str_pattern,
    "video_range": generic_float_pattern,
    "video_percent_viewed": generic_int_pattern,
    "video_platform_version": generic_str_pattern,
    "video_player_id": generic_str_pattern,
    "video_player_name": generic_str_pattern,
    "video_playhead": generic_int_pattern,
    "video_seconds_viewed": generic_int_pattern,
    "video_session_id": generic_str_pattern
}

audio_parameters = {
    "audio_account": generic_int_pattern,
    "audio_destination": generic_url_pattern,
    "audio_duration": generic_float_pattern,
    "audio_id": generic_int_pattern,
    "audio_milestones": generic_int_pattern,
    "audio_name": generic_str_pattern,
    "audio_range": generic_float_pattern,
    "audio_percent_viewed": generic_int_pattern,
    "audio_platform_version": generic_str_pattern,
    "audio_player_id": generic_str_pattern,
    "audio_player_name": generic_str_pattern,
    "audio_playhead": generic_int_pattern,
    "audio_seconds_viewed": generic_int_pattern,
    "audio_session_id": generic_str_pattern,
    "bc_id": uuid_pattern,
    "line_item_id": generic_int_pattern,
    "vguid": uuid_pattern
}

valid_events = ["audio_complete", "audio_engagement", "audio_error", "audio_impression", "audio_impression", "audio_play_request",
                "audio_start", "bcid_page_view", "cust_ad_impression", "cust_ad_click", "formedics_engage", "page_view",
                "video_complete", "video_engagement", "video_error", "video_impression", "video_impression", "video_play_request",
                "video_start", "f1_content_widget_click", "f1_content_widget_impression"]

tracking_rules = {
    "version": "1.1.0",
    "events": valid_events,
    "rules": {
        "description": "Sample validation rules for GA4 events",
        "events": {
            "audio_complete": {
                "description": "Brightcove audio_complete event validation",
                "required": ["bc_id", "audio_account", "audio_destination", "audio_id", "audio_name", "audio_platform_version",
                            "audio_player_id", "audio_player_name", "audio_session_id"],
                "parameters": audio_parameters
            },
            "audio_engagement": {
                "description": "Audio engagement event validation",
                "required": ["bc_id", "audio_account", "audio_destination", "audio_duration", "audio_id", "audio_milestones",
                            "audio_name", "audio_percent_viewed", "audio_platform_version", "audio_player_id", "audio_player_name",
                            "audio_playhead", "audio_seconds_viewed", "audio_session_id"],
                "parameters": audio_parameters
            },
            "audio_error": {
                "description": "Audio error event validation",
                "required": ["bc_id", "audio_account", "audio_destination", "audio_id","audio_name", "audio_platform_version",
                            "audio_player_id", "audio_player_name","audio_session_id"],
                "parameters": audio_parameters
            },
            "audio_impression": {
                "description": "Audio impression event validation",
                "required": ["bc_id", "audio_account", "audio_destination", "audio_id","audio_name", "audio_platform_version",
                            "audio_player_id", "audio_player_name","audio_session_id"],
                "parameters": audio_parameters
            },
            "audio_play_request": {
                "description": "Audio play event validation",
                "required": ["bc_id", "audio_account", "audio_destination", "audio_id","audio_name", "audio_platform_version",
                            "audio_player_id", "audio_player_name","audio_session_id"],
                "parameters": audio_parameters
            },
            "audio_start": {
                "description": "Audio start event validation",
                "required": ["bc_id", "audio_account", "audio_destination", "audio_id","audio_name", "audio_platform_version",
                            "audio_player_id", "audio_player_name","audio_session_id"],
                "parameters": audio_parameters
            },
            "bcid_page_view": {
                "description": "Blueconic page view event validation",
                "required": ["bcId", "page_location", "page_title"],
                "parameters": {
                    "bcId": uuid_pattern,
                    "page_location": generic_url_pattern,
                    "page_title": generic_str_pattern
                }
            }, 
            "cust_ad_impression": {
                "description": "Custom GAM Ad Impression",
                "required": ["bc_id", "gam_creative_id", "gam_line_item_id", "gam_order_id", "slot_name"],
                "parameters": {
                    "bc_id": uuid_pattern,
                    "gam_creative_id": generic_str_pattern,
                    "gam_line_item_id": generic_int_pattern,
                    "gam_order_id": generic_int_pattern,
                    "slot_name": generic_str_pattern,
                    "vguid": uuid_pattern
                }
            },
            "cust_ad_click": {
                "description": "Custom GAM Ad Click",
                "required": ["bc_id", "gam_creative_id", "gam_line_item_id", "gam_order_id", "slot_name"],
                "parameters": {
                    "bc_id": uuid_pattern,
                    "gam_creative_id": generic_str_pattern,
                    "gam_line_item_id": generic_int_pattern,
                    "gam_order_id": generic_int_pattern,
                    "slot_name": generic_str_pattern,
                    "vguid": uuid_pattern
                }
            },
            "page_view": {
                "description": "Page view event validation",
                "required": ["page_location", "page_title"],
                "parameters": {
                    "page_location": generic_str_pattern,
                    "page_title": generic_str_pattern,
                }
            },
            "formedics_engage": {
                "description": "Formedics event validation",
                "required": ["bc_id", "interaction_type", "engagement_type"],
                "parameters": {
                    "bc_id": uuid_pattern,
                    "creative_id": {
                        "pattern": "^.*$",
                        "description": "Part of the original spec but i don't believe it was ever used."
                    },
                    "engagement_type": {
                        "pattern": "^(bm_engage|bn_engage)$",
                        "description": "Must be one of the following (bn_engage, bm_engage)"
                    },
                    "interaction_type": {
                        "pattern": "^(interstitial|interstitial-click|interstitial-close|native-activate|native-imp)$",
                        "description": "Must be one of the following (interstitial, interstitial-click, interstitial-close, native-activate, native-imp)"
                    },
                    "line_item_id": {
                        "pattern": "^\d{7}$",
                        "description": "Must be a number with seven digits"
                    }
                }
            },
            "video_complete": {
                "description": "Brightcove video_complete event validation",
                "required": ["bc_id", "video_account", "video_destination", "video_id", "video_name", "video_platform_version",
                            "video_player_id", "video_player_name", "video_session_id"],
                "parameters": video_parameters
            },
            "video_engagement": {
                "description": "Video engagement event validation",
                "required": ["bc_id", "video_account", "video_destination", "video_duration", "video_id", "video_milestones",
                            "video_name", "video_percent_viewed", "video_platform_version", "video_player_id", "video_player_name",
                            "video_playhead", "video_seconds_viewed", "video_session_id"],
                "parameters": video_parameters
            },
            "video_error": {
                "description": "Video error event validation",
                "required": ["bc_id", "video_account", "video_destination", "video_id","video_name", "video_platform_version",
                            "video_player_id", "video_player_name","video_session_id"],
                "parameters": video_parameters
            },
            "video_impression": {
                "description": "Video impression event validation",
                "required": ["bc_id", "video_account", "video_destination", "video_id","video_name", "video_platform_version",
                            "video_player_id", "video_player_name","video_session_id"],
                "parameters": video_parameters
            },
            "video_play_request": {
                "description": "Video play event validation",
                "required": ["bc_id", "video_account", "video_destination", "video_id","video_name", "video_platform_version",
                            "video_player_id", "video_player_name","video_session_id"],
                "parameters": video_parameters
            },
            "video_start": {
                "description": "Video start event validation",
                "required": ["bc_id", "video_account", "video_destination", "video_id","video_name", "video_platform_version",
                            "video_player_id", "video_player_name","video_session_id"],
                "parameters": video_parameters
            },
            "f1_content_widget_click": {
                "description": "Events specific to the F1 Content Widget",
                "required": ["case_id", "property", "title"],
                "parameters": {
                    "case_id": uuid_pattern,
                    "property": generic_str_pattern,
                    "title": generic_str_pattern
                }
            },
            "f1_content_widget_impression": {
                "description": "Events specific to the F1 Content Widget",
                "required": ["case_id", "title", "property"],
                "parameters": {
                    "case_id": uuid_pattern,
                    "property": generic_str_pattern,
                    "title": generic_str_pattern
                }
            }
        },
        "global_rules": {
            "description": "Rules that apply to all events",
            "parameters": {
                "page_location": generic_url_pattern
            }
        }
    }
}