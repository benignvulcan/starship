
import sys, math, collections, unittest

_S = math.sqrt(3.0)/2.0 # + sys.float_info.epsilon does not really help
_EPSILON = 10 ** (2 - sys.float_info.dig)  # experimentally determined number of digits

class Vexor4d(collections.namedtuple('Vexor4dTuple','x y z v w')):
  # Where:
  #   x+y+z = 0 = 2D hexagonal coordinates
  #   v = vertical = cartesian z
  #   w = forth spatial dimension; +w = "ana", -w = "kata"
  def isValid(self):
    return abs(self.x + self.y + self.z) < _EPSILON
  def __add__(self, other):
    return Vexor4d(self.x+other.x, self.y+other.y, self.z+other.z, self.v+other.v, self.w+other.w)
  def toRectCoords(self):
    "Return conventional x,y,z,w 4-dimensional rectangular coordinates"
    # Sadly, this often returns a float x value that when squared becomes
    #   .7499999999999999 when it should be .75
    # Using round() may help: round(Vexor(1,0,-1).toRectCoords(), 12)
    return (_S*self.x,  (float(self.y) - self.z)/2.0, self.v, self.w)

def toVexor4d(x,y,z,w):
  return Vexor4d( x/_S, y - x/_S/2.0, -x/_S/2.0 - y, z, w)
