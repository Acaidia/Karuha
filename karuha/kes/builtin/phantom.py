from typing import Iterator, NoReturn, Union
from weakref import ref, ReferenceType, WeakValueDictionary

from ..core import BaseNode, Network, on, kes_msg, kes_evt, kes_exc
from ..core import network
from ..core.record import AbstractRecordManager
from .root import get_root_net, builtin_node


class _PhantomRecord:
    __slots__ = ["_node_ref"]
    
    def __init__(self, /, node: Union[BaseNode, ReferenceType]) -> None:
        if isinstance(node, ReferenceType):
            self._node_ref = node
        else:
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
    __slots__ = ["_nodes", "_count"]

    def __init__(self) -> None:
        super().__init__()
        self._nodes: WeakValueDictionary[int, BaseNode] = WeakValueDictionary()
        self._count = 0
    
    def get(self, nid: int) -> _PhantomRecord:
        if nid not in self._nodes:
            kes_exc.RuntimeError(f"there is no node with id {nid}").throw()
        node = self._nodes[nid]
        return _PhantomRecord(node)
    
    def new(self, node: BaseNode) -> int:
        count = self._count
        self._nodes[count] = node
        self._count += 1
        return count

    def drop(self, nid: int) -> BaseNode:
        node = self.get(nid).node
        return node

    def __iter__(self) -> Iterator[_PhantomRecord]:
        yield from map(_PhantomRecord, self._nodes.valuerefs())


@builtin_node("phantom_net")
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


network.phantom_net_factory = lambda: get_root_net()._get_port("phantom_net")
