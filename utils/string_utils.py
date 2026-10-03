def clean_text(text):
    """Remove non-BMP characters that ChromeDriver doesn't support."""
    if not text:
        return ""
    return ''.join(c for c in str(text) if ord(c) <= 0xFFFF)
