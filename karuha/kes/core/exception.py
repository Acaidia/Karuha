import asyncio
import builtins
from typing import List, NoReturn, Optional

from .event import Event, EventMode


class Exception(Event):
    __slots__ = ["text", "src_node", "src_message", "traceback"]

    mode = EventMode.PROPAGATE

    def __init__(self, text: str, /) -> None:
        super().__init__()
        self.text = text
        self.src_node = get_curr_node()
        self.src_message = get_curr_message()
        self.traceback: List["Network"] = []
    
    def throw(self) -> NoReturn:
        self.send()
        raise NodeCancelledError(exc=self)


class PortError(Exception):
    __slots__ = ["name"]

    def __init__(self, text: str, /, name: str) -> None:
        super().__init__(text)
        self.name = name


class ValueError(Exception):
    __slots__ = []


class UnsupportedMessageError(Exception):
    __slots__ = []


class RuntimeError(Exception):
    __slots__ = []


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


from .node import get_curr_node, get_curr_message
from .network import Network
