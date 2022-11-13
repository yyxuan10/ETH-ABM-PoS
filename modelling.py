import networkx as nx
import numpy as np

from base_utils import *
from malicious_node import *
from Gillespie import *
from fixedEvents import *
from randomProcess import *


class Model:
    '''
    This is used to build the network needed and parameterize the Gillespie Model
    Initiates the model and builds it around the parameters given model.gillespie.run to run the simulation.
    All objects are contained in the class.
    '''

    def __init__(self,
                 graph=None,
                 tau_block=None,
                 tau_attest=None,
                 seed=None,
                 malicious_percent=0.6
                 ):

        self.rng = np.random.default_rng(seed)
        self.tau_block = tau_block
        self.tau_attest = tau_attest

        self.blockchain = [Block('0', 'genesis')]
        self.network = Network(graph)
        self.no_of_malicious_nodes = np.floor(
            malicious_percent * len(self.network)).astype(int)
        self.no_of_nodes = len(self.network) - self.no_of_malicious_nodes

        self.nodes = []
        self.nodes.extend([Node(self.blockchain, rng=self.rng)
                           for i in range(self.no_of_nodes)])
        self.nodes.extend([MaliciousNode(self.blockchain, rng=self.rng)
                           for i in range(self.no_of_malicious_nodes)])

        self.validators = self.nodes

        self.network.set_neighborhood(self.nodes)
        self.edges = [(n, k) for n in self.nodes for k in n.neighbors]

        self.block_gossip_process = BlockGossipProcess(
            tau=self.tau_block, edges=self.edges)
        self.attestation_gossip_process = AttestationGossipProcess(
            tau=self.tau_attest, nodes=self.nodes)

        self.epoch_boundary = EpochBoundary(
            32*12, self.validators, rng=self.rng)
        self.slot_boundary = SlotBoundary(
            12, self.validators, self.epoch_boundary, rng=self.rng)
        self.attestation_boundary = AttestationBoundary(
            12, offset=4, slot_boundary=self.slot_boundary, epoch_boundary=self.epoch_boundary, rng=self.rng)

        self.processes = [self.block_gossip_process,
                          self.attestation_gossip_process]
        self.fixed_events = [self.epoch_boundary,
                             self.slot_boundary, self.attestation_boundary]

        self.gillespie = Gillespie(self.processes, self.rng)
        self.time = 0

    def run(self, stoping_time):

        while self.time < stoping_time:
            # generate next random increment time and save it in self.increment
            increment = self.gillespie.calculate_time_increment()

            # loop over fixed events and trigger if time passes fixed event time
            for fixed in self.fixed_events:
                fixed.trigger(self.time + increment)

            # select poisson process and trigger selected process
            next_process = self.gillespie.select_event()
            next_process.event()

            self.time += increment

    def results(self):
        d = {"test": 1}
        return d


if __name__ == "__main__":
    # As mentioned in the Stochatic Modelling paper,
    # the number of neighbors fixed but have to experiment multiple topologies
    net_p2p = nx.random_degree_sequence_graph(
        [10 for i in range(100)])
    lcc_set = max(nx.connected_components(net_p2p), key=len)
    net_p2p = net_p2p.subgraph(lcc_set).copy()
    net_p2p = nx.convert_node_labels_to_integers(
        net_p2p, first_label=0)
    model = Model(
        graph=net_p2p,
        tau_block=1,
        tau_attest=1
    )
    model.run(2e2)
    model.results()