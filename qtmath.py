
import math, unittest
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import QPointF, QRectF
from PyQt5.QtGui import QPolygonF

# These are apparently not defined by PyQt,
# but are implicitly converted to/from Python lists.
def QVector (seq): return map(lambda (x,y): QtCore.QPoint (x,y), seq)
def QVectorF(seq): return map(lambda (x,y): QtCore.QPointF(x,y), seq)

def RegularPolygon(n=6, s=None, apothem=None, circumradius=None, area=None, rotate=0.0):
  ''' Return a regular polygon with points in counter-clockwise order.
      rotate 0 to put a flat side to the right, rotate -pi/2 to put a flat side to the bottom.
  '''
  theta = 2*math.pi/n
  if not s is None:
    r = s / (2 * math.sin(math.pi / n))
  elif not apothem is None:
    r = apothem / math.cos(math.pi / n)
  elif not circumradius is None:
    r = circumradius
  elif not area is None:
    # A = 1/2 n r^2 sin(2pi/n)
    # 2A/(n sin(2pi/n)) = r^2
    # sqrt(2A/(n sin(2pi/n))) = r
    r = math.sqrt(2 * area / (n * math.sin(2*math.pi/n)))
  else:
    r = 1 / math.cos(math.pi / n)  # apothem=1
  rotate = rotate - theta/2
  return QtGui.QPolygonF(map(lambda i: QtCore.QPointF(r*math.cos(i*theta+rotate), r*math.sin(i*theta+rotate))
                            ,range(n)
                            )
                        )

class _TestQPolygons(unittest.TestCase):
  def test_QPolygon_intersection(self):
    tri1 = QVectorF([(0,0),(0,1),(1,0)])
    tri2 = QVectorF([(1,0),(0,0),(1,1)])
    tri3 = QVectorF([(.5,.5),(1,0),(0,0),(.5,.5)])
    tri3i = QVector([(1,1),(1,0),(0,0),(1,1)])
    sq1 = QVectorF([(0,0),(0,1),(1,1),(1,0)])
    # Intersect two triangles
    p1 = QPolygonF(tri1)
    p2 = QPolygonF(tri2)
    p3 = p1.intersected(p2)
    self.assertTrue( p1 == p1 )
    self.assertTrue( p1 == QPolygonF(tri1) )
    self.assertTrue( p3 == QPolygonF(tri3) )
    # Intersect two integer triangles
    p1 = QtGui.QPolygon(map(lambda (x,y): QtCore.QPoint(x,y), [(0,0),(0,1),(1,0)]))
    p2 = QtGui.QPolygon(map(lambda (x,y): QtCore.QPoint(x,y), [(1,0),(0,0),(1,1)]))
    p3 = p1.intersected(p2)
    self.assertTrue( p3 == QtGui.QPolygon(tri3i) )
    # Test containment/overlapping
    p1 = QtGui.QPolygonF(sq1)
    for v1 in sq1: self.assertTrue( p1.contains(v1) )        # vertices are contained
    self.assertTrue( p1.translated(2,0).intersected(p1).isEmpty() )
    self.assertTrue( p1.translated(1,0).intersected(p1).isEmpty() ) # common edges do not overlap
    self.assertFalse( p1.translated(.5,0).intersected(p1).isEmpty() )

if __name__=='__main__': unittest.main()

