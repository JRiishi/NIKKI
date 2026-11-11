import re


def slugify(text: str) -> str:
    """
    Convert text to a URL-friendly slug.
    
    Args:
        text: Input string to convert
    
    Returns:
        Lowercase string with spaces replaced by hyphens and non-alphanumeric
        characters removed (except hyphens)
    """
    # Lowercase the text
    slug = text.lower()
    
    # Replace spaces with hyphens
    slug = slug.replace(' ', '-')
    
    # Remove non-alphanumeric characters except hyphens
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    
    return slug
