
import sys, math, collections, unittest

#import decimal
#_S_DECIMAL = decimal.Decimal(3).sqrt()/2

_S = math.sqrt(3.0)/2.0 # + sys.float_info.epsilon does not really help
_EPSILON = 10 ** (2 - sys.float_info.dig)  # experimentally determined number of digits

class Vexor(collections.namedtuple('VexorTuple','x y z')):
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
    return "Vexor(%g,%g,%g)" % self
    #return "Vexor(% 9.4f,% 9.4f,% 9.4f)" % self
  def isValid(self):
    return abs(self.x + self.y + self.z) < _EPSILON
  def __add__(self, other):
    return Vexor(self.x+other.x, self.y+other.y, self.z+other.z)
  def __sub__(self, other):
    return Vexor(self.x-other.x, self.y-other.y, self.z-other.z)
  def __mul__(self, scalar):
    return Vexor(self.x*scalar, self.y*scalar, self.z*scalar)
  def __rmul__(self, scalar):
    return Vexor(scalar*self.x, scalar*self.y, scalar*self.z)
  def __div__(self, scalar):
    return Vexor(self.x/scalar, self.y/scalar, self.z/scalar)
  def __rdiv__(self, scalar):
    return Vexor(scalar/self.x, scalar/self.y, scalar/self.z)
  def __neg__(self):
    return Vexor(-self.x, -self.y, -self.z)
  def __pos__(self):
    return self
  def __eq__(self, other):
    return isinstance(other, Vexor) and all(a == b for a,b in zip(self, other))
  def __ne__(self, other):
    return not isinstance(other, Vexor) or any(a != b for a,b in zip(self, other))
  def toSkewXY(self):
    return (self.x, self.y)
  def toRectCoords(self):
    # Sadly, this often returns a float x value that when squared becomes
    #   .7499999999999999 when it should be .75
    # Using round() may help: round(Vexor(1,0,-1).toRectCoords(), 12)
    return (_S*self.x,  (float(self.y) - self.z)/2.0 )
  def __abs__(self):
    # Assuming absolute value = length = magnitude = Euclidean plane distance.
    # Note that len() will return the number of elements in the tuple.
    # Sadly, this often returns .9999999999999999 when it should return 1.0
    x, y = self.toRectCoords()
    return math.sqrt(x**2+y**2)
    #x, y = _S_DECIMAL * self.x, (decimal.Decimal(self.y) - self.z)/2
    #return float((x**2+y**2).sqrt())
  def manhattanLength(self):
    "Distance to the origin, taking only integral steps perpendicular to axes."
    # If Manhattan were laid out on a hexagonal plan, that is...
    return max(abs(self.x), abs(self.y), abs(self.z))
  def manhattanDistance(self, other):
    return (self - other).manhattanLength()
  # These would seem to be incorrect definitions of dot and cross product
  #   for this vector space:
  #  Vexor(1,0,-1) `dotProduct` Vexor(0,1,-1) = 1
  #  Vexor(1,0,-1).toRectCoords() `dotProduct` Vexor(0,1,-1).toRectCoords() = .5
  #def dotProduct(self, other):
  #  return sum(map(lambda a,b: a*b, self, other))
  #def crossProduct(self, other):
  #  return Vexor( self.y*other.z - self.z*other.y
  #              , self.z*other.x - self.x*other.z
  #              , self.x*other.y - self.y*other.x
  #              )
  rotated180 = __neg__
  def rotatedCCW120(self):
    return Vexor(self.z, self.x, self.y)
  def rotatedCW120(self):
    return Vexor(self.y, self.z, self.x)
  def rotatedCCW60(self):
    return Vexor(-self.y, -self.z, -self.x)
  def rotatedCW60(self):
    return Vexor(-self.z, -self.x, -self.y)
  def mirroredAboutX(self):
    return Vexor(self.x, self.z, self.y)        # x stays the same, yz flip
  def mirroredAboutY(self):
    return Vexor(self.z, self.y, self.x)
  def mirroredAboutZ(self):
    return Vexor(self.y, self.x, self.z)
  def mirroredAlongX(self):
    return Vexor(-self.x, -self.z, -self.y)     # x flips, yz "stay the same"
  def mirroredAlongY(self):
    return Vexor(-self.z, -self.y, -self.x)
  def mirroredAlongZ(self):
    return Vexor(-self.y, -self.x, -self.z)

def toVexor(x,y):
  return Vexor( x/_S, y - x/_S/2.0, -x/_S/2.0 - y)
  #x, y = decimal.Decimal(x), decimal.Decimal(y)
  #return Vexor( float(x/_S_DECIMAL), float(y - x/_S_DECIMAL/2), float(-x/_S_DECIMAL/2 - y))

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
        i = NEIGHBORS[x] * r
        istep = NEIGHBORS[(x+2)%6] * cell_step
        for count in range(r):
          yield i
          i += istep
        x += sextant_step
    r += rstep

def texture1(v):
  "A basic 3-coloring for hexagonal tiling."
  values = \
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
  x,y = v.toSkewXY()
  x %= 3
  y %= 3
  return values[(x,y)]

ZERO = Vexor(0,0,0)
NEIGHBORS = \
  ( Vexor( 1, 0,-1)
  , Vexor( 0, 1,-1)
  , Vexor(-1, 1, 0)
  , Vexor(-1, 0, 1)
  , Vexor( 0,-1, 1)
  , Vexor( 1,-1, 0)
  )
SEVEN = (ZERO,)+NEIGHBORS
_R2 = \
  ( Vexor( 2, 0,-2)
  , Vexor( 1, 1,-2)
  , Vexor( 0, 2,-2)
  , Vexor(-1, 2,-1)
  , Vexor(-2, 2, 0)
  , Vexor(-2, 1, 1)
  , Vexor(-2, 0, 2)
  , Vexor(-1,-1, 2)
  , Vexor( 0,-2, 2)
  , Vexor( 1,-2, 1)
  , Vexor( 2,-2, 0)
  , Vexor( 2,-1,-1)
  )

class TestVexor(unittest.TestCase):
  def testVexor(self):
    for s in range(-3, 4):
      for n in NEIGHBORS:
        h = Vexor(n.x*s, n.y*s, n.z*s)
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
    for n in NEIGHBORS:
      self.assertEqual( n.manhattanLength(), 1 )
      self.assertEqual( n.manhattanDistance(ZERO), 1 )
    for n in _R2:
      self.assertEqual( n.manhattanLength(), 2 )
      self.assertEqual( n.manhattanDistance(ZERO), 2 )
    for n in SEVEN + _R2:
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
      self.assertEqual( n / 1, n )
  def testSectorRange(self):
    self.assertEqual( [v for v in sectorRange(0      )], [] )
    self.assertEqual( [v for v in sectorRange(0,0    )], [] )
    self.assertEqual( [v for v in sectorRange(0,0,0  )], [] )
    self.assertEqual( [v for v in sectorRange(3,3    )], [] )
    self.assertEqual( [v for v in sectorRange(1      )], [ZERO] )
    self.assertEqual( [v for v in sectorRange(0,1    )], [ZERO] )
    self.assertEqual( [v for v in sectorRange(0,-1,-1)], [ZERO] )
    self.assertEqual( [v for v in sectorRange(2      )], [ZERO]+list(NEIGHBORS) )
    self.assertEqual( [v for v in sectorRange(0,2    )], [ZERO]+list(NEIGHBORS) )
    self.assertEqual( [v for v in sectorRange(1,-1,-1)], list(NEIGHBORS)+[ZERO] )
    self.assertEqual( [v for v in sectorRange(1,2    )], list(NEIGHBORS) )
    self.assertEqual( [v for v in sectorRange(1,2,1  )], list(NEIGHBORS) )
    self.assertEqual( [v for v in sectorRange(3      )], [ZERO]+list(NEIGHBORS)+list(_R2) )
    self.assertEqual( [v for v in sectorRange(2,-1,-1)], list(_R2)+list(NEIGHBORS)+[ZERO] )
    self.assertEqual( [v for v in sectorRange(1,2,1,1,5)], list(NEIGHBORS)[1:5] )
    self.assertEqual( [v for v in sectorRange(1,2,1,3,0,-1)], list(reversed(NEIGHBORS[1:4])) )

if __name__=='__main__': unittest.main()

