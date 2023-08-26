import asyncio
from typing import Any
from typing_extensions import Self


class Message(object):
    __slots__ = []

    def __rshift__(self, node: "BaseNode") -> Self:
        asyncio.create_task(node.handle_message(self))
        return self


class DataMessage(Message):
    __slots__ = ["data"]

    def __init__(self, /, data: Any) -> None:
        super().__init__()
        self.data = data
    

class ReflectMessage(Message):
    __slots__ = ["target", "raw"]

    def __init__(self, /, target: "BaseNode", message: Message) -> None:
        super().__init__()
        self.target = target
        self.raw = message


class PortMessage(Message):
    __slots__ = ["name"]

    def __init__(self, /, name: str) -> None:
        self.name = name


class PortGet(PortMessage):
    __slots__ = []


class PortSet(PortMessage):
    __slots__ = ["value"]

    def __init__(self, /, name: str, value: Any) -> None:
        super().__init__(name)
        self.value = value


class Event(Message):
    __slots__ = []


from .node import BaseNode
