import random, heapq
import sim_object
import vexor5

DEBUG = False
NEIGHBORS = vexor5.NEIGHBORS_4D

class HexArrayModel(sim_object.SimObject, dict):  # like a QAbstractItemModel
  def __init__(self, *posargs, **kwargs):
    super(HexArrayModel, self).__init__(*posargs, **kwargs)
    # map from (set of traversable dest Vexor) to 
    # (list of sets of cells of distance r)
    self._pathsCache = {}  
    self._trackRegions = False

    # high-water count of allocated regions
    self._allocRegionNum = 0          

    # unallocated region numbers lower than _allocRegionNum
    self._deallocatedRegions = set()  

    # map from region number to a point in the region
    #self._regionPt = { }              

    # map from region number to count of cells
    self._regionSizeDict = {None:0}   

    # ideally this would be tracked whenever setting a cell
    self._boundsVertical = (None,None)  

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
