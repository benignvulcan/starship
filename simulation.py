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
import hexmap
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
    self._cells = hexmap.HexArrayModel(parent=self)
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
    RING_RADIUS = 3**2
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
