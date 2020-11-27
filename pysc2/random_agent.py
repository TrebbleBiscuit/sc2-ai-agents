from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy

import random
import numpy as np
import pandas as pd
import os
from absl import app
from pysc2.agents import base_agent
from pysc2.lib import actions, features, units
from pysc2.env import sc2_env, run_loop


class RandomAgent(base_agent.BaseAgent):
  """A random agent for starcraft."""

  def step(self, obs):
    super(RandomAgent, self).step(obs)
    function_id = numpy.random.choice(obs.observation.available_actions)
    args = [[numpy.random.randint(0, size) for size in arg.sizes]
            for arg in self.action_spec.functions[function_id].args]
    return actions.FunctionCall(function_id, args)


class MyAgent(base_agent.BaseAgent):

  def __init__(self):
    self.reward = 0
    self.episodes = 0
    self.steps = 0
    self.obs_spec = None
    self.action_spec = None

  def setup(self, obs_spec, action_spec):
    self.obs_spec = obs_spec
    self.action_spec = action_spec

  def reset(self):
    self.episodes += 1

  def step(self, obs):
    super(MyAgent, self).step(obs)
    self.steps += 1
    self.reward += obs.reward
    function_id = numpy.random.choice(obs.observation.available_actions)
    args = [[numpy.random.randint(0, size) for size in arg.sizes]
            for arg in self.action_spec.functions[function_id].args]
    return actions.FunctionCall(function_id, args)


def main(unused_argv):
  agent1 = MyAgent()
  agent2 = RandomAgent()
  try:
    with sc2_env.SC2Env(
        map_name="Simple64",
        players=[sc2_env.Agent(sc2_env.Race.terran), 
                 sc2_env.Agent(sc2_env.Race.terran)],
        agent_interface_format=features.AgentInterfaceFormat(
            action_space=actions.ActionSpace.RAW,
            use_raw_units=True,
            raw_resolution=64,
        ),
        step_mul=48,
        disable_fog=True,
    ) as env:
      run_loop.run_loop([agent1, agent2], env, max_episodes=1000)
  except KeyboardInterrupt:
    pass


if __name__ == "__main__":
  app.run(main)