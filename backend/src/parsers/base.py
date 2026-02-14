from abc import ABC, abstractmethod
from src.models import RemittanceAdvice

class BasePDFParser(ABC):
    @abstractmethod
    def can_parse(self, file_path: str) -> bool:
        pass

    @abstractmethod
    def parse(self, file_path: str) -> RemittanceAdvice:
        pass