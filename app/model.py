"""Data models for tweet wishlist application."""
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class TweetImage:
    """Represents a tweet image."""
    url: str
    filename: str


@dataclass
class Tweet:
    """Represents a tweet with metadata."""
    tweet_id: str
    text: str
    images: List[TweetImage]
    author_name: Optional[str] = None
    author_username: Optional[str] = None


@dataclass
class WishlistEntry:
    """Represents an entry to be added to the wishlist."""
    date: str
    title: str
    url: str
    note: Optional[str]
    tweet_text: str
    images: List[TweetImage]