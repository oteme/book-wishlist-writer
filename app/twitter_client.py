"""Twitter/X client using vxtwitter API."""
import logging
from typing import List, Optional
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from model import Tweet, TweetImage
from util import extract_tweet_id, extract_username_and_tweet_id, generate_image_filename

logger = logging.getLogger(__name__)


class TwitterClient:
    """Client for fetching tweet data via vxtwitter API."""
    
    def __init__(self, vxtwitter_base_url: str = "https://api.vxtwitter.com"):
        """Initialize Twitter client.
        
        Args:
            vxtwitter_base_url: Base URL for vxtwitter API
        """
        self.base_url = vxtwitter_base_url
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry logic."""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
    
    def fetch_tweet(self, url: str) -> Tweet:
        """Fetch tweet data from URL.
        
        Args:
            url: Twitter/X URL
            
        Returns:
            Tweet object with text and images
            
        Raises:
            ValueError: If URL is invalid
            requests.RequestException: If API call fails
        """
        username, tweet_id = extract_username_and_tweet_id(url)
        logger.info(f"Fetching tweet {tweet_id}")
        
        # Call vxtwitter API with correct format
        api_url = f"{self.base_url}/{username}/status/{tweet_id}"
        try:
            response = self.session.get(api_url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch tweet {tweet_id}: {e}")
            raise
        
        data = response.json()
        
        # Extract tweet text
        tweet_text = data.get('text', '')
        if not tweet_text:
            raise ValueError(f"No text found for tweet {tweet_id}")
        
        # Extract author info
        author_name = data.get('user_name', '')
        author_username = data.get('user_screen_name', '')
        
        # Extract images
        images = self._extract_images(data, tweet_id)
        
        return Tweet(
            tweet_id=tweet_id,
            text=tweet_text,
            images=images,
            author_name=author_name,
            author_username=author_username
        )
    
    def _extract_images(self, data: dict, tweet_id: str) -> List[TweetImage]:
        """Extract image URLs from tweet data.
        
        Args:
            data: Raw API response
            tweet_id: Tweet ID
            
        Returns:
            List of TweetImage objects
        """
        images = []
        
        # Check for media_extended array
        media_list = data.get('media_extended', [])
        if not media_list:
            # Fallback to mediaURLs if available
            media_urls = data.get('mediaURLs', [])
            media_list = [{'url': url} for url in media_urls]
        
        for idx, media in enumerate(media_list):
            # Get the highest quality image URL
            url = media.get('url', '')
            if not url:
                continue
            
            # Look for original quality URL if available
            if 'altText' in media and 'url' in media:
                # vxtwitter sometimes provides higher res in different fields
                original_url = media.get('url', '').replace('name=small', 'name=orig')
                original_url = original_url.replace('name=medium', 'name=orig')
                original_url = original_url.replace('name=large', 'name=orig')
                url = original_url
            
            filename = generate_image_filename(tweet_id, idx + 1, url)
            images.append(TweetImage(url=url, filename=filename))
        
        return images