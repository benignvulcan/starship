#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math
from PyQt4 import QtCore, QtGui
#from PyQt4 import QtOpenGL
from PyQt4.QtGui  import QBrush, QColor, QPen

from qtmath import *
import simulation

class GraphicsLayerItem(QtGui.QGraphicsItemGroup):
  pass

class GraphicsTileItem(QtGui.QGraphicsPolygonItem):
  ''' A graphical description of a single hexagonal cell.
  '''

  polygon_vertices = RegularPolygon(n=6, apothem=simulation.CELL_APOTHEM, rotate=-math.pi/2)

  def __init__(self, cell, parent):
    QtGui.QGraphicsPolygonItem.__init__(self, self.polygon_vertices, parent)
    self._cell = cell
    self.setFlags( self.flags()
                 | QtGui.QGraphicsItem.ItemIsSelectable
                 | QtGui.QGraphicsItem.ItemIsFocusable
                #| QtGui.QGraphicsItem.ItemClipsToShape
                #| QtGui.QGraphicsItem.ItemIsMovable
                 )
    self.setPen(QtGui.QPen(QtGui.QColor(31,31,31), .05))
    self.setBrush(QtCore.Qt.yellow)
    self.selectionPen = QtGui.QPen(QtCore.Qt.white, .05)

  def paint(self, painter, option, widget=0):
    bgColor = QtGui.QColor.fromHsv(*self._cell.GetBgColor())
    if self._cell.isTargeted():
      brush = QBrush(bgColor, QtCore.Qt.Dense4Pattern)
      brush.setTransform(QtGui.QTransform.fromScale(.1,.1))
    else:
      brush = QBrush(bgColor)
    painter.setBrush(brush)
    if self.isSelected():
      painter.setPen(self.selectionPen)
    else:
      painter.setPen(self.pen())
    clipping_path = QtGui.QPainterPath()
    clipping_path.addPolygon(self.polygon())
    painter.setClipPath(clipping_path)
    painter.drawConvexPolygon(self.polygon())
    #painter.drawPolygon(self.polygon())
    for o in self._cell._objects:
      if isinstance(o, simulation.NPC):
        painter.setPen(self.pen())
        #painter.setBrush(QtCore.Qt.blue)
        painter.setBrush(QtGui.QColor.fromHsv(*o.GetColor()))
        r = simulation.CELL_APOTHEM*3/4.0
        painter.drawEllipse(QPointF(0,0), r, r)
        break
    for o in self._cell._objects:
      if isinstance(o, simulation.Player):
        #print "painting player" #, [self.polygon_vertices[i] for i in range(6)]
        painter.setPen(self.pen())
        #painter.setBrush(QtCore.Qt.magenta)
        painter.setBrush(QtGui.QColor.fromHsv(*o.GetColor()))
        #painter.setPen(QtCore.Qt.magenta)
        r = simulation.CELL_APOTHEM*3/4.0
        #print "draw(%s,%s,%s,%s)" % (-r,-r,2*r,2*r)
        painter.drawEllipse(QPointF(0,0), r, r)
        #painter.drawRect(-r,-r,2*r,2*r)
        #painter.drawRect(-1,-1,2,2)
        #painter.drawRect(-1,-1,1,1)
        #painter.drawConvexPolygon(self.polygon())
    if False:
      # paint region number
      painter.setBrush(self.brush())
      painter.setPen(QtCore.Qt.yellow)
      #painter.setFont(QtGui.QFont("Helvetica", 8))
      painter.scale(.03, .03)
      painter.drawText(QPointF(0,0), str(self._cell._region))

class HexTileGraphicsScene(QtGui.QGraphicsScene):
  '''
    The graphical description of (a portion) of a hex tiled model.
    It is NOT the model, nor the view.
    One of it's jobs is to cooperate with the model in maintaining sane coordinate indexing?
    Deal with selection (& focus?)

    Model is in regular mathematical coordinates.
    Sceen (and View) is in screen coordinates.
  '''
  def __init__(self, model):
    QtGui.QGraphicsScene.__init__(self)
    self._model = model  # simulation
    self._layers = {}    # map from z values to GraphicsItem layer master objects
    self._currentLayer = 0
    self.setBackgroundBrush(QtCore.Qt.black)
    self.addAxisLines()
    self.CreateLayers(self._model._cells)
    self.addCells(self._model._cells)
  def addAxisLines(self):
    xaxis = QtGui.QGraphicsLineItem(-10,0,10,0)
    yaxis = QtGui.QGraphicsLineItem(0,-10,0,10)
    p = QPen(QBrush(QtGui.QColor(31,31,31)), 0, QtCore.Qt.DotLine)
    xaxis.setPen(p)
    yaxis.setPen(p)
    self.addItem(xaxis)
    self.addItem(yaxis)
  def CreateLayers(self, cells):
    "For each layer, create a GraphicsLayerItem to serve as it's parent."
    (low, high) = cells.GetBoundsVertical()
    for i in range(low, high+1):
      y = GraphicsLayerItem()
      y.setZValue(i)
      self.addItem(y)
      self._layers[i] = y
      y.setVisible(i == self._currentLayer)
    print "{0} layers created".format(len(self._layers))
  def FlipLayer(self, delta):
    newLayer = self._currentLayer + delta
    if newLayer in self._layers:
      self._currentLayer = newLayer
      for i in self._layers:
        self._layers[i].setVisible(i == self._currentLayer)
  def addCells(self, cells):
    n = 13
    for v in cells.iterkeys():
      x, y, z, _w = v.toRectCoords()
      h = GraphicsTileItem(cells[v], parent=self._layers[z])
      h.moveBy(x,-y)
      #u = abs(round(v.x))%2 + abs(round(v.y))%2 + abs(round(v.z))%2  # dotted
      #u = ( abs(round(v.x)) + abs(round(v.y)) + abs(round(v.z)) )%3   # concentric
      #u = ( abs(round(v.x)) + 2*abs(round(v.y)) + 3*abs(round(v.z)) )%3   # different in different sectors
      #u = abs(round(v.x))%2 + abs(round(v.y))%2   # dotted and striped in alternating rows
      #u = ( abs(round(v.x)) + abs(round(v.y)) )%3
      #h.setBrush(QtGui.QColor.fromHsv( (360.0*v.x/n)%360, (256.0*v.y/n)%256, (256.0*v.z/n)%256 ))
      #h.setBrush(QtGui.QColor.fromHsv( u*120, (256.0*v.y/n)%256, (256.0*v.z/n)%256 ))
      #self.addItem(h) # redundant with actually setting a parent

      #if cells[v]._objects:
      #  # create player circle object
      #  r = CELL_APOTHEM/2.0
      #  e = QtGui.QGraphicsEllipseItem(-r,-r,r*2,r*2, h)
      #  e.setBrush(QtGui.QColor.fromHsv(60,255,255))
      #  #e.setPen(QtGui.QPen(QtGui.QColor(0,0,0)))

      if False:
        # add Vexor labels
        textItem = QtGui.QGraphicsSimpleTextItem("% 2d,% 2d,% 2d"%(round(v.x),round(v.y),round(v.z)))
        textItem = QtGui.QGraphicsSimpleTextItem("% 2d,% 2d"% v.toSkewXY())
        textItem.setBrush(QtGui.QColor.fromHsv(360/6, 255, 255))
        ts = .01
        textItem.setPen(QtGui.QPen(QBrush(QtCore.Qt.black),0))
        textItem.scale(ts,ts)
        textItem.moveBy(x-.25,-y-.1)
        self.addItem(textItem)
    print "{0} GraphicsTileItems created".format(len(cells))

  def Model(self): return self._model

  def UpdateFromModel(self):
    "Update GraphicsTileItems whose corresponding Cells in the simulation model have changed."
    # No need to store mapping or references from Cells or Vexors to GraphicsTileItems
    #   (in this class or in the model)
    #   when QGraphicsScene already indexes them by rectangular coordinates.
    changedCells = self._model.PopChanges()
    #print "UpdateFromModel(): changedCells =", changedCells
    for c in changedCells:
      x,y, _z, _w = c.Pos().toRectCoords()
      for i in self.items(QPointF(x,-y)):   # this iterates all z depths
        #print i, i.boundingRect()
        #i.update()
        i.update(i.boundingRect())
    if not self._model._centerOn is None:
      for v in self.views():
        v.CenterOnCell(self._model._centerOn)
      self._model._centerOn = None

