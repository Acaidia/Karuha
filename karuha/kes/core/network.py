import gc
from collections import defaultdict
from contextlib import suppress
from typing import (List, Literal, NoReturn, Optional, Type, TypeVar, Union,
                    overload)
from weakref import ref

from . import event as kes_evt
from . import exception as kes_exc
from . import message as kes_msg
from .node import AbstractPort, BaseNode, HandlerFlag, Node, PortFlag, on
from .record import AbstractRecordManager, RecordManager


T_Node = TypeVar("T_Node", bound=BaseNode)


class RecordPort(AbstractPort):
    __slots__ = ["nid"]

    node: "Network"

    def __init__(self, node: "Network", name: str, /, id: int, flag: PortFlag = PortFlag.DEFAULT) -> None:
        super().__init__(node, name, flag)
        self.nid = id
    
    def get(self, /) -> BaseNode:
        super().get()
        return self.node.records.get(self.nid).node
    
    def set(self, node: BaseNode, /) -> None:
        node.throw(
            kes_exc.PortError(
                "cannot write to node record",
                self.name
            )
        )


class Network(Node):
    __slots__ = ["records", "event_map", "stopping"]

    records: AbstractRecordManager

    def __init__(self, net: "Network") -> None:
        super().__init__(net)
        self.records = RecordManager()
        self.event_map = defaultdict(list)
        self.stopping = False
    
    def node_new(self, type: Type[BaseNode], *args, **kwds) -> None:
        self.send_event_inner(
            kes_evt.NodeNewEvent(type, *args, **kwds)
        )
    
    def node_drop(self, nid: int) -> None:
        self.send_event_inner(
            kes_evt.NodeDropEvent(nid)
        )
    
    @on(kes_msg.NodeInitializeMessage)
    def on_initialize(self, message: kes_msg.NodeInitializeMessage) -> None:
        self.send_event_inner(kes_evt.NetworkInitializeEvent())
    
    @on(kes_msg.NodeFinalizeMessage)
    def on_finalize(self, message: kes_msg.NodeFinalizeMessage) -> None:
        self.send_event_inner(kes_evt.NetworkFinalizeEvent())
    
    @on(kes_evt.Event)
    def on_event(self, event: kes_evt.Event) -> None:
        handled = False
        e = event.add_traceback(self)
        for tp in event.__class__.__mro__:
            if tp not in self.event_map:
                continue
            handled = True
            for i in self.event_map[tp]:
                self.send_message(i, e)
        if (not handled and kes_evt.EventMode.PROPAGATE == event.mode) or kes_evt.EventMode.FORCE_PROPAGATE == event.mode:
            return self.send_event(event)
        elif not handled and kes_evt.EventMode.THROW_ERR == event.mode:
            self.throw(kes_exc.UnsupportedMessageError(f"unsupported event {event}"))
    
    @on(kes_evt.NodeNewEvent, flag=HandlerFlag.PROPAGATE)
    def on_node_new(self, event: kes_evt.NodeNewEvent) -> None:
        if self.stopping:
            kes_exc.RuntimeError("cannot alloc node when the network was stopping").throw()
        node = self._node_alloc(event.type, *event.args, **event.kwargs)
        node.send_message(node, kes_msg.NodeInitializeMessage())
    
    @on(kes_evt.NodeDropEvent, flag=HandlerFlag.PROPAGATE)
    def on_node_drop(self, event: kes_evt.NodeDropEvent) -> None:
        self._node_dealloc(event.nid, disconnect=True)
        if self.stopping and not self.records:
            self.drop()
    
    @on(kes_evt.NodeTransferEvent, flag=HandlerFlag.PROPAGATE)
    def on_node_transfer(self, event: kes_evt.NodeTransferEvent) -> None:
        node = event.node
        self._node_receive(node)
    
    @on(kes_evt.NetworkInitializeEvent, flag=HandlerFlag.PROPAGATE)
    def on_net_initialize(self, event: kes_evt.NetworkInitializeEvent) -> None:
        for i in self.records:
            i.node.send_message_inner(kes_msg.NodeInitializeMessage())
    
    @on(kes_evt.NetworkFinalizeEvent, flag=HandlerFlag.PROPAGATE)
    def on_net_finalize(self, event: kes_evt.NetworkFinalizeEvent) -> None:
        self.stopping = True
        if not self.records:
            self.drop()
            return
        for i in self.records:
            self.send_message(i.node, kes_msg.NodeFinalizeMessage())

    def send_event_inner(self, event: kes_evt.Event) -> None:
        self.send_message_inner(event)
    
    @overload
    def throw_inner(self, exception: "kes_exc.Exception", *, cancel: Literal[False]) -> None: ...
    @overload
    def throw_inner(self, exception: "kes_exc.Exception", *, cancel: Literal[True] = True) -> NoReturn: ...

    def throw_inner(self, exception: "kes_exc.Exception", *, cancel: bool = True) -> None:
        self.send_message(self, exception)
        if cancel:
            raise kes_exc.NodeCancelledError(exc=exception)
    
    send_exception_inner = throw_inner

    def _node_alloc(self, node: Type[T_Node], *args, **kwds) -> T_Node:
        node_ins = node(self, *args, **kwds)
        nid = self.records.new(node_ins)
        node_ins.nid = nid
        return node_ins
    
    def _node_dealloc(self, nid: int, *, disconnect: bool = False) -> None:
        if disconnect:
            for i in self.records:
                with suppress(kes_exc.NodeCancelledError):
                    i.next.discard(nid)
        phantom_net = phantom_net_factory()
        if phantom_net is not None:
            self._node_transfer(nid, phantom_net)
            return
        n_ref = ref(self.records.drop(nid))
        gc.collect()
        if (node := n_ref) is not None:
            self.throw_inner(
                kes_exc.RuntimeError(f"the node {node!r} has additional references and cannot be released")
            )
    
    def _node_transfer(self, nid: int, target: "Network") -> None:
        node = self.records.drop(nid)
        self.send_message(
            target,
            kes_evt.NodeTransferEvent(node)
        )
    
    def _node_receive(self, node: BaseNode) -> None:
        nid = self.records.new(node)
        node.net = self
        node.nid = nid
    
    def _record_next(self, nid: int) -> List[BaseNode]:
        return [self.records.get(i).node for i in self.records.get(nid).next]
    
    def _connect(self, s_id: int, t_id: int) -> None:
        self.records.get(s_id).next.add(t_id)
    
    def _export(
            self,
            name_or_port: Union[str, AbstractPort],
            /,
            flag: PortFlag = PortFlag.DEFAULT,
            nid: Optional[int] = None
    ) -> None:
        if nid is not None:
            assert isinstance(name_or_port, str)
            name_or_port = RecordPort(self, name_or_port, nid, flag)
        return super()._export(name_or_port, flag)
    
    def _register_event(self, event: Type[kes_evt.Event], node: BaseNode) -> None:
        self.event_map[event].append(node)
    
    def _unregister_event(self, event: Type[kes_evt.Event], node: BaseNode) -> None:
        if node not in self.event_map[event]:
            self.throw_inner(
                kes_exc.ValueError(f"unregistered node {node}")
            )
        self.event_map[event].remove(node)
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__qualname__} net in net {self.net!r} at 0x{id(self):016X}>"


def phantom_net_factory() -> Optional[Network]:
    return
    