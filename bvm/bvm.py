#!/usr/bin/env python3

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
from mesa import Agent, Model
from mesa.time import RandomActivation
from mesa.datacollection import DataCollector
from mesa.batchrunner import BatchRunner
from enum import Enum
import logging
import time
import subprocess
import sys
import glob

logging.basicConfig(level=logging.INFO)

Opinion = Enum('Opinion', 'RED BLUE')

class VoterAgent(Agent):

    max_id = 0

    def __init__(self, unique_id, model, opinion=None):
        super().__init__(unique_id, model)
        VoterAgent.max_id = max(VoterAgent.max_id, unique_id)
        if opinion:
            self.opinion = opinion
        else:
            self.opinion = np.random.choice([Opinion.RED, Opinion.BLUE])
        logging.debug("Agent {} is {}.".format(self.unique_id, self.opinion))

    def step(self):
        logging.debug("Running agent {}...".format(self.unique_id))
        neis = self.model.G.adj[self.unique_id]
        if len(neis) == 0:
            logging.debug("  Agent {} has no neighbors!".format(self.unique_id))
        else:
            nei = self.model.schedule.agents[np.random.choice(neis)]
            if self.opinion != nei.opinion:
                logging.debug("  Agent {} listens to {}, becomes {}.".format(
                    self.unique_id, nei.unique_id, nei.opinion))
                self.opinion = nei.opinion
            else:
                logging.debug("  (Agents {} and {} already agree on {}.)"
                    .format(self.unique_id, nei.unique_id, nei.opinion))
        

    def __str__(self):
        return "Agent {}".format(self.unique_id)

    def __repr__(self):
        return "Agent {}".format(self.unique_id)


def frac_with_opinion(agents, opinion):
    return sum([ a.opinion == opinion
        for a in agents ]) / len(agents)


def iters_to_converge(model):
    return model.num_steps

def compute_lambda(model):
    return model.num_agents * model.p

class SocialWorld(Model):

    def __init__(self, N, p):
        logging.info("Initializing SocialWorld({},{})...".format(N,p))
        self.num_agents = N
        self.p = p
        self.schedule = RandomActivation(self)
        self.num_steps = 0
        self.G = nx.erdos_renyi_graph(N, p)
        while not nx.is_connected(self.G):
            self.G = nx.erdos_renyi_graph(N, p)

        # Attaching each VoterAgent object to one of the graph's node's
        # attribute dicts. (Seems nicer to make the node actually *be* the
        # VoterAgent, but can't figure out how to do this in networkx when
        # generating a random graph.)
        for i in range(self.num_agents):
            a = VoterAgent(i, self)
            self.G.nodes[i]["agent"] = a
            self.schedule.add(a)
        self.running = True   # could set this to stop prematurely

        self.datacollector = DataCollector(
            agent_reporters={},
            model_reporters={
                "FracRed": lambda model:
                    frac_with_opinion(model.schedule.agents, Opinion.RED) })

    def step(self):
        if not self.running:
            return
        if all([ a.opinion == self.schedule.agents[0].opinion
                for a in self.schedule.agents[1:] ]):
            logging.info("Simulation converged to {} in {} iterations."
                .format(self.schedule.agents[0].opinion, self.num_steps))
            self.running = False
        self.num_steps += 1
        logging.debug("Iteration {}...".format(self.num_steps))
        self.datacollector.collect(self)
        self.schedule.step()


    def run(self, num_steps=50):
        for _ in range(num_steps):
            self.step()



if __name__ == "__main__":

    if len(sys.argv) <= 1:
        print("Usage: bvm.py single|batch.")
        sys.exit()

    if sys.argv[1] == "single":

        # Single simulation run.
        m = SocialWorld(100, .2, VoterAgent)
        m.run(5000)

    else:

        # Batch simulation run.
        fixed = {"p":.2}
        variable_params = {"N": np.arange(10,100,5)}

        batch_run = BatchRunner(SocialWorld, variable_params, fixed,
            iterations=10, max_steps=1000,
            model_reporters={"lambda":compute_lambda,
                "itersToConverge": iters_to_converge})

        batch_run.run_all()
        df = batch_run.get_model_vars_dataframe()
        plt.figure()
        plt.scatter(df["lambda"], df.itersToConverge)
        plt.show()

        dfagg = df.groupby("lambda").itersToConverge.mean()
        plt.figure()
        plt.plot(dfagg.index,dfagg)
        plt.show()
