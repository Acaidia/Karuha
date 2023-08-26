from abc import ABC, abstractmethod
from asyncio import iscoroutine
from contextlib import suppress
from enum import IntFlag, auto
from inspect import signature
from types import MethodType
from typing import (Any, Callable, ClassVar, Coroutine, Dict, Generic, Literal,
                    NoReturn, Optional, Type, TypeVar, Union, get_args,
                    overload)
from typing_extensions import Self

from .message import DataMessage, Message, PortGet, PortSet, ReflectMessage


T_Message = TypeVar("T_Message", bound=Message)
T_Node = TypeVar("T_Node", bound="Node", covariant=True)


class PortFlag(IntFlag):
    READABLE = auto()
    WRITABLE = auto()
    HOOKABLE = auto()
    DEFAULT = READABLE | HOOKABLE


class BaseNode(object):
    __slots__ = ["net", "nid"]

    def __init__(self, net: "Network", id: int) -> None:
        self.net = net
        self.nid = id
    
    def pass_down(self, message: Message) -> None:
        for i in self.net.node_next(self.nid):
            self.net.send_message(i, message)

    @overload
    def throw(self, exception: "kes_exc.Exception", *, cancel: Literal[False]) -> None: ...
    @overload
    def throw(self, exception: "kes_exc.Exception", *, cancel: Literal[True] = True) -> NoReturn: ...

    def throw(self, exception: "kes_exc.Exception", *, cancel: bool = True) -> None:
        self.net.send_message(self.net, exception)
        if cancel:
            raise kes_exc.NodeCancelledError(exc=exception)

    async def handle_message(self, message: "Message", /) -> None:
        self.throw(
            kes_exc.UnsupportedMessageError("unprocessable message", message=message)
        )
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__qualname__} node at 0x{id(self):#016X}>"


class AbstractPort(ABC):
    __slots__ = ["node", "name", "flag"]

    def __init__(self, node: BaseNode, name: str, /, flag: PortFlag = PortFlag.DEFAULT) -> None:
        super().__init__()
        self.node = node
        self.name = name
        self.flag = flag

    @abstractmethod
    def get(self, /) -> Any:
        node = self.node
        if PortFlag.READABLE not in self.flag:
            node.throw(
                kes_exc.PortError(
                    f"port {self.name} is not readable",
                    node, "READ", self.name
                )
            )
    
    @abstractmethod
    def set(self, value: Any, /) -> None:
        node = self.node
        if PortFlag.WRITABLE not in self.flag:
            node.throw(
                kes_exc.PortError(
                    f"port {self.name} is not writable",
                    node, "WRITE", self.name
                )
            )


class AttrPort(AbstractPort):
    __slots__ = []

    def get(self, /) -> Any:
        super().get()
        return getattr(self.node, self.name)

    def set(self, value: Any, /) -> None:
        super().set(value)
        setattr(self.node, self.name, value)


class HandlerFlag(IntFlag):
    REFLECTIVE = auto()
    SEND_RET = auto()
    PROPAGATE = auto()
    DEFAULT = REFLECTIVE


class MessageHandler(Generic[T_Message]):
    __slots__ = ["__func__", "flag", "_message_type", "__orig_class__"]

    def __init__(
            self,
            func: Callable[["Node", T_Message], Any],
            /,
            flag: HandlerFlag = HandlerFlag.DEFAULT,
            message_type: Optional[Type[T_Message]] = None
    ) -> None:
        self.__func__ = func
        self.flag = flag
        if message_type is not None:
            self._message_type = message_type
    
    @property
    def message_type(self) -> Type[T_Message]:
        with suppress(AttributeError):
            return self._message_type
        
        message_type: T_Message
        try:
            orig_cls = self.__orig_class__
            message_type, = get_args(orig_cls)
            assert issubclass(message_type, Message)
            self._message_type = message_type
            return message_type
        except Exception:
            pass
        
        try:
            sig = signature(self.__func__)
            _, message_type = (i.annotation for i in sig.parameters.values())
            assert issubclass(message_type, Message)  # type: ignore
            self._message_type = message_type
            return message_type
        except Exception:
            pass
        raise ValueError("unable to get the message type corresponding to the handler")

    @overload
    def __get__(self, ins: None, owner: Type["Node"]) -> Self: ...
    @overload
    def __get__(self, ins: "Node", owner: Type["Node"]) -> Callable[[T_Message], Coroutine]: ...

    def __get__(self, ins: Optional["Node"], owner: Type["Node"]) -> Union[Self, Callable]:
        if ins is None:
            return self
        return MethodType(self, ins)
    
    async def __call__(self, node: "Node", message: T_Message) -> Any:
        try:
            ret = self.__func__(node, message)
            if iscoroutine(ret):
                ret = await ret
            return ret
        except Exception as e:
            node.throw(kes_exc.PyKernelError(e))


def on(
        message: Type[T_Message],
        *,
        flag: HandlerFlag = HandlerFlag.DEFAULT,
        node: Optional[Type[T_Node]] = None
) -> Callable[[Callable[[T_Node, T_Message], Any]], MessageHandler[T_Message]]:
    def inner(func: Callable[[T_Node, T_Message], Any]):
        handler = MessageHandler[message](func, flag=flag)  # type: ignore
        if node is not None:
            node.__message_handler__[message] = handler
        return handler
    return inner


class Node(BaseNode):
    __slots__ = ["port_map"]

    __message_handler__: ClassVar[Dict[Type[Message], MessageHandler]]

    def __init__(self, net: "Network", id: int) -> None:
        self.net = net
        self.nid = id
        self.port_map: Dict[str, AbstractPort] = {}
    
    def export(self, name_or_port: Union[str, "AbstractPort"], /, flag: PortFlag = PortFlag.DEFAULT) -> None:
        if isinstance(name_or_port, str):
            self.port_map[name_or_port] = AttrPort(self, name_or_port, flag)
        else:
            self.port_map[name_or_port.name] = name_or_port
    
    def get_port(self, name: str) -> Any:
        if name not in self.port_map:
            self.throw(kes_exc.PortError(f"node {self!r} has not port {name}", self, "READ", name))
        return self.port_map[name].get()
    
    def set_port(self, name: str, value: Any) -> None:
        if name not in self.port_map:
            self.throw(kes_exc.PortError(f"node {self!r} has not port {name}", self, "READ", name))
        return self.port_map[name].set(value)

    async def handle_message(self, message: "Message", /) -> None:
        raw_message = message
        if isinstance(message, ReflectMessage):
            target = message.target
            message = message.raw
        else:
            target = None
        handled = False
        for tp in message.__class__.__mro__:
            hdl = self.__message_handler__.get(tp)
            if hdl is None:
                continue
            ret = await hdl(self, message)
            handled = True
            if HandlerFlag.SEND_RET in hdl.flag:
                data = DataMessage(ret)
                if target is not None:
                    if HandlerFlag.REFLECTIVE not in hdl.flag:
                        self.throw(
                            kes_exc.UnsupportedMessageError(
                                f"{tp} is not reflective", raw_message
                            )
                        )
                    self.net.send_message(target, data)
                else:
                    self.pass_down(data)
            if HandlerFlag.PROPAGATE not in hdl.flag:
                break
        if not handled:
            self.throw(
                kes_exc.UnsupportedMessageError(
                    "unhandlable message", message=raw_message
                )
            )
    
    @on(PortGet, flag=HandlerFlag.REFLECTIVE | HandlerFlag.SEND_RET)
    def on_port_get(self, message: PortGet) -> Any:
        return self.get_port(message.name)

    @on(PortSet, flag=HandlerFlag(0))
    def on_port_set(self, message: PortSet) -> None:
        self.set_port(message.name, message.value)

    __message_handler__ = {PortGet: on_port_get, PortSet: on_port_set}
        
    @classmethod
    def on(
            cls,  message: Type[T_Message],
            *, flag: HandlerFlag = HandlerFlag.DEFAULT
    ) -> Callable[[Callable[[Self, T_Message], Any]], MessageHandler[T_Message]]:
        return on(message, flag=flag, node=cls)

    def __init_subclass__(cls) -> None:
        cls.__message_handler__ = cls.__message_handler__.copy()
        super().__init_subclass__()
        for i in cls.__dict__.values():
            if not isinstance(i, MessageHandler):
                continue
            cls.__message_handler__[i.message_type] = i


from . import exception as kes_exc
from .network import Network
