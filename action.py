"""This module defines Action objects."""

class Action(object):
  """A general thing a Player can do"""
  def __init__(self):
    super(Action, self).__init__()
  def Preempts(self, other): 
    return True
class Walk(Action):
  """Action to move a player in a certain direction"""
  def __init__(self, degrees):
    super(Walk, self).__init__()
    self.degrees = degrees
class GoTo(Action):
  """Action to send a player to a particular target location"""
  def __init__(self, there):
    super(GoTo, self).__init__()
    self.there = there
