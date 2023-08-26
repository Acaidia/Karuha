import asyncio
import builtins
from typing import Literal, Optional
from .message import Message, Event


class Exception(Event):
    __slots__ = ["text"]

    def __init__(self, text: str, /) -> None:
        super().__init__()
        self.text = text


class PortError(Exception):
    __slots__ = ["action", "name", "node"]

    def __init__(self, text: str, /, node: "BaseNode", action: Literal["READ", "WRITE"], name: str) -> None:
        super().__init__(text)
        self.node = node
        self.action = action
        self.name = name


class ValueError(Exception):
    __slots__ = []


class UnsupportedMessageError(Exception):
    __slots__ = ["message"]

    def __init__(self, text: str, /, message: Message) -> None:
        super().__init__(text)
        self.message = message


class PyKernelError(Exception):
    __slots__ = ["py_exc"]

    def __init__(self, exception: builtins.Exception) -> None:
        super().__init__(str(exception))
        self.py_exc = exception


class NodeCancelledError(asyncio.CancelledError):
    __slots__ = ["exc_message"]

    def __init__(self, *args: object, exc: Optional[Exception] = None) -> None:
        super().__init__(*args)
        self.exc_message = exc


from .node import BaseNode
