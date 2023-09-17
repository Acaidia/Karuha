from unittest import IsolatedAsyncioTestCase

from karuha.kes import Network, Node, kes_msg, kes_evt
from karuha.kes.core import network
from karuha.kes.builtin.phantom import PhantomNetworkManager
from karuha.kes.root import root_net
from karuha.kes.api import kes_init


class TestKES(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        kes_init()

    def test_core(self) -> None:
        self.assertGreaterEqual(len(Node.__message_handler__), 4)
        self.assertGreaterEqual(len(Network.__message_handler__), 7)
        self.assertIs(Node.on_port_get.message_type, kes_msg.PortGet)
        del Node.on_port_set.__orig_class__
        self.assertIs(Node.on_port_set.message_type, kes_msg.PortSet)
        ph_net = network.phantom_net_factory()
        self.assertIs(root_net._get_port("phantom_net"), ph_net)
        self.assertIs(root_net.records.get(1).node, ph_net)
    
    async def test_record(self) -> None:
        node1 = Node(root_net)
        self.assertFalse(hasattr(node1, "nid"))
        node2 = root_net._node_alloc(Node)
        self.assertIs(root_net.records.get(node2.nid).node, node2)
        root_net._node_dealloc(node2.nid)
        with self.assertRaises(RuntimeError):
            root_net.records.get(node2.nid)
    
    def test_phantom(self) -> None:
        rdm = PhantomNetworkManager()
        node0 = Node(root_net)
        rdm.new(node0)
        self.assertEqual(node0.nid, 0)
        self.assertIs(node0, rdm.get(0).node)
        del node0
        with self.assertRaises(RuntimeError):
            rdm.get(0)
        node1 = Node(root_net)
        rdm.new(node1)
        self.assertEqual(node1.nid, 1)
    
    async def test_root(self) -> None:
        root_net.node_new(Network)
        root_net
        