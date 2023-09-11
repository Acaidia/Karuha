import asyncio
from abc import ABC, abstractmethod
from asyncio import iscoroutine
from contextlib import suppress
from contextvars import ContextVar
from enum import IntFlag, auto
from inspect import signature
from types import MethodType
from typing import (Any, Callable, ClassVar, Coroutine, Dict, Generic, Literal,
                    NoReturn, Optional, Set, Type, TypeVar, Union, get_args,
                    overload)

from typing_extensions import Self, Annotated, _AnnotatedAlias

from .message import (DataMessage, Message, NodeFinalizeMessage,
                      NodeInitializeMessage, PortGet, PortSet, ReflectMessage)


T_co = TypeVar("T_co", covariant=True)
T_Message = TypeVar("T_Message", bound=Message)
T_Node = TypeVar("T_Node", bound="Node", covariant=True)

var_node = ContextVar["BaseNode"]("node")
var_message = ContextVar["Message"]("message")


async def prepare_and_exec(node: "BaseNode", message: Message) -> None:
    var_node.set(node)
    var_message.set(message)
    try:
        await node.handle_message(message)
    except Exception as e:
        raise kes_exc.NodeCancelledError(
            "uncaught exception",
            exc=kes_exc.PyKernelError(e)
        ) from e


def get_curr_node() -> "BaseNode":
    try:
        return var_node.get()
    except LookupError as e:
        raise RuntimeError("not in the KES runtime") from e


def get_curr_message() -> Message:
    try:
        return var_message.get()
    except LookupError as e:
        raise RuntimeError("not in the KES runtime") from e


class BaseNode(object):
    __slots__ = ["net", "nid", "__weakref__"]

    net: "Network"
    nid: int

    def __init__(self, net: "Network") -> None:
        self.net = net
    
    @staticmethod
    def send_message(target: "BaseNode", message: Message, /) -> None:
        asyncio.create_task(prepare_and_exec(target, message))
    
    def send_message_inner(self, message: Message, /) -> None:
        self.send_message(self, message)
    
    def pass_down(self, message: Message, /) -> None:
        for i in self.net._record_next(self.nid):
            self.send_message(i, message)
    
    def send_event(self, event: "Event", /) -> None:
        self.send_message(self.net, event)

    @overload
    def throw(self, exception: "kes_exc.Exception", *, cancel: Literal[False]) -> None: ...
    @overload
    def throw(self, exception: "kes_exc.Exception", *, cancel: Literal[True] = True) -> NoReturn: ...

    def throw(self, exception: "kes_exc.Exception", *, cancel: bool = True) -> None:
        self.send_event(exception)
        if cancel:
            raise kes_exc.NodeCancelledError(exc=exception)
    
    send_exception = throw

    async def handle_message(self, message: "Message", /) -> None:
        self.throw(
            kes_exc.UnsupportedMessageError("unprocessable message")
        )
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__qualname__} node in net {self.net!r} at 0x{id(self):#016X}>"


class PortFlag(IntFlag):
    READABLE = auto()
    WRITABLE = auto()
    DEFAULT = READABLE


class AbstractPort(ABC, Generic[T_co]):
    __slots__ = ["node", "name", "flag"]

    def __init__(self, node: BaseNode, name: str, /, flag: PortFlag = PortFlag.DEFAULT) -> None:
        super().__init__()
        self.node = node
        self.name = name
        self.flag = flag

    @abstractmethod
    def get(self, /) -> T_co:
        node = self.node
        if PortFlag.READABLE not in self.flag:
            node.throw(
                kes_exc.PortError(
                    f"port {self.name} is not readable",
                    self.name
                )
            )
    
    @abstractmethod
    def set(self, value: T_co, /) -> None:  # type: ignore
        node = self.node
        if PortFlag.WRITABLE not in self.flag:
            node.throw(
                kes_exc.PortError(
                    f"port {self.name} is not writable",
                    self.name
                )
            )


class AttrPort(AbstractPort[T_co]):
    __slots__ = []

    def get(self, /) -> T_co:
        super().get()
        return getattr(self.node, self.name)

    def set(self, value: T_co, /) -> None:  # type: ignore
        super().set(value)
        setattr(self.node, self.name, value)


class HandlerFlag(IntFlag):
    DEFAULT = 0
    REFLECTIVE = auto()
    SEND_RET = auto()
    PROPAGATE = auto()


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
        ret = self.__func__(node, message)
        if iscoroutine(ret):
            ret = await ret
        return ret


Export = Annotated[T_co, AttrPort[T_co]]


def on(
        message: Type[T_Message],
        *,
        flag: HandlerFlag = HandlerFlag.DEFAULT,
        node: Optional[Type[T_Node]] = None
) -> Callable[[Callable[[T_Node, T_Message], Any]], MessageHandler[T_Message]]:
    def inner(func: Callable[[T_Node, T_Message], Any]):
        if isinstance(func, MessageHandler):
            func = func.__func__
        handler = MessageHandler[message](func, flag=flag)  # type: ignore
        if node is not None:
            node.__message_handler__[message] = handler
        return handler
    return inner


class Node(BaseNode):
    __slots__ = ["port_map"]

    __export_attr__: ClassVar[Set[str]] = set()
    __message_handler__: ClassVar[Dict[Type[Message], MessageHandler]]

    def __init__(self, net: "Network") -> None:
        self.net = net
        self.port_map: Dict[str, AbstractPort] = {i: AttrPort(self, i) for i in self.__export_attr__}
    
    def initialize(self) -> None:
        self.send_message(self, NodeInitializeMessage())
    
    def finalize(self) -> None:
        self.send_message(self, NodeFinalizeMessage())
    
    def drop(self) -> None:
        self.send_event(NodeDropEvent(self.nid))

    async def handle_message(self, message: "Message", /) -> None:
        if isinstance(self.net, PhantomNetwork):
            self.throw(kes_exc.RuntimeError("phantom node does not receive messages"))
            
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
                                f"{tp} is not reflective"
                            )
                        )
                    self.send_message(target, data)
                else:
                    self.pass_down(data)
            if HandlerFlag.PROPAGATE not in hdl.flag:
                break
        if not handled:
            self.throw(
                kes_exc.UnsupportedMessageError(
                    "unhandlable message"
                )
            )
    
    @on(NodeInitializeMessage)
    def on_initialize(self, message: NodeInitializeMessage) -> None:
        pass

    @on(NodeFinalizeMessage)
    def on_finalize(self, message: NodeFinalizeMessage) -> None:
        self.drop()
    
    @on(PortGet, flag=HandlerFlag.REFLECTIVE | HandlerFlag.SEND_RET)
    def on_port_get(self, message: PortGet) -> Any:
        return self._get_port(message.name)

    @on(PortSet)
    def on_port_set(self, message: PortSet) -> None:
        self._set_port(message.name, message.value)

    __message_handler__ = {
        NodeInitializeMessage: on_initialize, NodeFinalizeMessage: on_finalize,
        PortGet: on_port_get, PortSet: on_port_set,
    }
        
    @classmethod
    def on(
            cls,  message: Type[T_Message],
            *, flag: HandlerFlag = HandlerFlag.DEFAULT
    ) -> Callable[[Callable[[Self, T_Message], Any]], MessageHandler[T_Message]]:
        return on(message, flag=flag, node=cls)

    def _export(self, name_or_port: Union[str, "AbstractPort"], /, flag: PortFlag = PortFlag.DEFAULT) -> None:
        if isinstance(name_or_port, str):
            self.port_map[name_or_port] = AttrPort(self, name_or_port, flag)
        else:
            self.port_map[name_or_port.name] = name_or_port
    
    def _get_port(self, name: str) -> Any:
        if name not in self.port_map:
            self.throw(kes_exc.PortError(f"node {self!r} has not port {name}", name))
        return self.port_map[name].get()
    
    def _set_port(self, name: str, value: Any) -> None:
        if name not in self.port_map:
            self.throw(kes_exc.PortError(f"node {self!r} has not port {name}", name))
        return self.port_map[name].set(value)

    def __init_subclass__(cls) -> None:
        cls.__message_handler__ = cls.__message_handler__.copy()
        cls.__export_attr__ = cls.__export_attr__.copy()
        super().__init_subclass__()
        for i in cls.__dict__.values():
            if isinstance(i, MessageHandler):
                cls.__message_handler__[i.message_type] = i
        for k, v in cls.__annotations__.items():
            if v == Export or (isinstance(v, _AnnotatedAlias) and v.__metadata__ == (AttrPort,)):
                cls.__export_attr__.add(k)


from . import exception as kes_exc
from .event import Event, NodeDropEvent
from .network import Network
from .phantom import PhantomNetwork
