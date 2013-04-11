class SimObject(object):
  def __init__(self, parent=None):
    super(SimObject, self).__init__()
    self._parent = parent       # Containing SimObject - often a Cell
  def Parent(self): return self._parent
  def SetParent(self, newParent):
    if not self._parent is None:
      self._parent.Remove(self)
    if not newParent is None:
      newParent.Add(self)
    self._parent = newParent
  def RegisterComponent(self, components):
    "Install self to appropriate components."

  def Simulation(self):
    "Retrieve the top-level SimObject"
    return self._parent.Simulation()
  def Scheduler(self):
    "Retrieve the nearest Scheduler."
    return self._parent.Scheduler()
  def TileMap(self):
    return self._parent.TileMap()
  def PathsTo(self, there):
    return self.TileMap().PathsFromTo(self._parent.Pos(), there)
  def PathTo(self, there):
    return self.TileMap().PathFromTo(self._parent.Pos(), there)

  def Changed(self, what=None):
    "Propagate a change notice upwards."
    if what is None: what = self
    if not self._parent is None:
      self._parent.Changed(what)

  def SendResult(self, *posargs, **kwargs):
    if not self._parent is None:
      self._parent.SendResult(*posargs, **kwargs)
    else: print "SimObject.SendResult() dropping on the floor"

def isTraversable(c): return c.isTraversable()
def manhattanDistance(a,b): return a.manhattanDistance(b)
def heapiter(aHeap):
  "Iterate a heapq (by destructively iterating a copy)."
  h = aHeap[:]
  while h:
    yield heapq.heappop(h)
