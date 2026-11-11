def slugify(text: str) -> str:
    """
    Converts text to a URL-friendly slug by lowercasing, replacing spaces with hyphens,
    and removing non-alphanumeric characters.
    
    Args:
        text: The input text string
        
    Returns:
        A URL-friendly slug string
    """
    # Convert to lowercase
    slug = text.lower()
    
    # Replace spaces with hyphens
    slug = slug.replace(' ', '-')
    
    # Remove all non-alphanumeric characters except hyphens
    slug = ''.join(c if c.isalnum() or c == '-' else '' for c in slug)
    
    # Strip leading and trailing hyphens
    slug = slug.strip('-')
    
    return slug
