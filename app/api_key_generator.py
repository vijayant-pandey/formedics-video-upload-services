import secrets


def generate_api_key(length=32):
    """
    Generates a cryptographically strong, URL-safe API key.

    Args:
        length (int): The desired length of the API key in bytes.
                      The resulting string length will be longer due to base64 encoding.

    Returns:
        str: The generated API key.
    """
    return secrets.token_urlsafe(length)

# Example usage:
api_key = generate_api_key(32)
print(f"Generated API Key: {api_key}")
