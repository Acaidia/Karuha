from ..core import Network, kes_msg
from .root import get_root_net, builtin_node
from .phantom import PhantomNetworkManager


@builtin_node("temp_net")
class TempNetwork(Network):
    __slots__ = []

    records: PhantomNetworkManager

    def __init__(self, net: Network) -> None:
        super().__init__(net)
        self.records = PhantomNetworkManager()

 

def get_temp_net() -> TempNetwork:
    return get_root_net()._get_port("temp_net")
