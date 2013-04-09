
import sys, math, numbers, collections, unittest

_S = math.sqrt(3.0)/2.0 # + sys.float_info.epsilon does not really help
_EPSILON = 10 ** (2 - sys.float_info.dig)  # experimentally determined number of digits

class Vexor(collections.namedtuple('VexorTuple','x y z v w')):
  # Where:
  #   x+y+z = 0 = 2D hexagonal coordinates
  #   v = vertical = cartesian z
  #   w = forth spatial dimension; +w = "ana", -w = "kata"
  '''
  A "Hex Vector".  Math with hexagonal coordinates, as defined by:

      axis      ____
       +y      /x= 0\ 
         \____/ y= 2 \____
         /x=-1\ z=-2 /x= 1\ 
    ____/ y= 2 \____/ y= 1 \____
   /x=-2\ z=-1 /x= 0\ z=-2 /x= 2\ 
  / y= 2 \____/ y= 1 \____/ y= 0 \ 
  \ z= 0 /x=-1\ z=-1 /x= 1\ z=-2 /
   \____/ y= 1 \____/ y= 0 \____/
   /x=-2\ z= 0 /x= 0\ z=-1 /x= 2\ 
  / y= 1 \____/ y= 0 \____/ y=-1 \__+x axis
  \ z= 1 /x=-1\ z= 0 /x= 1\ z=-1 /
   \____/ y= 0 \____/ y=-1 \____/
   /x=-2\ z= 1 /x= 0\ z= 0 /x= 2\ 
  / y= 0 \____/ y=-1 \____/ y=-2 \ 
  \ z= 2 /x=-1\ z= 1 /x= 1\ z= 0 /
   \____/ y=-1 \____/ y=-2 \____/
        \ z= 2 /x= 0\ z= 1 /
         \____/ y=-2 \____/
         /    \ z= 2 /
       +z      \____/
      axis

  x = distance from the perpendicular through the x axis at 0
  y = distance from the perpendicular through the y axis at 0
  z = distance from the perpendicular through the z axis at 0
  For the most part, this is just like Cartesian vector math.
  Notable invariant: x + y + z == 0

  This class is intended to have value semantics, not identity semantics:
    Instance variables should not change after construction.
      (Indeed, they can't, since this class is a tuple.)
    Operations normally return new instances, but may return one of the input
      objects if its value is the same as the needed result.
  '''
  # Cartesian slope of hex y axis is sqrt(3), perpendicular is -1/sqrt(3) = -sqrt(3)/3
  # As far as I can tell, this is a valid vector space.
  def __repr__(self):
    return "Vexor(%g,%g,%g, %g,%g)" % self
  def isValid(self):
    return abs(self.x + self.y + self.z) < _EPSILON
  def __add__(self, other):
    return Vexor(self.x+other.x, self.y+other.y, self.z+other.z, self.v+other.v, self.w+other.w)
  def __sub__(self, other):
    return Vexor(self.x-other.x, self.y-other.y, self.z-other.z, self.v-other.v, self.w-other.w)
  def __mul__(self, scalar):
    return Vexor(self.x*scalar, self.y*scalar, self.z*scalar, self.v*scalar, self.w*scalar)
  def __rmul__(self, scalar):
    return Vexor(scalar*self.x, scalar*self.y, scalar*self.z, scalar*self.v, scalar*self.w)
  def divFloat(self, scalar):
    scalar = float(scalar)
    return Vexor(self.x/scalar, self.y/scalar, self.z/scalar, self.v/scalar, self.w/scalar)
  def divInt(self, scalar):
    "Divide (using native coercions) and convert result to valid integer coordinates"
    return Vexor(self.x/scalar, self.y/scalar, self.z/scalar, self.v/scalar, self.w/scalar).vexorInt()
  def divmodInt(self, scalar):
    q = Vexor(self.x/scalar, self.y/scalar, self.z/scalar, self.v/scalar, self.w/scalar).vexorInt()
    return (q, self - (q * scalar))
  def vexorInt(self, int=int):
    "Truncate or round to nearest valid coordinate"
    x = int(self.x)
    y = int(self.y)
    z = int(self.z)
    s = x + y + z
    if s:
      dx = abs(x - self.x)
      dy = abs(y - self.y)
      dz = abs(z - self.z)
      if dx >= dy and dx >= dz:
        x -= s  # dx is max
      elif dy >= dx and dy >= dz:
        y -= s  # dy is max
      else:
        z -= s
    return Vexor(x,y,z,int(self.v),int(self.w))
  def __neg__(self):
    return Vexor(-self.x, -self.y, -self.z, -self.v, -self.w)
  def __pos__(self):
    return self
  def toSkewXY(self):
    return (self.x, self.y)
  def toSkewXYVW(self):
    return (self.x, self.y, self.v, self.w)
  def toRectCoords(self):
    "Return conventional x,y,z,w 4-dimensional rectangular coordinates"
    # Sadly, this often returns a float x value that when squared becomes
    #   .7499999999999999 when it should be .75
    # Using round() may help: round(Vexor(1,0,-1).toRectCoords(), 12)
    return (_S*self.x,  (float(self.y) - self.z)/2.0, self.v, self.w)
  def __abs__(self):
    # Assuming absolute value = length = magnitude = Euclidean plane distance.
    # Note that len() will return the number of elements in the tuple.
    # Sadly, this often returns .9999999999999999 when it should return 1.0
    x, y, v, w = self.toRectCoords()
    return math.sqrt(x**2+y**2+v**2+w**2)
  def manhattanLength(self):
    "Distance to the origin, taking only integral steps perpendicular to axes."
    # If Manhattan were laid out on a mixed hexagonal-cartesian plan, that is...
    return max(abs(self.x), abs(self.y), abs(self.z)) + abs(self.v) + abs(self.w)
  def manhattanDistance(self, other):
    return (self - other).manhattanLength()

def toVexor(x,y,z,w):
  return Vexor( x/_S, y - x/_S/2.0, -x/_S/2.0 - y, z, w)

def sectorRange(r=None, rstop=None, rstep=1, sextant_start=0, sextant_stop=6, sextant_step=1, cell_step=1):
  "Generate Vexors by radius and then by sextant."
  # Concatenate these using itertools.chain() (instead of '+')
  if rstop is None:
    rstop = r
    r = 0
  assert r >= 0
  sextant_start %= 6
  while r != rstop:
    if r == 0:
      yield ZERO
    else:
      x = sextant_start
      while x != sextant_stop:
        i = NEIGHBORS_2D[x] * r
        istep = NEIGHBORS_2D[(x+2)%6] * cell_step
        for count in range(r):
          yield i
          i += istep
        x += sextant_step
    r += rstep

_uniform1coloring_map = \
    { (0,0) : 0
    , (1,0) : 1
    , (2,0) : 2
    , (0,1) : 2
    , (1,1) : 0
    , (2,1) : 1
    , (0,2) : 1
    , (1,2) : 2
    , (2,2) : 0
    }

def uniform1coloring(v):
  '"1-uniform" 3-coloring for hexagonal tiling.'
  # See http://en.wikipedia.org/w/index.php?title=Hexagonal_tiling
  x,y = v.toSkewXY()
  return _uniform1coloring_map[(x%3,y%3)]

def uniform2coloring(v):
  '"2-uniform" 4-coloring for hexagonal tiling.'
  x,y = v.toSkewXY()
  return ((x&1)<<1) | (y&1)

ZERO = Vexor(0,0,0, 0,0)

NEIGHBORS_2D = \
  ( Vexor( 1, 0,-1, 0,0)
  , Vexor( 0, 1,-1, 0,0)
  , Vexor(-1, 1, 0, 0,0)
  , Vexor(-1, 0, 1, 0,0)
  , Vexor( 0,-1, 1, 0,0)
  , Vexor( 1,-1, 0, 0,0)
  )

UP   = Vexor(0,0,0, 1, 0)
DOWN = Vexor(0,0,0,-1, 0)
ANA  = Vexor(0,0,0, 0, 1)
KATA = Vexor(0,0,0, 0,-1)

NEIGHBORS_3D = NEIGHBORS_2D + (UP,DOWN)
NEIGHBORS_4D = NEIGHBORS_3D + (ANA,KATA)

SEVEN  = (ZERO,)+NEIGHBORS_2D
NINE   = SEVEN + (UP,DOWN)
ELEVEN = NINE + (ANA, KATA)

_R2_2D = \
  ( Vexor( 2, 0,-2, 0,0)
  , Vexor( 1, 1,-2, 0,0)
  , Vexor( 0, 2,-2, 0,0)
  , Vexor(-1, 2,-1, 0,0)
  , Vexor(-2, 2, 0, 0,0)
  , Vexor(-2, 1, 1, 0,0)
  , Vexor(-2, 0, 2, 0,0)
  , Vexor(-1,-1, 2, 0,0)
  , Vexor( 0,-2, 2, 0,0)
  , Vexor( 1,-2, 1, 0,0)
  , Vexor( 2,-2, 0, 0,0)
  , Vexor( 2,-1,-1, 0,0)
  )

_R2_3D = _R2_2D + tuple(n+UP for n in NEIGHBORS_2D) + tuple(n+DOWN for n in NEIGHBORS_2D) + (UP+UP, DOWN+DOWN)

class TestVexor(unittest.TestCase):
  def testVexor(self):
    for s in range(-3, 4):
      for n in NEIGHBORS_4D:
        h = Vexor(n.x*s, n.y*s, n.z*s, n.v*s, n.w*s)
        r = h.toRectCoords()
        rh = toVexor(*r)
        dh = h.manhattanDistance(rh)
        if False:
          print "%s --> %s --> %s {%g}" % \
          (  h
          ,  "(% 9.4f,% 9.4f)" % r
          ,  rh
          , dh
          )
        self.assertTrue(rh.isValid())
        self.assertEqual(h, h)
        self.assertTrue(dh < _EPSILON)
        if s == 0: break
    self.assertEqual( ZERO.manhattanLength(), 0 )
    for n in NEIGHBORS_4D:
      self.assertEqual( n.manhattanLength(), 1 )
      self.assertEqual( n.manhattanDistance(ZERO), 1 )
    for n in _R2_2D:
      self.assertEqual( n.manhattanLength(), 2 )
      self.assertEqual( n.manhattanDistance(ZERO), 2 )
    for n in SEVEN + _R2_2D:
      if n != ZERO:
        self.assertNotEqual( -n, n )
        self.assertNotEqual( n * 2, n )
      self.assertTrue( n.isValid() )
      self.assertEqual( n, n )
      self.assertEqual( +n, n )
      self.assertEqual( - - n, n )
      self.assertEqual( n + ZERO, n )
      self.assertEqual( ZERO + n, n )
      self.assertEqual( n - ZERO, n )
      self.assertEqual( ZERO - n, -n )
      self.assertEqual( n * 0, ZERO )
      self.assertEqual( 0 * n, ZERO )
      self.assertEqual( 1 * n, n )
      self.assertEqual( n * 1, n )
      self.assertEqual( n.divFloat(1), n )
      for d in (-3,-2,-1,1,2,3):
        #print "{0} divFloat  {1} -> {2}".format(n, d, n.divFloat(d))
        #print "{0} divInt    {1} -> {2}".format(n, d, n.divInt(d))
        #print "{0} divmodInt {1} -> {2}".format(n, d, n.divmodInt(d))
        self.assertTrue(n.divFloat(d).isValid())
        self.assertTrue(n.divInt(d).isValid())
  def testSectorRange(self):
    self.assertEqual( [v for v in sectorRange(0      )], [] )
    self.assertEqual( [v for v in sectorRange(0,0    )], [] )
    self.assertEqual( [v for v in sectorRange(0,0,0  )], [] )
    self.assertEqual( [v for v in sectorRange(3,3    )], [] )
    self.assertEqual( [v for v in sectorRange(1      )], [ZERO] )
    self.assertEqual( [v for v in sectorRange(0,1    )], [ZERO] )
    self.assertEqual( [v for v in sectorRange(0,-1,-1)], [ZERO] )
    self.assertEqual( [v for v in sectorRange(2      )], [ZERO]+list(NEIGHBORS_2D) )
    self.assertEqual( [v for v in sectorRange(0,2    )], [ZERO]+list(NEIGHBORS_2D) )
    self.assertEqual( [v for v in sectorRange(1,-1,-1)], list(NEIGHBORS_2D)+[ZERO] )
    self.assertEqual( [v for v in sectorRange(1,2    )], list(NEIGHBORS_2D) )
    self.assertEqual( [v for v in sectorRange(1,2,1  )], list(NEIGHBORS_2D) )
    self.assertEqual( [v for v in sectorRange(3      )], [ZERO]+list(NEIGHBORS_2D)+list(_R2_2D) )
    self.assertEqual( [v for v in sectorRange(2,-1,-1)], list(_R2_2D)+list(NEIGHBORS_2D)+[ZERO] )
    self.assertEqual( [v for v in sectorRange(1,2,1,1,5)], list(NEIGHBORS_2D)[1:5] )
    self.assertEqual( [v for v in sectorRange(1,2,1,3,0,-1)], list(reversed(NEIGHBORS_2D[1:4])) )

if __name__=='__main__': unittest.main()

