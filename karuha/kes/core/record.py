from abc import ABC, abstractmethod
from typing import Iterator, List, NamedTuple, Protocol, Set

from .node import BaseNode
from . import exception as kes_exc


class RecordLike(Protocol):
    @property
    def node(self) -> BaseNode: ...
    @property
    def next(self) -> Set[int]: ...


class AbstractRecordManager(ABC):
    __slots__ = []

    @abstractmethod
    def get(self, nid: int) -> RecordLike:
        raise NotImplementedError
    
    @abstractmethod
    def new(self, node: BaseNode) -> int:
        raise NotImplementedError
    
    @abstractmethod
    def drop(self, nid: int) -> BaseNode:
        raise NotImplementedError
    
    @abstractmethod
    def __iter__(self) -> Iterator[RecordLike]:
        raise NotImplementedError

    def __len__(self) -> int:
        return len(tuple(self))
    

class NodeRecord(NamedTuple):
    node: BaseNode
    next: Set[int]


class RecordManager(AbstractRecordManager):
    __slots__ = ["_records", "_id_cache"]

    def __init__(self) -> None:
        super().__init__()
        self._records: List[NodeRecord] = []
        self._id_cache = set()
    
    def get(self, nid: int) -> NodeRecord:
        if nid < 0 or nid >= len(self._records) or nid in self._id_cache:
            kes_exc.RuntimeError(f"there is no node with id {nid}").throw()
        return self._records[nid]
    
    def new(self, node: BaseNode) -> int:
        record = NodeRecord(node, set())
        if self._id_cache:
            nid = self._id_cache.pop()
            self._records[nid] = record
        else:
            nid = len(self._records)
            self._records.append(
                NodeRecord(node, set())
            )
        node.nid = nid
        return nid
    
    def drop(self, nid: int) -> BaseNode:
        if nid == len(self._records) - 1:
            record = self._records.pop()
            while (n := len(self._records) - 1) in self._id_cache:
                self._id_cache.remove(n)
                self._records.pop()
        else:
            record = self.get(nid)
            self._id_cache.add(nid)
        return record.node
    
    def __iter__(self) -> Iterator[NodeRecord]:
        for i, record in enumerate(self._records):
            if i not in self._id_cache:
                yield record
    
    def __len__(self) -> int:
        return len(self._records) - len(self._id_cache)
