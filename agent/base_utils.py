import networkx as nx
import numpy as np


class Network:
    """Object to manage the peer-to-peer network. It is a wrapper of networkx.Graph right now.
    INPUT
    - G,    a networkx.Graph object
    """

    def __init__(self, graph):
        # G is a networkx Graph
        self.graph = graph

    def __len__(self):
        return len(self.graph)

    def set_neighborhood(self, honest_nodes, malicious_nodes):
        # dictionary mapping nodes in the nx.graph to their peers on p2p graph

        # Shuffle the nodes to
        peers_dict = dict(
            zip(self.graph.nodes(), [*honest_nodes, *malicious_nodes]))

        malicious_peer_dict = {v: k for k,
                               v in peers_dict.items() if v in malicious_nodes}

        # save peer node object as an attribute of nx node
        nx.set_node_attributes(
            self.graph, values=peers_dict, name='node_mapping')

        for n in self.graph.nodes():
            node_object = self.graph.nodes[n]["node_mapping"]
            # save each neighbour in the nx.Graph inside the peer node object
            for k in self.graph.neighbors(n):
                node_object.neighbors.add(self.graph.nodes[k]["node_mapping"])

        # save each malcious neighbour inside the peer node object and add an edge in the graph
        for node_object in malicious_nodes:
            for node_object2 in malicious_nodes:
                if node_object == node_object2:
                    continue
                node_object.malicious_neighbors.add(node_object2)
                self.graph.add_edges_from(
                    [(malicious_peer_dict[node_object], malicious_peer_dict[node_object2])])


class Block:
    '''
    Class for blocks.

    INPUT:
    value            - blocks values (this is arbitray value) used to differentiate the generation.
    emitter          - List of objects
    slot             - slot of the block
    parent           - Block object (parent of the block)
    transactions     - Number (integer) of transactions in the block
    '''
    counter = 0

    @classmethod
    def __update(cls):
        cls.counter += 1

    def __init__(self, value, emitter, slot, parent=None):

        self.id = self.counter
        self.__update()
        self.children = set()
        self.parent = parent
        self.value = value

        if parent == None:
            self.parent = None
            self.height = 0
            self.emitter = "genesis"
            self.slot = slot
            self.predecessors = {self}

        else:
            self.parent = parent
            self.height = self.parent.height + 1
            self.emitter = emitter
            parent.children.add(self)
            self.predecessors = parent.predecessors.copy()
            self.predecessors.add(self)
            self.slot = slot

    def __repr__(self):
        return '<Block {} (h={}) (v={})>'.format(self.id, self.slot, self.value)

    def __next__(self):
        if self.parent:
            return self.parent
        else:
            raise StopIteration


class Attestation():
    """It wraps a block to a node. In the context of attestation, 
    the block is the attested block and the node is the attestor.
    INPUTS:
    - attestor,  Node object
    - block,     Block object
    """

    def __init__(self, attestor, block, slot):
        self.attestor = attestor
        self.block = block
        self.slot = slot

    def as_dict(self):
        return {self.slot: {self.attestor: self.block}}

    def __eq__(self, other):
        return self.attestor == other.attestor and self.block == other.block and self.slot == self.slot

    def __hash__(self):
        return hash((self.attestor, self.slot, self.block))

    def __repr__(self):
        return '<Attestation: Block {} by node {}>'.format(self.block.id, self.slot, self.attestor.id)