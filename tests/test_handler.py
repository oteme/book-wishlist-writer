"""Tests for Lambda handler."""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add app directory to path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from handler import lambda_handler, validate_request, check_api_key, format_wishlist_entry, get_entry_type, EntryType
from model import WishlistEntry, TweetImage, Tweet


class TestValidateRequest:
    """Test request validation."""
    
    def test_valid_request(self):
        """Test valid request."""
        event = {
            'body': json.dumps({
                'url': 'https://x.com/user/status/123456',
                'note': 'test note'
            })
        }
        url, note = validate_request(event)
        assert url == 'https://x.com/user/status/123456'
        assert note == 'test note'
    
    def test_missing_url(self):
        """Test missing URL."""
        event = {'body': json.dumps({'note': 'test'})}
        with pytest.raises(ValueError, match="URL is required"):
            validate_request(event)
    
    def test_invalid_url(self):
        """Test invalid URL."""
        event = {
            'body': json.dumps({
                'url': 'https://example.com/not-twitter'
            })
        }
        with pytest.raises(ValueError, match="Invalid Twitter/X URL"):
            validate_request(event)
    
    def test_long_note(self):
        """Test note that's too long."""
        event = {
            'body': json.dumps({
                'url': 'https://x.com/user/status/123',
                'note': 'x' * 501
            })
        }
        with pytest.raises(ValueError, match="Note is too long"):
            validate_request(event)


class TestCheckApiKey:
    """Test API key validation."""
    
    def test_no_key_required(self):
        """Test when no API key is required."""
        event = {'headers': {}}
        assert check_api_key(event, None) is True
    
    def test_valid_key(self):
        """Test valid API key."""
        event = {'headers': {'x-api-key': 'test-key'}}
        assert check_api_key(event, 'test-key') is True
    
    def test_invalid_key(self):
        """Test invalid API key."""
        event = {'headers': {'x-api-key': 'wrong-key'}}
        assert check_api_key(event, 'test-key') is False
    
    def test_missing_key(self):
        """Test missing API key when required."""
        event = {'headers': {}}
        assert check_api_key(event, 'test-key') is False


class TestFormatWishlistEntry:
    """Test wishlist entry formatting."""
    
    def test_format_with_images_and_note(self):
        """Test formatting with images and note."""
        entry = WishlistEntry(
            date='2024-01-15',
            title='@testuser',
            url='https://x.com/testuser/status/123',
            note='Great book recommendation',
            tweet_text='Check out this book!\\nIt\'s amazing!',
            images=[
                TweetImage(url='https://example.com/1.jpg', filename='123_1.jpg'),
                TweetImage(url='https://example.com/2.jpg', filename='123_2.jpg')
            ]
        )
        
        result = format_wishlist_entry(entry)
        expected_lines = [
            'https://x.com/testuser/status/123',
            'Check out this book!',
            'It\'s amazing!',
            '![[assets/2025-08/123_1.jpg]]',
            '![[assets/2025-08/123_2.jpg]]',
            '',
            '---'
        ]
        assert result == '\n'.join(expected_lines)
    
    def test_format_without_note(self):
        """Test formatting without note."""
        entry = WishlistEntry(
            date='2024-01-15',
            title='@testuser',
            url='https://x.com/testuser/status/123',
            note=None,
            tweet_text='Simple tweet',
            images=[]
        )
        
        result = format_wishlist_entry(entry)
        expected_lines = [
            'https://x.com/testuser/status/123',
            'Simple tweet',
            '',
            '---'
        ]
        assert result == '\n'.join(expected_lines)


class TestGetEntryType:
    """Test entry type detection."""
    
    def test_book_entry_type(self):
        """Test default book entry type."""
        event = {'rawPath': '/ingest'}
        assert get_entry_type(event) == EntryType.BOOK
        
        event = {'path': '/ingest'}
        assert get_entry_type(event) == EntryType.BOOK
        
        event = {}
        assert get_entry_type(event) == EntryType.BOOK
    
    def test_liked_entry_type(self):
        """Test liked entry type."""
        event = {'rawPath': '/liked'}
        assert get_entry_type(event) == EntryType.LIKED
        
        event = {'path': '/liked'}
        assert get_entry_type(event) == EntryType.LIKED


class TestLambdaHandler:
    """Test Lambda handler."""
    
    @patch('handler.get_secret')
    @patch('handler.TwitterClient')
    @patch('handler.GitHubClient')
    @patch('handler.download_image')
    def test_successful_ingestion(self, mock_download, mock_github_cls, mock_twitter_cls, mock_get_secret):
        """Test successful tweet ingestion."""
        # Setup mocks
        mock_get_secret.return_value = {
            'GITHUB_TOKEN': 'test-token',
            'API_KEY': 'test-api-key',
            'GITHUB_OWNER': 'owner',
            'GITHUB_REPO': 'repo',
            'GITHUB_BRANCH': 'main'
        }
        
        mock_twitter = Mock()
        mock_twitter.fetch_tweet.return_value = Tweet(
            tweet_id='123456',
            text='Test tweet content',
            images=[TweetImage(url='https://example.com/img.jpg', filename='123456_1.jpg')],
            author_username='testuser'
        )
        mock_twitter_cls.return_value = mock_twitter
        
        mock_github = Mock()
        mock_github.upload_image.return_value = {'commit': {'sha': 'abc123'}}
        mock_github.append_to_file.return_value = {'commit': {'sha': 'def456'}}
        mock_github_cls.return_value = mock_github
        
        mock_download.return_value = b'fake-image-data'
        
        # Create event
        event = {
            'headers': {'x-api-key': 'test-api-key'},
            'body': json.dumps({
                'url': 'https://x.com/testuser/status/123456',
                'note': 'Read later'
            })
        }
        
        # Call handler
        response = lambda_handler(event, None)
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        assert body['tweetId'] == '123456'
        assert len(body['commits']) == 2
        
        # Verify calls
        mock_twitter.fetch_tweet.assert_called_once()
        mock_github.upload_image.assert_called_once()
        mock_github.append_to_file.assert_called_once()
    
    @patch('handler.get_secret')
    def test_unauthorized_request(self, mock_get_secret):
        """Test unauthorized request."""
        mock_get_secret.return_value = {'API_KEY': 'test-api-key'}
        
        event = {
            'headers': {'x-api-key': 'wrong-key'},
            'body': json.dumps({'url': 'https://x.com/user/status/123'})
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert body['status'] == 'error'
        assert body['message'] == 'Unauthorized'
    
    @patch('handler.get_secret')
    def test_invalid_request(self, mock_get_secret):
        """Test invalid request."""
        mock_get_secret.return_value = {'API_KEY': None}
        
        event = {
            'headers': {},
            'body': json.dumps({'note': 'missing url'})
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['status'] == 'error'