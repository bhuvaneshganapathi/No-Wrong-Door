"""
Abstract Base Adapter for data sources
"""
from abc import ABC, abstractmethod
from app.models import AdapterResponse

class BaseAdapter(ABC):
    
    @abstractmethod
    def fetch_all(self) -> AdapterResponse:
        pass

    @abstractmethod
    def fetch_by_id(self, id_str: str) -> AdapterResponse:
        pass
