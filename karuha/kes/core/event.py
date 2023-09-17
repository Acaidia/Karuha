from copy import copy
from enum import Enum, auto
from typing import Any, ClassVar, Tuple, Type
from typing_extensions import Self

from .message import Message


class EventMode(Enum):
    IGNORE = auto()
    THROW_ERR = auto()
    PROPAGATE = auto()
    FORCE_PROPAGATE = auto()


class Event(Message):
    __slots__ = ["traceback"]

    mode: ClassVar[EventMode] = EventMode.IGNORE

    def __init__(self) -> None:
        super().__init__()
        self.traceback: Tuple["Network", ...] = ()

    def send(self) -> None:
        get_curr_node().send_event(self)
    
    def add_traceback(self, net: "Network") -> Self:
        ne = copy(self)
        ne.traceback = self.traceback + (net,)
        return ne
    
    @property
    def is_primary(self) -> bool:
        return not self.traceback

    def __repr__(self) -> str:
        return f"<{self.__class__.__qualname__} event>"


class NetworkInitializeEvent(Event):
    __slots__ = []


class NetworkFinalizeEvent(Event):
    __slots__ = []


class NodeNewEvent(Event):
    __slots__ = ["type", "args", "kwargs"]

    def __init__(self, type: Type["BaseNode"], *args: Any, **kwds: Any) -> None:
        super().__init__()
        self.type = type
        self.args = args
        self.kwargs = kwds


class NodeDropEvent(Event):
    __slots__ = ["nid"]
    
    def __init__(self, /, nid: int) -> None:
        super().__init__()
        self.nid = nid


class NodeTransferEvent(Event):
    __slots__ = ["node"]

    def __init__(self, /, node: "BaseNode") -> None:
        super().__init__()
        self.node = node


from .node import BaseNode, get_curr_node
from .network import Network
