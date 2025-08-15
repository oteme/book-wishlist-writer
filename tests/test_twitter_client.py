"""Tests for Twitter client."""
import pytest
from unittest.mock import Mock, patch
import requests

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from twitter_client import TwitterClient
from model import Tweet, TweetImage
from util import extract_tweet_id


class TestExtractTweetId:
    """Test tweet ID extraction."""
    
    def test_standard_x_url(self):
        """Test standard x.com URL."""
        assert extract_tweet_id('https://x.com/user/status/123456789') == '123456789'
    
    def test_twitter_url(self):
        """Test twitter.com URL."""
        assert extract_tweet_id('https://twitter.com/user/status/123456789') == '123456789'
    
    def test_mobile_url(self):
        """Test mobile URLs."""
        assert extract_tweet_id('https://mobile.x.com/user/status/123456789') == '123456789'
        assert extract_tweet_id('https://m.twitter.com/user/status/123456789') == '123456789'
    
    def test_url_with_query_params(self):
        """Test URL with query parameters."""
        assert extract_tweet_id('https://x.com/user/status/123456789?s=20') == '123456789'
        assert extract_tweet_id('https://twitter.com/user/status/123456789?t=abc&s=09') == '123456789'
    
    def test_web_intent_url(self):
        """Test web intent URL format."""
        assert extract_tweet_id('https://x.com/i/web/status/123456789') == '123456789'
    
    def test_invalid_url(self):
        """Test invalid URLs."""
        with pytest.raises(ValueError):
            extract_tweet_id('https://example.com/not-a-tweet')
        
        with pytest.raises(ValueError):
            extract_tweet_id('https://x.com/user/not-a-status')


class TestTwitterClient:
    """Test Twitter client."""
    
    @patch('twitter_client.requests.Session')
    def test_fetch_tweet_success(self, mock_session_cls):
        """Test successful tweet fetch."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'text': 'This is a test tweet with\nmultiple lines',
            'user_name': 'Test User',
            'user_screen_name': 'testuser',
            'media_extended': [
                {'url': 'https://pbs.twimg.com/media/abc.jpg'},
                {'url': 'https://pbs.twimg.com/media/def.png'}
            ]
        }
        
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session
        
        # Test
        client = TwitterClient()
        tweet = client.fetch_tweet('https://x.com/testuser/status/123456')
        
        # Verify
        assert tweet.tweet_id == '123456'
        assert tweet.text == 'This is a test tweet with\nmultiple lines'
        assert tweet.author_username == 'testuser'
        assert len(tweet.images) == 2
        assert tweet.images[0].filename == '123456_1.jpg'
        assert tweet.images[1].filename == '123456_2.png'
    
    @patch('twitter_client.requests.Session')
    def test_fetch_tweet_no_images(self, mock_session_cls):
        """Test fetching tweet without images."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'text': 'Text only tweet',
            'user_screen_name': 'testuser',
            'media_extended': []
        }
        
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session
        
        # Test
        client = TwitterClient()
        tweet = client.fetch_tweet('https://x.com/testuser/status/789')
        
        # Verify
        assert tweet.tweet_id == '789'
        assert tweet.text == 'Text only tweet'
        assert len(tweet.images) == 0
    
    @patch('twitter_client.requests.Session')
    def test_fetch_tweet_api_error(self, mock_session_cls):
        """Test API error handling."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.HTTPError()
        
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session
        
        # Test
        client = TwitterClient()
        with pytest.raises(requests.HTTPError):
            client.fetch_tweet('https://x.com/user/status/999')
    
    @patch('twitter_client.requests.Session')
    def test_fetch_tweet_no_text(self, mock_session_cls):
        """Test tweet with no text."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'text': '',
            'media_extended': []
        }
        
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session
        
        # Test
        client = TwitterClient()
        with pytest.raises(ValueError, match="No text found"):
            client.fetch_tweet('https://x.com/user/status/123')
    
    def test_extract_images_with_original_quality(self):
        """Test image extraction with original quality URLs."""
        client = TwitterClient()
        
        data = {
            'media_extended': [
                {
                    'url': 'https://pbs.twimg.com/media/abc.jpg?name=small',
                    'altText': 'Image description'
                },
                {
                    'url': 'https://pbs.twimg.com/media/def.png?name=medium'
                }
            ]
        }
        
        images = client._extract_images(data, '123456')
        
        assert len(images) == 2
        assert images[0].url == 'https://pbs.twimg.com/media/abc.jpg?name=orig'
        assert images[1].url == 'https://pbs.twimg.com/media/def.png?name=orig'