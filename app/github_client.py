"""GitHub client for interacting with repository contents."""
import base64
import logging
import time
from typing import Optional, Dict, Any, List
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class GitHubClient:
    """Client for GitHub API operations."""
    
    def __init__(self, token: str, owner: str, repo: str, branch: str = "main"):
        """Initialize GitHub client.
        
        Args:
            token: GitHub personal access token
            owner: Repository owner
            repo: Repository name
            branch: Target branch
        """
        self.token = token
        self.owner = owner
        self.repo = repo
        self.branch = branch
        self.base_url = "https://api.github.com"
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create HTTP session with authentication."""
        session = requests.Session()
        session.headers.update({
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json',
            'X-GitHub-Api-Version': '2022-11-28'
        })
        
        # Add retry logic for transient failures
        retry = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
    
    def get_file_content(self, path: str) -> Optional[Dict[str, Any]]:
        """Get file content and metadata from GitHub.
        
        Args:
            path: File path in repository
            
        Returns:
            Dict with content, sha, etc. or None if not found
        """
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/contents/{path}"
        params = {'ref': self.branch}
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get file {path}: {e}")
            raise
    
    def create_or_update_file(self, path: str, content: bytes, message: str, 
                            sha: Optional[str] = None, max_retries: int = 5) -> Dict[str, Any]:
        """Create or update a file in the repository with retry logic.
        
        Args:
            path: File path in repository
            content: File content as bytes
            message: Commit message
            sha: SHA of existing file (required for updates)
            max_retries: Maximum number of retries for conflicts
            
        Returns:
            API response with commit info
        """
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/contents/{path}"
        
        for attempt in range(max_retries):
            try:
                # Prepare request data
                data = {
                    'message': message,
                    'content': base64.b64encode(content).decode('utf-8'),
                    'branch': self.branch
                }
                
                if sha:
                    data['sha'] = sha
                
                response = self.session.put(url, json=data, timeout=30)
                
                # Handle conflicts
                if response.status_code in [409, 422]:
                    if attempt < max_retries - 1:
                        logger.warning(f"Conflict updating {path}, retrying (attempt {attempt + 1})")
                        # Exponential backoff
                        time.sleep(2 ** attempt)
                        
                        # Refresh SHA
                        file_info = self.get_file_content(path)
                        if file_info:
                            sha = file_info['sha']
                            continue
                    else:
                        logger.error(f"Max retries exceeded for {path}")
                        raise Exception(f"Conflict updating {path} after {max_retries} attempts")
                
                response.raise_for_status()
                return response.json()
                
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Error updating {path}, retrying: {e}")
                    time.sleep(2 ** attempt)
                    continue
                else:
                    logger.error(f"Failed to update {path}: {e}")
                    raise
    
    def append_to_file(self, path: str, content_to_append: str, message: str) -> Dict[str, Any]:
        """Append content to an existing file or create if not exists.
        
        Args:
            path: File path in repository
            content_to_append: Content to append
            message: Commit message
            
        Returns:
            API response with commit info
        """
        # Get existing content
        file_info = self.get_file_content(path)
        
        if file_info:
            # Decode existing content
            existing_content = base64.b64decode(file_info['content']).decode('utf-8')
            # Ensure file ends with newline
            if existing_content and not existing_content.endswith('\n'):
                existing_content += '\n'
            new_content = existing_content + content_to_append
            sha = file_info['sha']
        else:
            # Create new file
            new_content = content_to_append
            sha = None
        
        # Ensure final newline
        if not new_content.endswith('\n'):
            new_content += '\n'
        
        return self.create_or_update_file(
            path=path,
            content=new_content.encode('utf-8'),
            message=message,
            sha=sha
        )
    
    def upload_image(self, path: str, image_data: bytes, message: str) -> Dict[str, Any]:
        """Upload an image to the repository.
        
        Args:
            path: Image path in repository
            image_data: Image binary data
            message: Commit message
            
        Returns:
            API response with commit info
        """
        # Check if file already exists
        file_info = self.get_file_content(path)
        sha = file_info['sha'] if file_info else None
        
        return self.create_or_update_file(
            path=path,
            content=image_data,
            message=message,
            sha=sha
        )