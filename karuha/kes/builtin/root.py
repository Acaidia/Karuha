import asyncio
from typing import Callable, Dict, Type, TypeVar

from ..core import BaseNode, Network, HandlerFlag, on, kes_evt, kes_exc


_T_NodeCls = TypeVar("_T_NodeCls", bound=Type[BaseNode])


class RootNetwork(Network):
    __slots__ = []

    __builtin_node__: Dict[str, Type[BaseNode]] = {}
    
    def __init__(self) -> None:
        super().__init__(self)
        self.records.new(self)
        for k, v in self.__builtin_node__.items():
            node = self._node_alloc(v)
            self._export(k, nid=node.nid)

    @on(kes_exc.Exception)
    def on_exception(self, exc: kes_exc.Exception) -> None:
        asyncio.get_running_loop().stop()
    
    @on(kes_evt.NodeDropEvent, flag=HandlerFlag.PROPAGATE)
    async def on_node_drop(self, event: kes_evt.NodeDropEvent) -> None:
        if event.nid == 0:
            asyncio.get_running_loop().stop()
        elif event.nid != 1:
            await super().on_node_drop(event)
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__qualname__} root net in at 0x{id(self):016X}>"


root_net: RootNetwork = RootNetwork()


def set_root_net(net: RootNetwork) -> None:
    global root_net
    root_net = net


def get_root_net() -> RootNetwork:
    return root_net


def builtin_node(name: str) -> Callable[[_T_NodeCls], _T_NodeCls]:
    def inner(cls: _T_NodeCls) -> _T_NodeCls:
        RootNetwork.__builtin_node__[name] = cls
        return cls
    return inner
