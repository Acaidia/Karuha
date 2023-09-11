from typing import Any
from typing_extensions import Self


class Message(object):
    __slots__ = []

    def __rshift__(self, node: "BaseNode") -> Self:
        get_curr_node().send_message(node, self)
        return self
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__qualname__} messge>"


class DataMessage(Message):
    __slots__ = ["data"]

    def __init__(self, /, data: Any) -> None:
        super().__init__()
        self.data = data

    def __repr__(self) -> str:
        return f"<{self.__class__.__qualname__} messge with data {self.data!r}>"


class NodeInitializeMessage(Message):
    __slots__ = []


class NodeFinalizeMessage(Message):
    __slots__ = []


class ReflectMessage(Message):
    __slots__ = ["target", "raw"]

    def __init__(self, /, target: "BaseNode", message: Message) -> None:
        super().__init__()
        self.target = target
        self.raw = message
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__qualname__} messge with {self.raw!r} from {self.target!r}>"


class PortAction(Message):
    __slots__ = ["name"]

    def __init__(self, /, name: str) -> None:
        self.name = name
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__qualname__} messge for port {self.name!r}>"


class PortGet(PortAction):
    __slots__ = []


class PortSet(PortAction):
    __slots__ = ["value"]

    def __init__(self, /, name: str, value: Any) -> None:
        super().__init__(name)
        self.value = value


class PortExportAttr(PortAction):
    __slots__ = []


from .node import BaseNode, get_curr_node
