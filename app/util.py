"""Utility functions for tweet wishlist application."""
import re
from datetime import datetime
from typing import Tuple, Optional
import os
from urllib.parse import urlparse


def extract_tweet_id(url: str) -> str:
    """Extract tweet ID from various Twitter/X URL formats.
    
    Args:
        url: Twitter/X URL
        
    Returns:
        Tweet ID
        
    Raises:
        ValueError: If URL format is invalid
    """
    # Remove query parameters
    url = url.split('?')[0]
    
    # Pattern to match various Twitter/X URL formats
    patterns = [
        r'https?://(?:www\.|m\.|mobile\.)?(?:twitter\.com|x\.com)/\w+/status/(\d+)',
        r'https?://(?:www\.|m\.|mobile\.)?(?:twitter\.com|x\.com)/i/web/status/(\d+)',
    ]
    
    for pattern in patterns:
        match = re.match(pattern, url)
        if match:
            return match.group(1)
    
    raise ValueError(f"Invalid Twitter/X URL format: {url}")


def extract_username_and_tweet_id(url: str) -> Tuple[str, str]:
    """Extract username and tweet ID from Twitter/X URL.
    
    Args:
        url: Twitter/X URL
        
    Returns:
        Tuple of (username, tweet_id)
        
    Raises:
        ValueError: If URL format is invalid
    """
    # Remove query parameters
    url = url.split('?')[0]
    
    # Pattern to match username and tweet ID
    pattern = r'https?://(?:www\.|m\.|mobile\.)?(?:twitter\.com|x\.com)/(\w+)/status/(\d+)'
    match = re.match(pattern, url)
    
    if match:
        return match.group(1), match.group(2)
    
    raise ValueError(f"Invalid Twitter/X URL format: {url}")


def format_date(date: datetime) -> str:
    """Format date as YYYY-MM-DD.
    
    Args:
        date: Datetime object
        
    Returns:
        Formatted date string
    """
    return date.strftime('%Y-%m-%d')


def get_year_month(date: datetime) -> str:
    """Get YYYY-MM format from date.
    
    Args:
        date: Datetime object
        
    Returns:
        Year-month string
    """
    return date.strftime('%Y-%m')


def sanitize_text_for_markdown(text: str) -> str:
    """Sanitize text for markdown format.
    
    Args:
        text: Raw text
        
    Returns:
        Sanitized text with proper line breaks
    """
    # First, handle escaped newlines (\n) by converting them to actual newlines
    text = text.replace('\\n', '\n')
    
    # Clean up excessive whitespace on each line while preserving line breaks
    lines = text.split('\n')
    cleaned_lines = [' '.join(line.split()) for line in lines]
    
    # Remove empty lines and rejoin
    cleaned_lines = [line for line in cleaned_lines if line.strip()]
    
    return '\n'.join(cleaned_lines)


def determine_file_extension(url: str) -> str:
    """Determine file extension from URL.
    
    Args:
        url: Image URL
        
    Returns:
        File extension (jpg, jpeg, png, webp)
    """
    # Parse URL and get the path
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    # Check for common image extensions
    for ext in ['jpg', 'jpeg', 'png', 'webp']:
        if path.endswith(f'.{ext}'):
            return ext
    
    # Default to jpg if no extension found
    return 'jpg'


def generate_image_filename(tweet_id: str, sequence: int, url: str) -> str:
    """Generate image filename.
    
    Args:
        tweet_id: Tweet ID
        sequence: Image sequence number
        url: Image URL
        
    Returns:
        Filename like {tweetId}_{seq}.{ext}
    """
    ext = determine_file_extension(url)
    return f"{tweet_id}_{sequence}.{ext}"


def generate_image_path(date: datetime, filename: str, assets_dir: str = "assets") -> str:
    """Generate full image path.
    
    Args:
        date: Current date
        filename: Image filename
        assets_dir: Base assets directory
        
    Returns:
        Path like assets/YYYY-MM/filename
    """
    year_month = get_year_month(date)
    return f"{assets_dir}/{year_month}/{filename}"