# Patch for Flask-Login to use urllib.parse instead of Werkzeug URL decoding
import logging
from urllib.parse import parse_qs

def url_decode(query_string, *args, **kwargs):
    """
    Replacement for Werkzeug's url_decode using urllib.parse
    
    Args:
        query_string (str): URL-encoded query string
    
    Returns:
        dict: Decoded query parameters
    """
    return parse_qs(query_string, *args, **kwargs)

# Monkey patch flask_login.utils to use our custom url_decode
try:
    import flask_login.utils
    flask_login.utils.url_decode = url_decode
    logging.info("Successfully patched flask_login.utils.url_decode")
except ImportError as e:
    logging.error(f"Could not import flask_login.utils: {e}")
    raise
