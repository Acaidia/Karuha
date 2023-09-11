import asyncio

from .node import Export, HandlerFlag, on
from .network import Network
from .phantom import PhantomNetwork, set_phantom_net
from . import event as kes_evt
from . import exception as kes_exc


class RootNetwork(Network):
    __slots__ = ["phantom_net"]

    phantom_net: Export[PhantomNetwork]

    def __init__(self) -> None:
        super().__init__(self)
        self.records.new(self)
        self.phantom_net = self._node_alloc(PhantomNetwork)

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
        return f"<{self.__class__.__qualname__} root net in at 0x{id(self):#016X}>"


root_net: RootNetwork = RootNetwork()
set_phantom_net(root_net.phantom_net)


def set_root_net(net: RootNetwork) -> None:
    global root_net
    root_net = net
    set_phantom_net(root_net.phantom_net)


def get_root_net() -> RootNetwork:
    return root_net
