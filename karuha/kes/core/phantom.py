from typing import Dict, Iterator, NoReturn, Optional
from weakref import ref

from .node import BaseNode, on
from .record import AbstractRecordManager
from .network import Network
from . import message as kes_msg
from . import event as kes_evt
from . import exception as kes_exc


class PhantomRecord:
    __slots__ = ["_node_ref"]
    
    def __init__(self, /, node: BaseNode) -> None:
        self._node_ref = ref(node)
    
    @property
    def node(self) -> BaseNode:
        node = self._node_ref()
        if node is None:
            kes_exc.RuntimeError("node has been released").throw()
        return node
    
    @property
    def next(self) -> NoReturn:
        kes_exc.RuntimeError("no connection info for a phantom record").throw()
    
    @property
    def valid(self) -> bool:
        return self._node_ref() is not None


class PhantomNetworkManager(AbstractRecordManager):
    __slots__ = ["_records", "_count"]

    def __init__(self) -> None:
        super().__init__()
        self._records: Dict[int, PhantomRecord] = {}
        self._count = 0
    
    def get(self, nid: int) -> PhantomRecord:
        if nid in self._records:
            record = self._records[nid]
            if record.valid:
                return record
            del self._records[nid]
        kes_exc.RuntimeError(f"there is no node with id {nid}").throw()
    
    def new(self, node: BaseNode) -> int:
        count = self._count
        self._records[count] = PhantomRecord(node)
        self._count += 1
        return count

    def drop(self, nid: int) -> BaseNode:
        node = self.get(nid).node
        del self._records[nid]
        return node

    def gc(self) -> None:
        released = [
            i for i, rd in self._records.items() if not rd.valid
        ]
        for i in released:
            del self._records[i]
    
    def __iter__(self) -> Iterator[PhantomRecord]:
        released = []
        for i, rd in self._records.items():
            if rd.valid:
                yield rd
            else:
                released.append(i)
        for i in released:
            self._records.pop(i, None)


class PhantomNetwork(Network):
    __slots__ = ["nid"]

    records: PhantomNetworkManager

    def __init__(self, net: Network) -> None:
        super().__init__(net)
        self.records = PhantomNetworkManager()
    
    @on(kes_evt.NodeNewEvent)
    def on_node_new(self, event: kes_evt.Event) -> NoReturn:
        self.throw(kes_exc.UnsupportedMessageError("cannot alloc a node in phantom network"))
    
    @on(kes_evt.NodeDropEvent)
    def on_node_drop(self, event: kes_evt.Event) -> None:
        pass
    

phantom_net: PhantomNetwork


def set_phantom_net(net: PhantomNetwork) -> None:
    global phantom_net
    phantom_net = net


def get_phantom_net() -> PhantomNetwork:
    return phantom_net
