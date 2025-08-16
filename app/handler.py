"""AWS Lambda handler for tweet wishlist ingestion."""
import json
import logging
import os
import boto3
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
import requests

from twitter_client import TwitterClient
from github_client import GitHubClient
from model import WishlistEntry
from util import (
    format_date, 
    sanitize_text_for_markdown,
    generate_image_path,
    extract_tweet_id
)

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
secrets_client = boto3.client('secretsmanager')


class EntryType(Enum):
    """Type of wishlist entry."""
    BOOK = "book"
    LIKED = "liked"


def get_secret(secret_name: str) -> Dict[str, str]:
    """Retrieve secret from AWS Secrets Manager.
    
    Args:
        secret_name: Name of the secret
        
    Returns:
        Secret values as dict
    """
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        logger.error(f"Failed to retrieve secret {secret_name}: {e}")
        raise


def validate_request(event: Dict[str, Any]) -> tuple:
    """Validate incoming request.
    
    Args:
        event: Lambda event
        
    Returns:
        Tuple of (url, note)
        
    Raises:
        ValueError: If validation fails
    """
    # Parse body
    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON in request body")
    
    # Validate URL
    url = body.get('url', '').strip()
    if not url:
        raise ValueError("URL is required")
    
    # Basic URL validation
    if not url.startswith(('https://twitter.com/', 'https://x.com/', 
                          'https://mobile.twitter.com/', 'https://mobile.x.com/',
                          'https://www.twitter.com/', 'https://www.x.com/')):
        raise ValueError("Invalid Twitter/X URL")
    
    # Get optional note
    note = body.get('note', '').strip()
    if note and len(note) > 500:  # Reasonable limit
        raise ValueError("Note is too long (max 500 characters)")
    
    return url, note


def get_entry_type(event: Dict[str, Any]) -> EntryType:
    """Determine entry type from Lambda event path.
    
    Args:
        event: Lambda event
        
    Returns:
        EntryType enum value
    """
    # API Gateway v2 uses rawPath, v1 uses path
    path = event.get('rawPath', event.get('path', ''))
    
    if '/liked' in path:
        return EntryType.LIKED
    return EntryType.BOOK


def check_api_key(event: Dict[str, Any], expected_key: Optional[str]) -> bool:
    """Check API key if configured.
    
    Args:
        event: Lambda event
        expected_key: Expected API key
        
    Returns:
        True if valid or not required
    """
    if not expected_key:
        return True
    
    headers = event.get('headers', {})
    provided_key = headers.get('x-api-key', headers.get('X-Api-Key', ''))
    
    return provided_key == expected_key


def format_wishlist_entry(entry: WishlistEntry, entry_type: EntryType = EntryType.BOOK) -> str:
    """Format wishlist entry as markdown.
    
    Args:
        entry: WishlistEntry object
        entry_type: Type of entry (BOOK or LIKED)
        
    Returns:
        Formatted markdown string
    """
    lines = []
    
    # Main entry line
    main_line = f"- {entry.date} [{entry.title}]({entry.url})"
    if entry.note:
        main_line += f" note: {entry.note}"
    lines.append(main_line)
    
    # Tweet text
    sanitized_text = sanitize_text_for_markdown(entry.tweet_text)
    lines.append(f"  - text: {sanitized_text}")
    
    # Original link
    lines.append(f"  - original: {entry.url}")
    
    # Images
    if entry.images:
        lines.append("  - images:")
        for image in entry.images:
            # Use different assets directory based on entry type
            assets_dir = os.environ.get(
                'VAULT_LIKED_ASSETS_DIR' if entry_type == EntryType.LIKED else 'VAULT_ASSETS_DIR',
                'Liked/assets' if entry_type == EntryType.LIKED else 'assets'
            )
            image_path = generate_image_path(
                datetime.now(),
                image.filename,
                assets_dir
            )
            lines.append(f"    - [[{image_path}]]")
    
    return '\n'.join(lines)


def download_image(url: str) -> bytes:
    """Download image from URL.
    
    Args:
        url: Image URL
        
    Returns:
        Image data as bytes
    """
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler.
    
    Args:
        event: Lambda event
        context: Lambda context
        
    Returns:
        API response
    """
    try:
        # Get configuration from environment
        secret_name = os.environ.get('SECRET_NAME', 'tweet-wishlist-secrets')
        secrets = get_secret(secret_name)
        
        # Check API key if configured
        api_key = secrets.get('API_KEY')
        if not check_api_key(event, api_key):
            return {
                'statusCode': 401,
                'body': json.dumps({
                    'status': 'error',
                    'message': 'Unauthorized'
                })
            }
        
        # Validate request
        try:
            url, note = validate_request(event)
            tweet_id = extract_tweet_id(url)
        except ValueError as e:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'status': 'error',
                    'message': str(e)
                })
            }
        
        logger.info(f"Processing tweet {tweet_id}")
        
        # Determine entry type
        entry_type = get_entry_type(event)
        logger.info(f"Entry type: {entry_type.value}")
        
        # Initialize clients
        twitter_client = TwitterClient()
        github_client = GitHubClient(
            token=secrets['GITHUB_TOKEN'],
            owner=secrets.get('GITHUB_OWNER', os.environ.get('GITHUB_OWNER')),
            repo=secrets.get('GITHUB_REPO', os.environ.get('GITHUB_REPO')),
            branch=secrets.get('GITHUB_BRANCH', os.environ.get('GITHUB_BRANCH', 'main'))
        )
        
        # Fetch tweet data
        try:
            tweet = twitter_client.fetch_tweet(url)
        except Exception as e:
            logger.error(f"Failed to fetch tweet: {e}")
            return {
                'statusCode': 502,
                'body': json.dumps({
                    'status': 'error',
                    'message': 'Failed to fetch tweet data',
                    'tweetId': tweet_id
                })
            }
        
        # Validate tweet has content
        if not tweet.text and not tweet.images:
            return {
                'statusCode': 422,
                'body': json.dumps({
                    'status': 'error',
                    'message': 'Tweet has no text or images',
                    'tweetId': tweet_id
                })
            }
        
        # Prepare wishlist entry
        current_date = datetime.now()
        entry = WishlistEntry(
            date=format_date(current_date),
            title=f"@{tweet.author_username or 'unknown'}",
            url=url,
            note=note if note else None,
            tweet_text=tweet.text,
            images=tweet.images
        )
        
        commits = []
        
        # Upload images first
        for image in tweet.images:
            try:
                logger.info(f"Downloading image {image.url}")
                image_data = download_image(image.url)
                
                # Use different assets directory based on entry type
                assets_dir = os.environ.get(
                    'VAULT_LIKED_ASSETS_DIR' if entry_type == EntryType.LIKED else 'VAULT_ASSETS_DIR',
                    'Liked/assets' if entry_type == EntryType.LIKED else 'assets'
                )
                image_path = generate_image_path(
                    current_date,
                    image.filename,
                    assets_dir
                )
                
                logger.info(f"Uploading image to {image_path}")
                github_client.upload_image(
                    path=image_path,
                    image_data=image_data,
                    message=f"chore: add tweet images {tweet_id}"
                )
                commits.append(image_path)
                
            except Exception as e:
                logger.error(f"Failed to process image {image.url}: {e}")
                # Continue with other images
        
        # Append to wishlist
        wishlist_path = os.environ.get(
            'VAULT_LIKED_PATH' if entry_type == EntryType.LIKED else 'VAULT_WISHLIST_PATH',
            'Liked/tweets.md' if entry_type == EntryType.LIKED else 'wishlist.md'
        )
        wishlist_content = format_wishlist_entry(entry, entry_type)
        
        try:
            github_client.append_to_file(
                path=wishlist_path,
                content_to_append=wishlist_content + '\n',
                message=f"chore: append {'liked tweet' if entry_type == EntryType.LIKED else 'wishlist'} {format_date(current_date)} ({tweet_id})"
            )
            commits.append(wishlist_path)
        except Exception as e:
            logger.error(f"Failed to update wishlist: {e}")
            if "Conflict" in str(e):
                return {
                    'statusCode': 409,
                    'body': json.dumps({
                        'status': 'error',
                        'message': 'Concurrent update conflict, please retry',
                        'tweetId': tweet_id
                    })
                }
            raise
        
        # Success response
        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'success',
                'message': 'Tweet added to wishlist',
                'tweetId': tweet_id,
                'commits': commits
            })
        }
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'message': 'Internal server error'
            })
        }