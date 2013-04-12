#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math, random, heapq, unittest, pprint
#from PyQt4 import QtCore #, QtGui, uic
#from PyQt4.QtCore import QPointF, QRectF
#from PyQt4.QtGui  import QBrush, QColor, QPen, QPolygonF

#from vexor5 import *
#from vexor5 import NEIGHBORS_4D, sectorRange, DOWN, ZERO, UP,NEIGHBORS_2D, Vexor
import vexor5
import scheduler
import action
import sim_object
#from action import Walk
#from job import Job
#from sim_object import SimObject, isTraversable, manhattanDistance, heapiter

DEBUG = False
def sign(n): return cmp(n, 0)

CELL_BREADTH = 1  # meter
CELL_APOTHEM = CELL_BREADTH / 2.0

NEIGHBORS = vexor5.NEIGHBORS_4D

#===============================================================================

#===============================================================================


class HexArrayModel(sim_object.SimObject, dict):  # like a QAbstractItemModel
  def __init__(self, *posargs, **kwargs):
    super(HexArrayModel, self).__init__(*posargs, **kwargs)
    self._pathsCache = {}  # map from (set of traversable dest Vexor) to (list of sets of cells of distance r)
    self._trackRegions = False
    self._allocRegionNum = 0          # high-water count of allocated regions
    self._deallocatedRegions = set()  # unallocated region numbers lower than _allocRegionNum
    #self._regionPt = { }              # map from region number to a point in the region
    self._regionSizeDict = {None:0}   # map from region number to count of cells
    self._boundsVertical = (None,None)  # ideally this would be tracked whenever setting a cell
#  def __len__(self): return 
#  def __getitem__(self, key):
#    return self._cells.get[key]
#  def __setitem__(self, key, value):
#    self._cells[key] = value
  def TileMap(self):
    return self
  def GetBoundsVertical(self):
    "Return the pair (low,high) encompassing the lowest and highest cell."
    return self._boundsVertical
  def ExistingNeighborPositionsOf(self, pos, neighborVexors=NEIGHBORS):
    "Return list of all existing adjacent points"
    return [pos+n for n in neighborVexors if pos+n in self]
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
      if DEBUG: print "UpdateCellRegion({0}) done: isolated cell".format(pos)
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
    if DEBUG: print "UpdateCellRegion({0}) done".format(pos)
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
  def PathsFromTo(self, here, there, isPathable=sim_object.isTraversable):
    "Given a destination cell position (or set of them), return a set of adjacent closer positions, or None."
    assert isinstance(here, vexor5.Vexor)
    if isinstance(there, vexor5.Vexor):
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
  def PathFromTo(self, here, there, isPathable = sim_object.isTraversable
                                  , cost_heuristic = sim_object.manhattanDistance
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
    assert isinstance(here, vexor5.Vexor)
    if isinstance(there, vexor5.Vexor):
      there = frozenset([there])
    if not there: return None
    if here in there: return []   # can't get any closer!
    # if DEBUG: print "Path From {0} to {1}".format(here, there) 
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
        # if DEBUG: print "found shortest path from {0} to {1}".format(here, there)
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
    if DEBUG: print "no path from {0} to {1}".format(here, there)
    return None

class EnumerateConstants(object):
  def __init__(self, names):
    for number, name in enumerate(names.split()):
      setattr(self, name, number)

Textures = EnumerateConstants("VOID DECK BULKHEAD")
RenderObjects = EnumerateConstants("BG TARGETING PLAYER NPC")

class Deck(sim_object.SimObject):
  def __repr__(self):
    return "DECK"
  def RegisterComponent(self, components):
    #components.Discard(BULKHEAD)
    components.support = self
    components.ChangedTopology(self)
DECK = Deck()  # Deck singleton
class Bulkhead(sim_object.SimObject):
  def __repr__(self):
    return "BULKHEAD"
  def RegisterComponent(self, components):
    #components.Discard(DECK)
    components.structure = self
    components.obstructions.add(self)
    components.ChangedTopology(self)
BULKHEAD = Bulkhead() # Bulkhead singleton

class Cell(sim_object.SimObject):
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
  def __repr__(self):
    return "<Cell pos={0}>".format((self._pos))
  def Pos(self): return self._pos
  def ExistingNeighbors(self):
    return self.TileMap().ExistingNeighbors(self._pos)
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
  def ChangedTopology(self, what=None):
    self.ChangedPathing(what)
  def ChangedPathing(self, what=None):
    self.TileMap().FlushPathsCache()
    self.TileMap().UpdateCellRegion(self._pos)
    self.Changed(self)
  def Changed(self, what=None):
    self._parent.Changed(self)
    up_pos = self._pos+vexor5.UP
    if up_pos in self.TileMap():
      self.TileMap()[up_pos].Changed(self)
  def isSupporter(self):
    return BULKHEAD in self._objects
  def isSupported(self):
    if self._components.support or DECK in self._objects:
      return True
    dn_pos = self._pos+vexor5.DOWN
    return dn_pos in self.TileMap() and self.TileMap()[dn_pos].isSupporter()
  def isTraversable(self):
    return len(self._components.obstructions)==0 and self.isSupported()
  def isAccessible(self):
    for n in self.ExistingNeighbors():
      if n.isTraversable(): return True
    return False
  def GetBgTexture(self):
    if self._components.structure is None and not self.isSupported():
      return Textures.VOID
    elif not self._components.structure is None:
      return Textures.BULKHEAD
    elif self.isSupported():
      return Textures.DECK
    else:
      return None
  def GetRenderSpec(self):
    'Return a list of rendering instructions for this cell.'
    player = None
    npc = None
    for o in self._objects:
      if isinstance(o, NPC):
        npc = o
      elif isinstance(o, Player):
        player = o
    seq = [ (RenderObjects.BG, self.GetBgTexture()) ]
    if self.isTargeted():
      seq.append( (RenderObjects.TARGETING, None) )
    if player:
      seq.append( (RenderObjects.PLAYER, player.GetColor()) )
    elif npc:
      seq.append( (RenderObjects.NPC, npc.GetColor()) )
    return seq
  def isTargeted(self):
    return len(self._futureLook) > 0
  def containsInstanceOf(self, klass):
    for o in self._objects:
      if isinstance(o, klass): return True
    return False

class Character(sim_object.SimObject):
  def Region(self): return self.Cell()._region
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
  def __repr__(self):
    return "<NPC: cell={0}, job={1}>".format(self.Cell(), self._job)
  def Cycle(self, _unusedInput):
    if self._job:
      self.JobWalk()
    else:
      self.DrunkWalk()
  def isIdle(self):
    return self._job is None
  def DisinterestInJob(self, j):
    "Return a metric of how disinterested this NPC is in job j"
    if not self.Region() in [n._region for n in j.CellsToWorkFrom()]:
      return 1000
    distanceToOfferedJob = self.MDistanceToJob(j)
    if distanceToOfferedJob == 0:
      return 100 
    if self._job:
      return distanceToOfferedJob * 4
    return distanceToOfferedJob
  def OfferJob(self, j):
    if DEBUG: print "Offering job {0} to NPC {1}".format(j, self)
    if not self.isInterestedInJob(j):
      if DEBUG: print "Not interested in Job {0}".format(j)
      return j
    if DEBUG: print "Taking job {0} in favor of job {1}".format(j,self._job)
    oldJob = self._job
    self.TakeJob(j)
    return oldJob    
      
  def MDistanceToJob(self, j):
    return self.Parent().Pos().manhattanDistance(j.target.Pos())
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
    print "NPC: Finishing Job ", self._job
    assert self in self._job.claimants
    self._job.Finish(self)
    self.Simulation().FinishJob(self._job)
    self._job = None  # done
    self.Changed()
    print "NPC: Finished Job ", self._job
  def JobWalk(self):
    if self._path is None:
      self._path = self.PathTo(self._job.target.Pos())
    if self._path is None or self._path == []:
      print "Abandoning Job {0} because path is {1}".format(self._job, self._path)
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
    if isinstance(self._goalCmd, action.Walk):
      self.Walk()
    elif isinstance(self._goalCmd, action.GoTo):
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
      if DEBUG: print "discarding duplicate job posting"
      return
    self._jobs.append(j)
    # Assuming target is a cell...
    j.target._futureLook.append(j)
    j.target.Changed()
  def ClaimJob(self, claimant, j):
    if DEBUG: print "ClaimJob", j
    assert j in self._jobs
    assert not j.claimants
    j.claimants.append(claimant)
    self._idleWorkers.remove(claimant)
  def UnclaimJob(self, claimant, j):
    if DEBUG: print "UnclaimJob", j, j.claimants, claimant
    assert j in self._jobs
    j.claimants.remove(claimant)
    self._idleWorkers.add(claimant)
    if j.claimants: print "Remaining Claiminants:", j.claimants
  def GetUnclaimedJobs(self):
    return [j for j in self._jobs if len(j.claimants)==0]
  def FinishJob(self, j):
    print "JobDispatcher.FinishJob({0})".format(j)
    for w in j.claimants:
      self._idleWorkers.add(w)
    if j in self._jobs:
      self._jobs.remove(j)
      print "JobDispatcher.FinishJob done"
    else:
      print "*** job {0} not found ***".format(j)
  def JobCount(self):
    return len(self._jobs)
  def IdleWorkerCount(self):
    return len(self._idleWorkers)

  def FindCandidatesForJob(self, j, candidates):
    adjacentRegions = set(n._region for n in j.target.ExistingNeighbors())
    candidatesInRegion = filter(lambda w: w.Parent()._region in adjacentRegions, candidates)
    disinterestCandidatePairs = map(lambda w: (w.DisinterestInJob(j), w), candidatesInRegion)
    disinterestCandidatePairs.sort(reverse=True)
    return disinterestCandidatePairs

  def AssignJobs(self, _):    
    "Match available jobs to available workers"
    print "Assigning jobs"
    #candidates = filter(lambda w: w.isIdle(), self._idleWorkers)
    candidates = self._idleWorkers
    print len(candidates)," Candidate Workers"
    if not candidates:
      return
    accessibleJobs = filter(lambda j: not j.claimants and j.target.isAccessible(), self._jobs)
    print len(accessibleJobs), " ready jobs"
    if not accessibleJobs:
      return

    #if DEBUG: print "Accessible Jobs:", accessibleJobs

    possibleMatches = {}   # map from job to list of (disinterest, worker)
    possibleMatches[None] = None
    engagements = dict((w,(1001,None)) for w in candidates) # map from worker to (disinterest, tentative job)

    for j in accessibleJobs[:30]:
      job = j
      while job:
        #if DEBUG: print "Finding Match for job {0}".format(job)
        if job not in possibleMatches:
          possibleMatches[job] = self.FindCandidatesForJob(job, candidates)
        if not possibleMatches[job]: 
          break
        (disinterest, w) = possibleMatches[job].pop()
        if disinterest < engagements[w][0]:
          (engagements[w], job) = ((disinterest, job), engagements[w][1])

    for w in engagements:
      (disinterest, j) = engagements[w]
      if not j is None:
        if DEBUG: print "Assigning job {0}, interest {1}, to {2}".format(j, disinterest, w)
        w.TakeJob(j)

class Simulation(sim_object.SimObject):

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

    startVexors = [k for k in self._cells.keys() if k.v==0 and self._cells[k].isTraversable()]
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
  def IdleWorkerCount(self):
    return self._dispatcher.IdleWorkerCount()

  def CreateWorld(self):
    HUB_RADIUS = 3**2
    RING_RADIUS = 3**3
    RING2_RADIUS = RING_RADIUS * 2
    # Create cells
    for u in vexor5.sectorRange(RING2_RADIUS+HUB_RADIUS+1):
      for v in (vexor5.DOWN,vexor5.ZERO,vexor5.UP):
        uv = u+v
        self._cells[uv] = Cell(self._cells, uv)
        self._cells.UpdateCellRegion(uv)
    self._cells._boundsVertical = (-1,1)  # 3 layers exist
    # Create spokes
    for sextant in range(6):
      for r in range(HUB_RADIUS-2,RING2_RADIUS-2):
        for w in range(-2,3):
          v = vexor5.NEIGHBORS_2D[sextant]*r + vexor5.NEIGHBORS_2D[(sextant+2)%6]*w + vexor5.DOWN
          #self._cells[v].Add(DECK)
          self._cells[v].Add(BULKHEAD)
    # Create ring(s)
    for r in range(-2, 3): # for thickness of ring
      for v in vexor5.sectorRange(RING_RADIUS+r,RING_RADIUS+r+1):
        self._cells[v+vexor5.DOWN].Add(BULKHEAD)
      for v in vexor5.sectorRange(RING2_RADIUS+r,RING2_RADIUS+r+1):
        self._cells[v+vexor5.DOWN].Add(BULKHEAD)
    # Create hubs
    for v in vexor5.sectorRange(HUB_RADIUS):  # create (bottom) center hub first
      self._cells[vexor5.DOWN+v].Add(BULKHEAD)
    for n in vexor5.NEIGHBORS_2D:
      hub = n*RING_RADIUS + vexor5.DOWN
      for v in vexor5.sectorRange(HUB_RADIUS):
        self._cells[hub+v].Add(BULKHEAD)
      hub = n*RING2_RADIUS + vexor5.DOWN
      for v in vexor5.sectorRange(HUB_RADIUS):
        self._cells[hub+v].Add(BULKHEAD)
    # Find edges
    edges = set()
    for v in self._cells.keys():
      if not self._cells[v].isSupported():                # is there a DECK here?
        continue                                          # no, skip it
      for v2 in self._cells.ExistingNeighborPositionsOf(v, neighborVexors=vexor5.NEIGHBORS_2D):
        if not self._cells[v2].isSupported():             # is there a DECK adjacent?
          edges.add(v)                                    # no, so v is an edge.
          break
    # And in a separate pass, add bulkheads to edges
    for v in edges:
      #self._cells[v].Remove(DECK)
      self._cells[v].Add(BULKHEAD)
    if False:
      # Create random obstructing walls in interior
      k_traversable = [k for k in self._cells.keys() if self._cells[k].isTraversable()]
      print "%d traversable interior" % len(k_traversable)
      for i in range(len(k_traversable)/3):
        v = random.choice(k_traversable)
        #print "adding BULKHEAD at %s" % (v,)
        self._cells[v].Discard(DECK)
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
