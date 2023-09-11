from enum import Enum, auto
from typing import Any, ClassVar, List, Type

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
        self.traceback: List["Network"] = []

    def send(self) -> None:
        get_curr_node().send_event(self)
    
    def add_traceback(self, net: "Network") -> None:
        self.traceback.append(net)

    def __repr__(self) -> str:
        return f"<{self.__class__.__qualname__} event>"


class NetworkInitEvent(Event):
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
