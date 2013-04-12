#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import QPointF, QRectF
#from PyQt4.QtGui  import QBrush, QColor, QPen, QPolygonF
import simulation

class HexTileGraphicsView(QtGui.QGraphicsView):
  '''
    A view on to a HexTileGraphicsScene. (There may be other views on the same scene.)
      No scroll bars. (not implemented yet)
      Do not pan past edge. (not implemented yet)
      Map movement directions from view to scene/model.
  '''
  model_event = QtCore.pyqtSignal(int)

  def __init__(self, parent):
    QtGui.QGraphicsView.__init__(self, parent)
    #self.setOptimizationFlags(self.DontAdjustForAntialiasing) # does not disbale antialiasing!
    #self.setDragMode(QtGui.QGraphicsView.RubberBandDrag)  # set via Designer
    self._zoom = 1.0
    self._duodecimants = 0   # track number of duodecimants (30 degree rotations)
    self._depressedOctants = set()
    #self.setViewportUpdateMode(QtGui.QGraphicsView.NoViewportUpdate)
    print "HexTileGraphicsView.viewportUpdateMode =", self.viewportUpdateMode()
    #self.translate(0.5,0.5)
    self.Zoom(32)
    #self.centerOn(0,0
  def Rotate(self, duodecimant):
    "Rotate (duodecimant * 30 degrees) CCW."
    self._duodecimants = (self._duodecimants + duodecimant) % 12
    print "HexTileGraphicsView.Rotate(%s): rotating to %d duodecimants" % (duodecimant, self._duodecimants)
    self.rotate(30*(duodecimant%12))
  ZOOM_FACTOR = 3 ** (1/3.0)
  def Zoom(self, f=None):
    if f is None: f = self.ZOOM_FACTOR
    z = self._zoom * f
    if z > 4 and z < 343:  # 7**3
      self._zoom = z
      self.scale(f,f)
  def ZoomIn(self):
    self.Zoom(self.ZOOM_FACTOR)
  def ZoomOut(self):
    self.Zoom(1/self.ZOOM_FACTOR)
  #def event(self, event):
  #  if event.type == QtCore.QEvent.
  #    return True
  #  return MyMainWindowDesign.event(event)
  def wheelEvent(self, event):
    #print "wheelEvent.delta() =", event.delta() / 8.0
    f = self.ZOOM_FACTOR ** (event.delta() / 120.0)  # 120 = 15 degrees = 1 typical wheel step
    self.Zoom(f)

  # Sigh. Type QtCore.Key is not exposed, even though event.key() returns objects of that type.
  key2octant = dict( ((int(k),int(m)),v) for ((k,m),v) in
    { (QtCore.Qt.Key_6        , QtCore.Qt.KeypadModifier) : 0
    , (QtCore.Qt.Key_Right    , QtCore.Qt.KeypadModifier) : 0
    , (QtCore.Qt.Key_Right    , QtCore.Qt.NoModifier    ) : 0
    , (QtCore.Qt.Key_9        , QtCore.Qt.KeypadModifier) : 1
    , (QtCore.Qt.Key_PageUp   , QtCore.Qt.KeypadModifier) : 1
    , (QtCore.Qt.Key_8        , QtCore.Qt.KeypadModifier) : 2
    , (QtCore.Qt.Key_Up       , QtCore.Qt.KeypadModifier) : 2
    , (QtCore.Qt.Key_Up       , QtCore.Qt.NoModifier    ) : 2
    , (QtCore.Qt.Key_7        , QtCore.Qt.KeypadModifier) : 3
    , (QtCore.Qt.Key_Home     , QtCore.Qt.KeypadModifier) : 3
    , (QtCore.Qt.Key_4        , QtCore.Qt.KeypadModifier) : 4
    , (QtCore.Qt.Key_Left     , QtCore.Qt.KeypadModifier) : 4
    , (QtCore.Qt.Key_Left     , QtCore.Qt.NoModifier    ) : 4
    , (QtCore.Qt.Key_1        , QtCore.Qt.KeypadModifier) : 5
    , (QtCore.Qt.Key_End      , QtCore.Qt.KeypadModifier) : 5
    , (QtCore.Qt.Key_2        , QtCore.Qt.KeypadModifier) : 6
    , (QtCore.Qt.Key_Down     , QtCore.Qt.KeypadModifier) : 6
    , (QtCore.Qt.Key_Down     , QtCore.Qt.NoModifier    ) : 6
    , (QtCore.Qt.Key_3        , QtCore.Qt.KeypadModifier) : 7
    , (QtCore.Qt.Key_PageDown , QtCore.Qt.KeypadModifier) : 7
    }.iteritems() )
  def keyPressEvent(self, event):
    k = int(event.key())
    m = int(event.modifiers())
    if (k,m) in self.key2octant:
      o = self.key2octant[(k,m)]
      print "octkey#%d" % o,
      self._depressedOctants.add(o)
      if self._depressedOctants == set([0,2]):
        o = 1
      elif self._depressedOctants == set([2,4]):
        o = 3
      elif self._depressedOctants == set([4,6]):
        o = 5
      elif self._depressedOctants == set([6,0]):
        o = 7
      model = self.scene().Model()
      model.Player().PostInput(simulation.Walk(self._duodecimants*30 + o*45))
      #self.CenterOnCell( self.scene().Model().Player().Parent() )
      #self.scene().update()
      #self.scene().UpdateFromModel()
      # TODO: get app/framewnd/simulation to process this right away
      #model.Scheduler().ExecEventsFor(model.Player().AnticipatedReadyDelay())
      self.model_event.emit(666)
    elif k == QtCore.Qt.Key_PageUp:
      self.scene().FlipLayer(1)
    elif k == QtCore.Qt.Key_PageDown:
      self.scene().FlipLayer(-1)
    elif k == QtCore.Qt.Key_BracketLeft or k == QtCore.Qt.Key_Slash:
      self.Rotate(-1)
    elif k == QtCore.Qt.Key_BracketRight or k == QtCore.Qt.Key_Asterisk:
      self.Rotate(1)
    elif k == QtCore.Qt.Key_Plus:
      self.ZoomIn()
    elif k == QtCore.Qt.Key_Minus:
      self.ZoomOut()
    else:
      print "HexTileGraphicsView.keyPressEvent(): key=%08x, modifers=%08x" % (k,m)
      QtGui.QGraphicsView.keyPressEvent(self, event)
    #print type(k), type(m), type(QtCore.Qt.Key_Right), type(QtCore.Qt.NoModifier)
  def keyReleaseEvent(self, event):
    k = int(event.key())
    m = int(event.modifiers())
    if (k,m) in self.key2octant:
      o = self.key2octant[(k,m)]
      self._depressedOctants.discard(o)
  def CenterOnCell(self, c):
    cx,cy,_v,_w = c.Pos().toRectCoords()
    print "Centering on %s -> %g,%g" % (c,cx,cy)
    self.centerOn(QPointF(cx,-cy))

