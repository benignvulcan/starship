#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math, random, heapq, unittest
#from PyQt4 import QtCore #, QtGui, uic
#from PyQt4.QtCore import QPointF, QRectF
#from PyQt4.QtGui  import QBrush, QColor, QPen, QPolygonF

from vexor import *
import scheduler

DEBUG = True

def sign(n): return cmp(n,0)

CELL_BREADTH = 1  # meter
CELL_APOTHEM = CELL_BREADTH / 2.0

#===============================================================================

class Action(object):
  def __init__(self):
    super(Action,self).__init__()
  def Preempts(self, other): return True
class Walk(Action):
  def __init__(self, degrees):
    super(Walk,self).__init__()
    self.degrees = degrees
class GoTo(Action):
  def __init__(self, there):
    super(GoTo,self).__init__()
    self.there = there

class Job(object):
  def __init__(self, target=None, obj=None, duration=10, timestamp=None):
    super(Job,self).__init__()
    self.target = target
    self.obj = obj
    self.amountToDo = duration
    self.timestamp = timestamp
    self.claimants = []
  def __repr__(self):
   return "<Job target=%s, todo=%s>" % (self.target, self.amountToDo)
  def isSimilar(self, other):
    return type(self) == type(other) and self.target == other.target and self.obj == other.obj
  def Start(self, claimant):
    pass
  def isDone(self): return self.amountToDo <= 0
  def Work(self, claimant):
    self.amountToDo -= 1
  def Finish(self, claimant):
    pass
class Construct(Job):
  def Finish(self, claimant):
    # target is a cell
    self.target.Discard(DECK)
    self.target.Discard(BULKHEAD)
    if self in self.target._futureLook:
      self.target._futureLook.remove(self)  # sometimes fails
    self.target.Add(self.obj)
    self.target.Changed()
    super(Construct,self).Finish(claimant)
class Unconstruct(Job):
  def Finish(self, claimant):
    self.target.Discard(DECK)
    self.target.Discard(BULKHEAD)
    if self in self.target._futureLook:
      self.target._futureLook.remove(self)
    self.target.Changed()
    super(Unconstruct,self).Finish(claimant)

#===============================================================================

class SimObject(object):
  def __init__(self, parent=None):
    super(SimObject,self).__init__()
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

class HexArrayModel(SimObject, dict):  # like a QAbstractItemModel
  def __init__(self, *posargs, **kwargs):
    super(HexArrayModel, self).__init__(*posargs, **kwargs)
    self._pathsCache = {}  # map from (set of traversable dest Vexor) to (list of sets of cells of distance r)
    self._trackRegions = False
    self._allocRegionNum = 0          # high-water count of allocated regions
    self._deallocatedRegions = set()  # unallocated region numbers lower than _allocRegionNum
    #self._regionPt = { }              # map from region number to a point in the region
    self._regionSizeDict = {None:0}   # map from region number to count of cells
#  def __len__(self): return 
#  def __getitem__(self, key):
#    return self._cells.get[key]
#  def __setitem__(self, key, value):
#    self._cells[key] = value
  def TileMap(self):
    return self
  def ExistingNeighborPositionsOf(self, pos):
    "Return list of all existing adjacent points"
    return [pos+n for n in NEIGHBORS if pos+n in self]
  def ExistingNeighbors(self, pos):
    "Return list of all existing cells adjacent to pos"
    return [self[p] for p in self.ExistingNeighborPositionsOf(pos)]
  def _RenumberRegionsFrom(self, pos, fromRegions=None, toRegion=None):
    # This may be called as part of a merge or a split.
    # Perform a simple flood-fill find-and-replace.
    # Caller is expected to do any needed region deallocations.
    if fromRegions is None:
      fromRegions = frozenset([self[pos]._region])
    if toRegion is None:
      toRegion = self._AllocRegion()
    if DEBUG: print "renumbering regions %s -> %s @ %s" % (fromRegions, toRegion, pos)
    visited = set()
    unvisited = set([pos])
    while unvisited:
      pos = unvisited.pop()
      for n in NEIGHBORS:
        pn = pos + n
        if not pn in visited and pn in self and self[pn]._region in fromRegions:
          unvisited.add(pn)
      r = self[pos]._region
      if r != toRegion:
        self._regionSizeDict[r] -= 1
        self._regionSizeDict[toRegion] += 1
        self[pos]._region = toRegion
      visited.add(pos)
  def _MergeRegionsFrom(self, pos, targetRegions):
    #replacementRgn = min(targetRegions)
    replacementRgn = max( (self._regionSizeDict[r],r) for r in targetRegions )[1]
    if DEBUG: print "merging regions %s -> %s @ %s" % (targetRegions, replacementRgn, pos)
    self._RenumberRegionsFrom(pos, targetRegions, replacementRgn)
    self._DeallocateRegions(targetRegions - frozenset([replacementRgn]))
  def _DeallocateRegions(self, obsoleteRegions):
    if DEBUG: print "deallocating regions", obsoleteRegions
    for r in obsoleteRegions:
      del self._regionSizeDict[r]
      #del self._regionPt[r]
    self._deallocatedRegions.update(obsoleteRegions)
    self._GarbageCollectDeallocatedRegions()
    #if DEBUG: print "  done"
  def _GarbageCollectDeallocatedRegions(self):
    # We could just allocate regions monotonically forever,
    # but perhaps someday the number would roll over.
    for g in reversed(sorted(self._deallocatedRegions)):
      if g+1 == self._allocRegionNum:
        self._allocRegionNum -= 1
        self._deallocatedRegions.remove(g)
  def _AllocRegion(self):
    if self._deallocatedRegions:
      r = self._deallocatedRegions.pop()
    else:
      r = self._allocRegionNum
      self._allocRegionNum += 1
    self._regionSizeDict[r] = 0
    if DEBUG: print "allocating region", r
    return r
  def UpdateCellRegion(self, pos):
    "Cell at [pos] has (possibly) changed its traversability; update it's region."
    # Track both regions of traversability and regions of non-traversability.
    # Assumes there are only 2 kinds of regions (traversable and non-traversable).
    # Assumes all other cells are currently correctly marked.
    if not self._trackRegions: return
    if DEBUG: print "UpdateCellRegion(%s), existing region = %s" % (pos, self[pos]._region)
    oldRegion = self[pos]._region
    self._regionSizeDict[oldRegion] -= 1
    self[pos]._region = None          # Forget current region marking, if any
    verse = self[pos].isTraversable()
    similarRegions = set()
    for n in NEIGHBORS:
      if pos+n in self and self[pos+n].isTraversable() == verse:
        # Found a neighbor with same traversability
        similarRegions.add(self[pos+n]._region)   # Remember its region
        if self[pos]._region is None:
          # Take on its region, extending it.
          self[pos]._region = self[pos+n]._region
          self._regionSizeDict[self[pos+n]._region] += 1
    if self[pos]._region is None:
      # No similarly traversable neighbors were found,
      # so this must be an isolated cell,
      # so create a new region,
      self[pos]._region = self._AllocRegion()
      self._regionSizeDict[self[pos]._region] += 1
      # and logically this could not have caused any merging or splitting,
      # so be done.
      return
    if len(similarRegions) > 1:  # Found multiple similar adjacent regions?
      self._MergeRegionsFrom(pos, similarRegions)
    #del verse
    del similarRegions
    # This also may have caused a region to split:
    #   Check that regions that should be connected still are.
    #   This is cheap to verify, and expensive only in proportion to the
    #   infrequent cases where regions are or are almost split.
    visited_regions = set()
    for i in range(len(NEIGHBORS)):  # check connectivity of each neighbor
      p1 = pos + NEIGHBORS[i]
      if not p1 in self:
        continue
      r1 = self[p1]._region
      if r1 in visited_regions:
        continue
      # Found an unvisited adjacent region.
      # Check connectivity with any other neighbors marked with the same region.
      verse = self[p1].isTraversable()
      for j in range(i+1, len(NEIGHBORS)):  # iterate remaining neighbors
        p2 = pos + NEIGHBORS[j]
        if not p2 in self:
          continue
        r2 = self[p2]._region
        if r2 != r1:
          continue   # only check connectivity for cells marked with same region as cell i
        path = self.PathFromTo(p1, p2, isPathable=lambda c: c.isTraversable()==verse)
        if not path or self[path[-1]].isTraversable()!=verse:
          # p1 and p2 are no longer connected.  Re-number p2/r2.
          # Sadly, this will re-iterate all of the cells just iterated by PathFromTo()
          if self._regionSizeDict[r1] < self._regionSizeDict[r2]:
            self._RenumberRegionsFrom(p1, frozenset([r1]))  # allocates a new region
            r1 = self[p1]._region
          else:
            self._RenumberRegionsFrom(p2, frozenset([r2]))  # allocates a new region
          visited_regions.add(self[p2]._region)  # new region has been seen.
          #self._regionPt[self[p2]._region] = p2
      visited_regions.add(r1)
  def ComputeRegions(self):
    "(Re)assign region numbers to all cells.  Much faster when doing lots of updates."
    self._allocRegionNum = 0
    assigned = set()
    unassigned = set(self.keys())
    while unassigned:
      p1 = unassigned.pop()
      #print "p1 =", p1
      if self[p1]._region is None:
        verse = self[p1].isTraversable()
        visited = set()
        unvisited = set([p1])
        while unvisited:
          p2 = unvisited.pop()
          #print "p2 =", p2
          if self[p2].isTraversable() == verse:
            self[p2]._region = self._allocRegionNum
            self._regionSizeDict[self._allocRegionNum] = self._regionSizeDict.get(self._allocRegionNum, 0) + 1
            unassigned.discard(p2)
            assigned.add(p2)
            unvisited.update(p2+n for n in NEIGHBORS if not (p2+n) in visited and (p2+n) in self)
          visited.add(p2)
        self._allocRegionNum += 1
      assigned.add(p1)
  def FlushPathsCache(self):
    if DEBUG and self._pathsCache: print "flushing path cache"
    self._pathsCache = {}
  def PathsFromTo(self, here, there, isPathable=isTraversable):
    "Given a destination cell position (or set of them), return a set of adjacent closer positions, or None."
    assert isinstance(here, Vexor)
    if isinstance(there, Vexor):
      there = frozenset([there])
    if (not there) or (here in there): return None   # can't get any closer!
    tilemap = self.TileMap()
    #there = frozenset([p for p in there if isPathable(tilemap[p])])
    #if not there: return None # can't actually get there
    distances = self._pathsCache.setdefault(there, [there])
    seen = set(there)
    hits = 0
    r = 0
    while not here in seen:
      if r + 1 < len(distances):
        farther = distances[r+1]
        seen.update(farther)
        hits += len(farther)
      else:
        farther = set()
        for p in distances[r]:
          for n in NEIGHBORS:
            pn = p+n
            if not pn in seen and pn in tilemap and isPathable(tilemap[pn]):
              farther.add(pn)
            seen.add(pn)
        distances.append(farther)
      if not farther:
        if DEBUG: print "path cache hit, %d tiles, no route" % hits
        return None  # no progress, give up, no paths found
      r += 1
    if DEBUG: print "path cache hit, %d tiles" % hits
    return [here + n for n in NEIGHBORS if here + n in distances[r-1]]     # return set of closer positions
  def PathFromTo(self, here, there, isPathable = isTraversable
                                  , cost_heuristic = manhattanDistance
                                  , randomize = True):
    '''Given one or more destination cell positions, return a shortest path.
    Returns a list of positions starting with an adjacent cell and ending with a destination cell.
    If already at the destination, return an empty list.
    If there is no way to get there, return None.
    isPathable() should be a boolean function.
    The destination is allowed to be non-pathable, as standing next to a
      destination is often desirable or sufficient.
    '''
    # See http://en.wikipedia.org/wiki/A*_search_algorithm
    assert isinstance(here, Vexor)
    if isinstance(there, Vexor):
      there = frozenset([there])
    if not there: return None
    if here in there: return []   # can't get any closer!
    if randomize:
      # randomly prioritize equidistant choices
      rrng = 2**30
    else:
      rrng = 1
    # Search backwards, from There to Here, beacuse many There's can exist, but only one Here.
    # Note that if There is not adjacent to any cell in the same region as Here,
    # this will quickly rule out any possibility of a path.
    visited = set()
    came_from = {}
    gscore = {}                           # map of nodes to cost-from-There
    fscore = {}                           # map of nodes to estimated-cost-from-There-to-Here
    for t in there:
      gscore[t] = 0
      fscore[t] = gscore[t] + cost_heuristic(t, here)
    tovisit = [(fscore[t],random.randrange(rrng),t) for t in there]    # heapq of (fscore, node)
    heapq.heapify(tovisit)
    while tovisit:
      current = tovisit[0][-1]
      if current == here:
        # found a shortest route (there could be other equally short routes)
        path = []
        while current in came_from:
          current = came_from[current]
          path.append(current)
        return path
      heapq.heappop(tovisit)
      visited.add(current)
      for pn in (current + n for n in NEIGHBORS):
        if not pn in self or self[pn]._region != self[here]._region or not isPathable(self[pn]):
          continue  # do not route through this node
        g = gscore[current] + 1  # 1 = known distance between neighbors
        if pn in visited and g >= gscore[pn]:
          continue  # this route is no shorter, and pn has already been examined.
        pn_not_tovisit = all( pn != node for _, _, node in tovisit )
        if pn_not_tovisit or g < gscore[pn]:
         # found a new node or shorter route to a visited node
         came_from[pn] = current
         gscore[pn] = g
         fscore[pn] = g + cost_heuristic(pn, here)
         if pn_not_tovisit:
           # visit this node again in the future
           # (even if already visited, because now we know a shorter route)
           heapq.heappush(tovisit, (fscore[pn], random.randrange(rrng), pn) )
    return None

class EnumerateConstants(object):
  def __init__(self, names):
    for number, name in enumerate(names.split()):
      setattr(self, name, number)

Textures = EnumerateConstants("VOID DECK BULKHEAD")

class Deck(SimObject):
  def RegisterComponent(self, components):
    #components.Discard(BULKHEAD)
    components.support = self
    components.ChangedTopology(self)
DECK = Deck()  # Deck singleton
class Bulkhead(SimObject):
  def RegisterComponent(self, components):
    #components.Discard(DECK)
    components.structure = self
    components.obstructions.add(self)
    components.ChangedTopology(self)
BULKHEAD = Bulkhead() # Bulkhead singleton

class Cell(SimObject):
  class Components(object):
    def __init__(self, parent):
      self.parent = parent
      self.composition = None   # vaccum, gas(oxygen, nitrogen), liquid(water,salt), sand, concrete, steel
      self.structure = None     # structural (binding) component of cell, if any
      self.support = None       # support (prevents objects from falling through) component of cell, if any
      self.obstructions = set() # objects that prevent traversal
      self.plumbing = None      # connective transports of liquid, gas, plasma, energy, data
      self.fluid = None         # fluid content of cell, if any
    def __eq__(self, other):
      return self.structure==other.structure and self.support==other.support and self.obstructions==other.obstructions
    def Discard(self, obj):
      changed = False
      if self.structure == obj:
        self.structure = None
        changed = True
      if self.support   == obj:
        self.support   = None
        changed = True
      if obj in self.obstructions:
        self.obstructions.discard(obj)
        changed = True
      if changed:
        self.ChangedTopology()
    def ChangedTopology(self, what=None):
      self.parent.ChangedTopology()
  def __init__(self, parent, pos):
    super(Cell,self).__init__(parent=parent)
    self._pos = pos             # (coordinate) position of this cell within parent
    self._objects = set()       # things and characters
    self._components = Cell.Components(self)  # specific _objects that fulfill various component roles
    self._futureLook = []       # stuff to be built/installed/uninstalled ?
    self._region = None
  def Pos(self): return self._pos
  def ExistingNeighbors(self):
    return self.TileMap().ExistingNeighbors(self._pos)
  def __repr__(self): return "Cell@"+repr(self._pos)
  def Add(self, obj):
    if not obj in self._objects:
      self._objects.add(obj)
      obj.RegisterComponent(self._components)  # calls ChangedTopology as appropriate
      self.Changed()
  def Remove(self, obj):
    self._objects.remove(obj)
    self._components.Discard(obj)  # calls ChangedTopology as appropriate
    self.Changed()
  def Discard(self, obj):
    if obj in self._objects:
      self.Remove(obj)
      self.Changed()
  def ChangedTopology(self, what=None):
    self.ChangedPathing(what)
  def ChangedPathing(self, what=None):
    self.TileMap().FlushPathsCache()
    self.TileMap().UpdateCellRegion(self._pos)
    self.Changed(self)
  def Changed(self, what=None):
    self._parent.Changed(self)
  def isTraversable(self):
    return len(self._components.obstructions)==0 and not self._components.support is None
  def GetBgTexture(self):
    if self._components.structure is None and self._components.support is None:
      return Textures.VOID
    elif not self._components.structure is None:
      return Textures.BULKHEAD
    elif not self._components.support is None:
      return Textures.DECK
    else:
      return None
  textures2hsv = \
    { Textures.VOID      : (  0,   0,   0)
    , Textures.BULKHEAD  : (240,  15,  63)
    , Textures.DECK      : (200,  15, 191)
    }
  def GetBgColor(self):
    tx = self.GetBgTexture()
    h,s,v = self.textures2hsv[tx]
    if tx in (Textures.BULKHEAD, Textures.DECK):
      #h,s,v = (h, s, v + (id(self)%3)*16 )
      tupity = texture1(self._pos)
      h,s,v = (h, s, v + tupity*16 )
    return (h,s,v)
  def isTargeted(self):
    return len(self._futureLook) > 0
  def containsInstanceOf(self, klass):
    for o in self._objects:
      if isinstance(o, klass): return True
    return False

class Character(SimObject):
  def Cell(self): return self._parent
  def MoveTo(self, dest):
    c = self._parent
    self.SetParent(dest)
    c.Changed()
    dest.Changed()
    self.Changed()

class NPC(Character):
  def __init__(self, parent=None):
    super(NPC,self).__init__(parent=parent)
    self._cycleProcess = self.Scheduler().CreateProcess(self.Cycle)
    self.Scheduler().PostEvent(self._cycleProcess, dt=1/random.uniform(1,4), recurring=True)
    self._lastDirection = NEIGHBORS[0]
    self._job = None
    self._path = []
  def Cycle(self, _unusedInput):
    #if self._job is None and random.choice([True,False]):
    #  self.LookForJob()
    if self._job:
      self.JobWalk()
    else:
      self.DrunkWalk()
  def isIdle(self):
    return self._job is None
  def LookForJob(self):
    if not self._job is None:
      return
    jobs = self.Simulation().GetUnclaimedJobs()
    myRegion = self.Cell()._region
    jobs = [j for j in jobs if myRegion in [c._region for c in j.target.ExistingNeighbors()]]
    here = self._parent.Pos()
    # Assuming job.target is a cell...
    jobs.sort(key=lambda j: here.manhattanDistance(j.target.Pos()))
    for j in jobs:
      p = self.PathTo(j.target.Pos())
      if p:
        self._path = p
        self.TakeJob(j, p)
        break
    if jobs and not self._job: print "no pathable jobs"
  def TakeJob(self, j, initialPath=None):
    if not self._job is None:
      self.AbandonJob()
    self._job = j
    self._path = initialPath
    self.Simulation().ClaimJob(self, j)
    j.Start(self)
    self.Changed()
  def AbandonJob(self):
    self._path = None
    self.Simulation().UnclaimJob(self, self._job)
    self._job = None
    self.Changed()
  def FinishJob(self):
    self._job.Finish(self)
    self.Simulation().FinishJob(self._job)
    self._job = None  # done
    self.Changed()
  def JobWalk(self):
    if self._path is None:
      self._path = self.PathTo(self._job.target.Pos())
    if self._path is None or self._path == []:
      self.AbandonJob()
      return # can't get there
    if not self._job.target.Pos() == self._path[0]:
      if not self.TileMap()[self._path[0]].isTraversable():
        self._path = None
        return  # try again in a moment
      self.MoveTo(self.TileMap()[self._path[0]])
      self._path.pop(0)
      return # not there yet
    if not self._job.isDone():
      self._job.Work(self)
      return # not done yet
    if self._job.target.containsInstanceOf(Character):
      print "occupado!"
      if random.randrange(10) == 0:
        print "  giving up occupied job"
        self.AbandonJob()
      return
    self.FinishJob()
  def DrunkWalk(self):
    #print "NPC.DrunkWalk()"
    c = self._parent
    tilemap = self.TileMap()
    newpos = c.Pos()+self._lastDirection
    if (  random.choice([False]+[True]*7)
      and newpos in tilemap
      and tilemap[newpos].isTraversable()
      #and len(tilemap[newpos]._objects)==0
      ):
      traversable_directions = [newpos]
    else:
      neighbor_points = [c.Pos()+n for n in NEIGHBORS]
      traversable_directions = [p for p in neighbor_points
                                  if p in tilemap and tilemap[p].isTraversable()
                                    ]#and len(tilemap[p]._objects)==0]
    if traversable_directions:
      newpos = random.choice(traversable_directions)
      self._lastDirection = newpos - c.Pos()
      dest = tilemap[newpos]
      self.MoveTo(dest)
  def GetColor(self):
    if self._job:
      return (0, 255, 223-(id(self)%3)*48)
    else:
      return (240, 255, 223-(id(self)%3)*48)

class Player(Character):
  def __init__(self, parent=None):
    super(Player,self).__init__(parent=parent)
    self._lastSextant = 0               # direction last walked
    self._cmdProcess = self.Scheduler().CreateProcess(self.ProcessInputEvent)
    self._goalProcess = self.Scheduler().CreateProcess(self.ProcessGoalEvent)
    self._userCmdQueue = []             # queue of commands received not yet examined
    self._userCmdReadyTimeAbs = None    # Busy until this abs time
    self._userCmdReadyTimeDelta = None  # Next delay should be this long
    self._goalCmd = None                # Current activity
  def GetCmdProcess(self):
    return self._cmdProcess
  def PostInput(self, cmd):
    self._cmdProcess.PostInput(cmd)     # This will wind its way to ProcessInputEvent soon
  def HasGoal(self):
    return not self._goalCmd is None or self._userCmdQueue
  def DurationUntilNextCmd(self):
    if self._userCmdReadyTimeAbs is None:
      return 0
    dt = self._userCmdReadyTimeAbs - self.Scheduler().Now()
    if dt < 0:
      dt = 0
    return dt
  def ProcessInputEvent(self, cmd):
    # This function will receive external input events (Walk, GoTo)
    print "Player.ProcessInputEvent(%s)" % cmd
    # First, deal with this input by queueing it, possibly preempting earlier input.
    i = 0
    while i < len(self._userCmdQueue):
      if cmd.Preempts(self._userCmdQueue[i]):
        del self._userCmdQueue[i]
      else:
        i += 1
    self._userCmdQueue.append(cmd)
    self.ProcessGoalEvent(None)
  def ProcessGoalEvent(self, _):
    # This function receives internal move-along-slowly events.
    # Do something if enough time has elapsed and there's something to do.
    while self._userCmdReadyTimeAbs <= self.Scheduler().Now() and self.HasGoal():
      self.PerformOneCommand()
  def PerformOneCommand(self):
    # Unconditionally do something now.
    # Sets _goalCmd and if activity needs to spend time, then
    #   resets _userCmdReadyTimeAbs and posts a future event.
    print "PeformOneCommand, _goalCmd = %s, _userCmdQueue = %s" % (self._goalCmd, self._userCmdQueue)
    self._userCmdReadyTimeDelta = .5  # Commands consume this much simTime by default
    if self._goalCmd is None:
      self._goalCmd = self._userCmdQueue.pop(0)
    # Methods should set _userCmdReadyTimeDelta if they want a different busy time.
    # Methods should set _goalCmd to None when the goal is to be discarded.
    if isinstance(self._goalCmd, Walk):
      self.Walk()
    elif isinstance(self._goalCmd, GoTo):
      self.GoTo()
    else:
      print "  User Cmd ignored:", self._goalCmd
      self._goalCmd = None
    if self._userCmdReadyTimeDelta:
      now = self.Scheduler().Now()
      print "now = %s, _usrCmdReadyTimeAbs = %s, _userCmdReadyTimeDelta = %s, HasGoal = %s" % (
        now, self._userCmdReadyTimeAbs, self._userCmdReadyTimeDelta, self.HasGoal() )
      self._userCmdReadyTimeAbs = now + self._userCmdReadyTimeDelta
      #if self.HasGoal():
      self._goalProcess.PostEvent(dt=self._userCmdReadyTimeDelta, priority=0)
  def GoTo(self):
    path = self.PathTo(self._goalCmd.there)
    if path and self.TileMap()[path[0]].isTraversable():
      newpos = path[0]
      dest = self.TileMap()[newpos]
      self.MoveTo(dest)
      self._userCmdReadyTimeDelta = .5
      self.Simulation().CenterOn(self._parent)
      if len(path) > 1 and self.TileMap()[path[1]].isTraversable():
        return
    self._goalCmd = None
  def Walk(self):
    degrees = self._goalCmd.degrees % 360
    print "Player.Walk(%s)," % degrees,
    self._goalCmd = None
    if degrees % 60 == 0:
      # Trying to walk exactly wrong.
      # Deflect path toward the same side the cell was entered from (zig-zag).
      # 150 then 180 should produce 210; 210 then 180 should produce 150
      # 30 then 0 should produce -30; -30 then 0 should produce 30
      delta = degrees - (self._lastSextant * 60 + 30)  # 0..359 - 0..359 -> -359..359; I want -180..180
      delta_ = (delta+180) % 360 - 180
      deflection = 30 * sign(delta_)
      print "lastSextant = %s, deflection = %s," % (self._lastSextant, deflection),
      sextant = int((degrees+deflection)%360/60.0)
    else:
      sextant = int(degrees/60.0)
    print "sextant =", sextant
    assert sextant >= 0 and sextant < 6
    c = self._parent
    newpos = c.Pos() + NEIGHBORS[sextant]
    if newpos in self.TileMap() and self.TileMap()[newpos].isTraversable():
      print "player newpos =", newpos
      self._userCmdReadyTimeDelta = .5
      dest = self.TileMap()[newpos]
      self.MoveTo(dest)
      self._lastSextant = sextant
    #self.SendResult("CenterOn", self._parent)
    self.Simulation().CenterOn(self._parent)
  def GetColor(self): return (50,255,191)

class JobDispatcher(object):

  def __init__(self, aSimulation):
    super(JobDispatcher,self).__init__()
    self._simulation = aSimulation
    self._jobs = []
    self._workers = set()
    self._idleWorkers = set()
    self._process = self._simulation.Scheduler().CreateProcess(self.AssignJobs)
    self._simulation.Scheduler().PostEvent(self._process, dt=1, recurring=True)
  def AddWorker(self, anNPC):
    self._workers.add(anNPC)
    self._idleWorkers.add(anNPC)
  def PostJobs(self, jobs):
    for j in jobs:
      self.PostJob(j)
  def PostJob(self, j):
    assert j.claimants == []
    if any(j.isSimilar(b) for b in self._jobs):
      print "discarding duplicate job posting"
      return
    self._jobs.append(j)
    # Assuming target is a cell...
    j.target._futureLook.append(j)
    j.target.Changed()
  def ClaimJob(self, claimant, j):
    print "ClaimJob", j
    assert j in self._jobs
    j.claimants.append(claimant)
  def UnclaimJob(self, claimant, j):
    print "UnclaimJob", j
    assert j in self._jobs
    j.claimants.remove(claimant)
  def GetUnclaimedJobs(self):
    return [j for j in self._jobs if len(j.claimants)==0]
  def FinishJob(self, j):
    print "FinishJob", j
    if j in self._jobs:
      self._jobs.remove(j)
    else:
      print "  job %s not found" % j
  def JobCount(self):
    return len(self._jobs)
  def AssignJobs(self, _):
    candidates = [w for w in self._idleWorkers if w.isIdle()]
    if not candidates:
      return
    for j in self._jobs:
      if len(j.claimants)>0:
        continue
      h = []
      #candidates.sort(key=lambda w: w.Parent().Pos().manhattanDistance(j.target.Pos()))
      #nearest = min(candidates, key=lambda w: w.Parent().Pos().manhattanDistance(j.target.Pos()))
      for w in candidates:
        dist = w.Parent().Pos().manhattanDistance(j.target.Pos())
        if dist < 100:
          heapq.heappush(h, (dist, w))
      while h:
        nearest = h[0][1]
        p = nearest.PathTo(j.target.Pos())
        if p:
          nearest.TakeJob(j, p)
          candidates.remove(nearest)
          if not candidates:
            return
          break
        else:
          heapq.heappop(h)

class Simulation(SimObject):

  def __init__(self, qparent):
    super(Simulation,self).__init__()
    self._qparent = qparent
    self._cells = HexArrayModel(parent=self)
    self._changedCells = set()
    self._centerOn = None
    self._scheduler = scheduler.Scheduler()
    self._dispatcher = JobDispatcher(self)

    self.CreateWorld()
    count = len(self._cells)
    print count,"cells created"

    startVexors = [k for k in self._cells.keys() if self._cells[k].isTraversable()]
    startVexors.sort(key=lambda k: k.manhattanLength())

    #startCell = self._cells[Vexor(0,0,0)]
    #startCell = self._cells[random.choice(startVexors)]
    startCell = self._cells[startVexors[0]]
    self._player = Player(parent=startCell)
    startCell.Add(self._player)

    for i in range(len(startVexors) / 20):
      startCell = self._cells[random.choice(startVexors)]
      npc = NPC(parent=startCell)
      startCell.Add(npc)
      self._dispatcher.AddWorker(npc)

    self._cells._trackRegions = True
    self._cells.ComputeRegions()

  def Now(self):
    return self._scheduler.Now()

  def PostJob(self, j):
    self._dispatcher.PostJob(j)
  def PostJobs(self, jobs):
    self._dispatcher.PostJobs(jobs)
  def ClaimJob(self, claimant, j):
    self._dispatcher.ClaimJob(claimant, j)
  def UnclaimJob(self, claimant, j):
    self._dispatcher.UnclaimJob(claimant, j)
  def GetUnclaimedJobs(self):
    return self._dispatcher.GetUnclaimedJobs()
  def FinishJob(self, j):
    self._dispatcher.FinishJob(j)
  def JobCount(self):
    return self._dispatcher.JobCount()

  def CreateWorld(self):
    HUB_RADIUS = 3**2
    RING_RADIUS = 3**3
    RING2_RADIUS = RING_RADIUS * 2
    # Create cells
    for v in sectorRange(RING2_RADIUS+HUB_RADIUS+1):
      self._cells[v] = Cell(self._cells, v)
      self._cells.UpdateCellRegion(v)
    # Create spokes
    for sextant in range(6):
      for r in range(HUB_RADIUS-2,RING2_RADIUS-2):
        v = NEIGHBORS[sextant]*r
        for w in range(-2,3):
          v = NEIGHBORS[sextant]*r + NEIGHBORS[(sextant+2)%6]*w
          self._cells[v].Add(DECK)
    # Create ring(s)
    for r in range(-2, 3): # for thickness of ring
      for v in sectorRange(RING_RADIUS+r,RING_RADIUS+r+1):
          self._cells[v].Add(DECK)
      for v in sectorRange(RING2_RADIUS+r,RING2_RADIUS+r+1):
          self._cells[v].Add(DECK)
    # Create hubs
    for n in (Vexor(0,0,0),)+NEIGHBORS:
      hub = n*RING_RADIUS
      for v in sectorRange(HUB_RADIUS):
        self._cells[hub+v].Add(DECK)
      hub = n*RING2_RADIUS
      for v in sectorRange(HUB_RADIUS):
        self._cells[hub+v].Add(DECK)
    # Find edges
    edges = set()
    for v in self._cells.keys():
      if self._cells[v]._components.support is None:      # is there a DECK here?
        continue                                          # no, skip it
      for v2 in self._cells.ExistingNeighborPositionsOf(v):
        if self._cells[v2]._components.support is None:   # is there a DECK adjacent?
          edges.add(v)                                    # no, so v is an edge.
          break
    # And in a separate pass, add bulkheads to edges
    for v in edges:
      self._cells[v].Remove(DECK)
      self._cells[v].Add(BULKHEAD)
    # Create random obstructing walls in interior
    k_traversable = [k for k in self._cells.keys() if self._cells[k].isTraversable()]
    print "%d traversable interior" % len(k_traversable)
    for i in range(len(k_traversable)/3):
      v = random.choice(k_traversable)
      #print "adding BULKHEAD at %s" % (v,)
      self._cells[v].Remove(DECK)
      self._cells[v].Add(BULKHEAD)
      k_traversable.remove(v)

  def Simulation(self): return self
  def Scheduler(self): return self._scheduler
  def Player(self): return self._player

  def Changed(self, what):
    self._changedCells.add(what)
  def PopChanges(self):
    changeSet = self._changedCells
    self._changedCells = set()
    return changeSet
  def CenterOn(self, target):
    self._centerOn = target

  def SendResult(self, *posargs, **kwargs):
    self._qparent.ReceiveResult(*posargs, **kwargs)

if __name__=='__main__': unittest.main()
