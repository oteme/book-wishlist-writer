"""Tests for GitHub client."""
import pytest
import base64
from unittest.mock import Mock, patch
import requests

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from github_client import GitHubClient


class TestGitHubClient:
    """Test GitHub client."""
    
    def setup_method(self):
        """Setup test client."""
        self.client = GitHubClient(
            token='test-token',
            owner='testowner',
            repo='testrepo',
            branch='main'
        )
    
    @patch('github_client.requests.Session')
    def test_get_file_content_exists(self, mock_session_cls):
        """Test getting existing file content."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'content': base64.b64encode(b'test content').decode('utf-8'),
            'sha': 'abc123',
            'path': 'test.txt'
        }
        
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session
        
        # Test
        result = self.client.get_file_content('test.txt')
        
        # Verify
        assert result['sha'] == 'abc123'
        assert result['path'] == 'test.txt'
        mock_session.get.assert_called_once()
    
    @patch('github_client.requests.Session')
    def test_get_file_content_not_found(self, mock_session_cls):
        """Test getting non-existent file."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 404
        
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session
        
        # Test
        result = self.client.get_file_content('nonexistent.txt')
        
        # Verify
        assert result is None
    
    @patch('github_client.requests.Session')
    def test_create_new_file(self, mock_session_cls):
        """Test creating a new file."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            'commit': {'sha': 'def456'},
            'content': {'sha': 'file123'}
        }
        
        mock_session = Mock()
        mock_session.put.return_value = mock_response
        mock_session_cls.return_value = mock_session
        
        # Test
        result = self.client.create_or_update_file(
            path='new.txt',
            content=b'new content',
            message='Add new file'
        )
        
        # Verify
        assert result['commit']['sha'] == 'def456'
        mock_session.put.assert_called_once()
    
    @patch('github_client.requests.Session')
    def test_update_existing_file(self, mock_session_cls):
        """Test updating an existing file."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'commit': {'sha': 'ghi789'},
            'content': {'sha': 'file456'}
        }
        
        mock_session = Mock()
        mock_session.put.return_value = mock_response
        mock_session_cls.return_value = mock_session
        
        # Test
        result = self.client.create_or_update_file(
            path='existing.txt',
            content=b'updated content',
            message='Update file',
            sha='old123'
        )
        
        # Verify
        assert result['commit']['sha'] == 'ghi789'
        call_args = mock_session.put.call_args
        request_data = call_args[1]['json']
        assert request_data['sha'] == 'old123'
        assert request_data['message'] == 'Update file'
    
    @patch('github_client.requests.Session')
    @patch('github_client.time.sleep')
    def test_conflict_retry(self, mock_sleep, mock_session_cls):
        """Test conflict retry mechanism."""
        # Setup mocks
        conflict_response = Mock()
        conflict_response.status_code = 409
        
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {
            'commit': {'sha': 'success123'}
        }
        
        get_response = Mock()
        get_response.status_code = 200
        get_response.json.return_value = {'sha': 'new123'}
        
        mock_session = Mock()
        mock_session.put.side_effect = [conflict_response, success_response]
        mock_session.get.return_value = get_response
        mock_session_cls.return_value = mock_session
        
        # Test
        result = self.client.create_or_update_file(
            path='conflict.txt',
            content=b'content',
            message='Test conflict',
            sha='old123'
        )
        
        # Verify
        assert result['commit']['sha'] == 'success123'
        assert mock_session.put.call_count == 2
        mock_sleep.assert_called_once()
    
    @patch('github_client.requests.Session')
    def test_append_to_existing_file(self, mock_session_cls):
        """Test appending to an existing file."""
        # Setup mocks for get and put
        get_response = Mock()
        get_response.status_code = 200
        get_response.json.return_value = {
            'content': base64.b64encode(b'existing content').decode('utf-8'),
            'sha': 'existing123'
        }
        
        put_response = Mock()
        put_response.status_code = 200
        put_response.json.return_value = {
            'commit': {'sha': 'append123'}
        }
        
        mock_session = Mock()
        mock_session.get.return_value = get_response
        mock_session.put.return_value = put_response
        mock_session_cls.return_value = mock_session
        
        # Test
        result = self.client.append_to_file(
            path='append.txt',
            content_to_append='appended content',
            message='Append content'
        )
        
        # Verify
        assert result['commit']['sha'] == 'append123'
        
        # Check that content was properly merged
        put_call = mock_session.put.call_args
        request_data = put_call[1]['json']
        decoded_content = base64.b64decode(request_data['content']).decode('utf-8')
        assert 'existing content' in decoded_content
        assert 'appended content' in decoded_content
    
    @patch('github_client.requests.Session')
    def test_append_to_new_file(self, mock_session_cls):
        """Test appending to a non-existent file (creates new)."""
        # Setup mocks
        get_response = Mock()
        get_response.status_code = 404
        
        put_response = Mock()
        put_response.status_code = 201
        put_response.json.return_value = {
            'commit': {'sha': 'new123'}
        }
        
        mock_session = Mock()
        mock_session.get.return_value = get_response
        mock_session.put.return_value = put_response
        mock_session_cls.return_value = mock_session
        
        # Test
        result = self.client.append_to_file(
            path='new.txt',
            content_to_append='new content',
            message='Create new file'
        )
        
        # Verify
        assert result['commit']['sha'] == 'new123'
        
        # Check that only new content is present
        put_call = mock_session.put.call_args
        request_data = put_call[1]['json']
        decoded_content = base64.b64decode(request_data['content']).decode('utf-8')
        assert decoded_content == 'new content\n'
    
    @patch('github_client.requests.Session')
    def test_upload_image(self, mock_session_cls):
        """Test image upload."""
        # Setup mocks
        get_response = Mock()
        get_response.status_code = 404  # Image doesn't exist
        
        put_response = Mock()
        put_response.status_code = 201
        put_response.json.return_value = {
            'commit': {'sha': 'image123'}
        }
        
        mock_session = Mock()
        mock_session.get.return_value = get_response
        mock_session.put.return_value = put_response
        mock_session_cls.return_value = mock_session
        
        # Test
        image_data = b'\x89PNG\r\n\x1a\n'  # PNG header
        result = self.client.upload_image(
            path='images/test.png',
            image_data=image_data,
            message='Upload test image'
        )
        
        # Verify
        assert result['commit']['sha'] == 'image123'
        
        put_call = mock_session.put.call_args
        request_data = put_call[1]['json']
        decoded_content = base64.b64decode(request_data['content'])
        assert decoded_content == image_data