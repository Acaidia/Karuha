from unittest import IsolatedAsyncioTestCase

from karuha.kes import Network, Node, kes_msg
from karuha.kes.core.root import RootNetwork
from karuha.kes.root import root_net


class TestKES(IsolatedAsyncioTestCase):
    def test_core(self) -> None:
        self.assertGreaterEqual(len(Node.__message_handler__), 4)
        self.assertGreaterEqual(len(Network.__message_handler__), 7)
        self.assertIs(Node.on_port_get.message_type, kes_msg.PortGet)
        del Node.on_port_set.__orig_class__
        self.assertIs(Node.on_port_set.message_type, kes_msg.PortSet)
        # self.assertEqual(RootNetwork.__export_attr__, {"phantom_net"})
    
    async def test_record(self) -> None:
        node1 = Node(root_net)
        self.assertFalse(hasattr(node1, "nid"))
        node2 = root_net._node_alloc(Node)
        self.assertEqual(node2.nid, 2)
        self.assertIs(root_net.records.get(2).node, node2)
        root_net._node_dealloc(2)
        with self.assertRaises(RuntimeError):
            root_net.records.get(2)
    
    def test_root(self) -> None:
        net = root_net._node_alloc(Network)
        self.assertIs(net.net, root_net)
        
