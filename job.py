import simulation


class Job(object):
  def __init__(self, target=None, obj=None, duration=10, timestamp=None):
    super(Job,self).__init__()
    self.target = target
    self.obj = obj
    self.amountToDo = duration
    self.timestamp = timestamp
    self.claimants = []
  def __repr__(self):
    return "<Job target=%s, obj=%s>" % (self.target, self.obj)
  def isSimilar(self, other):
    return (type(self) == type(other) 
            and self.target == other.target 
            and self.obj == other.obj)
  def Start(self, claimant):
    pass
  def isDone(self): return self.amountToDo <= 0
  def Work(self, claimant):
    self.amountToDo -= 1
  def Finish(self, claimant):
    pass
  def CellsToWorkFrom(self):
    return [cell for cell in self.target.ExistingNeighbors() if cell.isTraversable()]


class Construct(Job):
  def Finish(self, claimant):
    # target is a cell
    print "Job.Finish()"
    self.target.Discard(simulation.DECK)
    self.target.Discard(simulation.BULKHEAD)
    if self in self.target._futureLook:
      self.target._futureLook.remove(self)  # sometimes fails
    self.target.Add(self.obj)
    self.target.Changed()
    super(Construct,self).Finish(claimant)
    print "Job.Finished"

class Unconstruct(Job):
  def Finish(self, claimant):
    self.target.Discard(DECK)
    self.target.Discard(BULKHEAD)
    if self in self.target._futureLook:
      self.target._futureLook.remove(self)
    self.target.Changed()
    super(Unconstruct, self).Finish(claimant)
