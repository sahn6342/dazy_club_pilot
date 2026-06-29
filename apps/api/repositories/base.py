from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    @abstractmethod
    def get_all(self) -> list[T]: ...

    @abstractmethod
    def get_by_id(self, id: str) -> Optional[T]: ...

    @abstractmethod
    def create(self, item: T) -> T: ...

    @abstractmethod
    def update(self, id: str, data: dict) -> Optional[T]: ...

    @abstractmethod
    def delete(self, id: str) -> bool: ...
