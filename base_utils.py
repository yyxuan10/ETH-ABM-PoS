import networkx as nx

from consensus_utils import *
from visualizations import *


class Block:
    '''
    Class for blocks.

    INPUT:
    emitter          - List of objects
    parent           - Block object (parent of the block)
    transactions     - Number (integer) of transactions in the block
    '''
    counter = 0

    @classmethod
    def __update(cls):
        cls.counter += 1

    def __init__(self, value, emitter="genesis", parent=None):

        self.id = self.counter
        self.__update()

        self.children = set()
        self.parent = parent
        self.value = value

        if parent == None:
            self.parent = None
            self.height = 0
            self.emitter = "genesis"
            self.predecessors = {self}

        else:
            self.parent = parent
            self.height = self.parent.height + 1
            self.emitter = emitter
            parent.children.add(self)
            self.predecessors = parent.predecessors.copy()
            self.predecessors.add(self)

    def __repr__(self):
        return '<Block {} (h={}) (v={})>'.format(self.id, self.height, self.value)

    def __next__(self):
        if self.parent:
            return self.parent
        else:
            raise StopIteration

class Node:
    '''Class for the validator.

    INPUT:
    - blockchain,   list of Block objects,
    '''
    counter = 0

    def __init__(self, block, rng):
        Node.counter += 1
        self.id = self.counter

        self.rng = rng

        self.local_blockchain = {block[0]}
        self.global_blockchain = block
        self.current_block = block[0]  # A Blockchain has to be initialized
        self.neighbors = set()  # set of neighbours peers on the p2p network
        self.non_gossiped_to = set()  # set of neighbour peers self.Node didn't gossip to

        self.attestations_ledger = AttestationsLedger(self, self.rng)
        self.is_attesting = False

    def propose_block(self, value):
        head_of_chain = self.use_lmd_ghost()
        new_block = Block(value, emitter=self, parent=head_of_chain)
        self.local_blockchain.add(new_block)

        self.global_blockchain.append(new_block)

        # tracks the neighbours self.Node didnt gossip
        self.non_gossiped_to = self.neighbors.copy()

        # draw_chain(self)
        return

    def is_gossiping(self):
        """If the set of nodes self.Node hasnt gossiped to it's empty,
        self.Node doesn't need to gossip anymore then self.is_gossiping it's False.
        """
        if self.non_gossiped_to:
            return True
        else:
            return False

    def update_local_blockchain(self, block):
        """When self.Node receive a new block, update the local copy of the blockchain.
        """
        while block not in self.local_blockchain:
            self.local_blockchain.add(block)
            self.attestations_ledger.check_cache(block)
            block = block.parent

    # TODO: gossip blocks, naming should be changed accordingly
    def gossip(self, listening_node):
        # self.non_gossiped_to.remove(listening_node)
        listening_node.listen(self)

    # TODO: listen blocks, naming should be changed accordingly
    def listen(self, gossiping_node):
        """Receive new block and update local information accordingly.
        """
        block = gossiping_node.use_lmd_ghost()
        self.update_local_blockchain(block)
        self.non_gossiped_to = self.neighbors.copy()
        self.non_gossiped_to.remove(gossiping_node)

        if self.is_attesting == True:
            self.attestations_ledger.attest()

    def use_lmd_ghost(self):
        return lmd_ghost(self.local_blockchain, self.attestations_ledger.attestations)

    def __repr__(self):
        return '<Node {}>'.format(self.id)


class Network:
    """Object to manage the peer-to-peer network. It is a wrapper of networkx.Graph right now.
    INPUT
    - G,    a networkx.Graph object
    """

    import networkx as nx

    def __init__(self, G):
        # G is a networkx Graph
        self.network = G

    def __len__(self):
        return len(self.network)

    # TODO: nodes -> peers
    def set_neighborhood(self, nodes):
        # dict map nodes in the nx.graph to nodes on p2p network
        nodes_dict = dict(zip(self.network.nodes(), nodes))
        # save peer node object as an attribute of nx node
        nx.set_node_attributes(self.network, values=nodes_dict, name='name')

        for n in self.network.nodes():
            m = self.network.nodes[n]["name"]
            # save each neighbour in the nx.Graph inside the peer node object
            for k in self.network.neighbors(n):
                m.neighbors.add(self.network.nodes[k]["name"])


class Message():
    """It wraps attestation with respective recipient.
    INPUTS:
    - attestation,  Attestation object
    - reciptient,   Node object
    """
    __slots__ = ('attestation', 'recipient')

    def __init__(self, attestation, recipient):
        self.attestation = attestation
        self.recipient = recipient

    def return_attestation(self):
        return self.attestation

    def __eq__(self, other):
        return self.attestation == other.attestation and self.recipient == other.recipient

    def __hash__(self):
        return hash((self.attestation, self.recipient))

    def __repr__(self):
        return '<Message: {} for recipient {}>'.format(str(self.attestation).strip('<>'), self.recipient.id)


class Attestation():
    """It wraps a block to a node. In the context of attestation, 
    the block is the attested block and the node is the attestor.
    INPUTS:
    - attestor,  Node object
    - block,     Block object
    """
    __slots__ = ('attestor', 'block')

    def __init__(self, attestor, block):
        self.attestor = attestor
        self.block = block

    def as_dict(self):
        return {self.attestor: self.block}

    def __eq__(self, other):
        return self.attestor == other.attestor and self.block == other.block

    def __hash__(self):
        return hash((self.attestor, self.block))

    def __repr__(self):
        return '<Attestation: Block {} by node {}>'.format(self.block.id, self.attestor.id)


class AttestationsLedger():
    """It manages and saves attestations for a node.
    INPUTS:
    - node,     a Node object
    """

    def __init__(self, node, rng):
        self.rng = rng
        self.node = node
        self.attestations = {}  # Node:Block
        self.message_queue = set()  # Message
        self.attestations_cache = set()  # Attestation

    def attest(self):
        """Create the Attestation for the current head of the chain block.
        """
        print('Block attested {} by node {}'.format(
            self.node.use_lmd_ghost(), self.node))
        attestation = Attestation(self.node, self.node.use_lmd_ghost())
        self.update_attestations(attestation)
        self.add_to_message_queue(attestation)  # init to send it out
        self.node.is_attesting = False # As a node has to attest only once in a slot

    def update_attestations(self, attestation):
        '''Expects an attestation object which is passed and then processed further.
        INPUTS:
        - attestation,  Attestation objectco
        OUTPUT:
        - Bool, whether or not the update takes place or not 
        '''
        # if node doesn't know the block the attestation is about, cache it
        if not attestation.block in self.node.local_blockchain:
            self.attestations_cache.add(attestation)
            return False
        # first time node receives attestation from specific attestor
        elif attestation.attestor not in self.attestations.keys():
            self.attestations[attestation.attestor] = attestation.block
            return True
        # node updates local latest attestation of the attestor
        elif attestation.attestor in self.attestations.keys():
            if attestation.block.id > self.attestations[attestation.attestor].id:
                # TODO: precaution block id used instead of block slot since lmd
                # TODO: epoch is the attestation timestamp-> use epoch
                self.attestations.update(attestation.as_dict())
                return True
        else:
            return False

    def add_to_message_queue(self, attestation):
        for n in self.node.neighbors:
            self.message_queue.add(Message(attestation, n))

    def select_attestation_message(self):
        s = self.rng.choice(list(self.message_queue))
        return s

    def send_attestation_message(self):
        if len(self.message_queue) > 0:
            message = self.select_attestation_message()
            self.message_queue.remove(message)
            # debug
            # print(str(self.node) + '  - sending ->  ' +
            #       str(message) + str(message.recipient))

            message.recipient.attestations_ledger.receive_attestation(self, message)

    def receive_attestation(self, other, message):
        attestation = message.attestation
        # debug
        # print(str(self.node) + '   <- receiving -  ' + str(message))

        if self.update_attestations(attestation):
            self.add_to_message_queue(attestation)

    def check_cache(self, block):
        """Manage the cache after receiving a new block.
        If the block was cached, removes all attestations related to 
        the block from the cache and update local attestations.
        When the node receive a block he alreaqdy had attestations for
        the node needs to update the cache.
        """
        # create set of blocks in the cache
        cached_blocks = set([a.block for a in self.attestations_cache])
        if block in cached_blocks:
            clear_cache = set()
            for a in self.attestations_cache:
                if a.block == block:
                    clear_cache.add(a)
                    self.update_attestations(a)
            self.attestations_cache = self.attestations_cache - clear_cache