from unittest import TestCase
from karuha.kes import Node, Network, kes_msg


class TestKES(TestCase):
    def test_core(self) -> None:
        self.assertEqual(2, len(Node.__message_handler__))
        self.assertEqual(3, len(Network.__message_handler__))
        self.assertIs(Node.on_port_get.message_type, kes_msg.PortGet)
        del Node.on_port_set.__orig_class__
        self.assertIs(Node.on_port_set.message_type, kes_msg.PortSet)
