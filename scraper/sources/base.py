from abc import ABC, abstractmethod
from datetime import date


class BaseSource(ABC):
    source_id: str
    auth_state_path: str

    @abstractmethod
    def ensure_authenticated(self) -> None:
        """Login and/or validate existing session. Persist auth state to auth_state_path."""

    @abstractmethod
    def get_new_article_urls(self, since_date: date) -> list[str]:
        """Return URLs of articles published after since_date that haven't been scraped."""

    @abstractmethod
    def scrape_article(self, url: str) -> dict:
        """Scrape a single article and return a dict matching the shared article schema."""
