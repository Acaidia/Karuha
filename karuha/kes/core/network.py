import asyncio
from typing import List, NamedTuple, Optional, Set, Type, TypeVar, Union

from .message import Event, Message
from .node import BaseNode, HandlerFlag, Node, AbstractPort, PortFlag, on
from . import exception as kes_exc


T_Node = TypeVar("T_Node", bound=BaseNode)


class NodeRecord(NamedTuple):
    node: BaseNode
    next: Set[int]


class RecordPort(AbstractPort):
    __slots__ = ["nid"]

    node: "Network"

    def __init__(self, node: "Network", name: str, /, id: int, flag: PortFlag = PortFlag.DEFAULT) -> None:
        super().__init__(node, name, flag)
        self.nid = id
    
    def get(self, /) -> BaseNode:
        super().get()
        return self.node.records[self.nid].node
    
    def set(self, node: BaseNode, /) -> None:
        node.throw(
            kes_exc.PortError(
                "cannot write to node record",
                node, "WRITE", self.name
            )
        )


class Network(Node):
    __slots__ = ["records", "event_map"]

    def __init__(self, net: "Network", id: int) -> None:
        super().__init__(net, id)
        self.records: List[NodeRecord] = []
        self.event_map = {}
    
    def node_new(self, node: Type[T_Node], *args, **kwds) -> T_Node:
        node_ins = node(self, len(self.records), *args, **kwds)
        self.records.append(NodeRecord(node_ins, set()))
        return node_ins
    
    def node_del(self, nid: int, *, disconnect: bool = False) -> None:
        if disconnect:
            for i in self.records:
                i.next.discard(nid)
        self._get_record(nid)
        del self.records[nid]
    
    def node_next(self, nid: int) -> List[BaseNode]:
        return [self._get_record(i).node for i in self._get_record(nid).next]
    
    def export(
            self,
            name_or_port: Union[str, AbstractPort],
            /,
            flag: PortFlag = PortFlag.DEFAULT,
            nid: Optional[int] = None
    ) -> None:
        if nid is not None:
            assert isinstance(name_or_port, str)
            name_or_port = RecordPort(self, name_or_port, nid, flag)
        return super().export(name_or_port, flag)
    
    def connect(self, s_id: int, t_id: int) -> None:
        self._get_record(s_id).next.add(t_id)
    
    def send_message(self, node: BaseNode, message: Message) -> None:
        asyncio.create_task(node.handle_message(message))
    
    @on(Event, flag=HandlerFlag(0))
    def on_event(self, event: Event) -> None:
        if event not in self.event_map:
            return self.send_message(self.net, event)
        for i in self.event_map[event]:
            self.send_message(i, event)

    def _get_record(self, nid: int, /) -> NodeRecord:
        if nid < 0 or nid >= len(self.records):
            err = kes_exc.ValueError(f"index {nid} out of range")
            self.send_message(self, err)
            raise kes_exc.NodeCancelledError(exc=err)
        return self.records[nid]
