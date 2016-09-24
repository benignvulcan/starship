#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math
from PyQt5 import QtCore, QtGui, QtWidgets
#from PyQt4 import QtOpenGL
from PyQt5.QtGui  import QBrush, QColor, QPen

from qtmath import *
import simulation
import vexor5

textures2hsv = \
  { simulation.Textures.VOID      : (  0,   0,   0)
  , simulation.Textures.BULKHEAD  : (240,  15,  63)
  , simulation.Textures.DECK      : (200,  15, 191)
  }
sevenHueMap = [0,30,60,120,180,240,300]

def Texture2HSV(tx, pos):
  'Given a texture and a vexor position, return a color.'
  h,s,v = textures2hsv[tx]
  if tx in (simulation.Textures.BULKHEAD, simulation.Textures.DECK):
    tupity = vexor5.uniform3coloring(pos)
    #h,s,v = (h, s, v + tupity*16 )
    h,s,v = (sevenHueMap[tupity], s*3, v)
  return (h,s,v)

#class GraphicsLayerItem(QtWidgets.QGraphicsItemGroup):
class GraphicsLayerItem(QtWidgets.QGraphicsRectItem):
  pass

class GraphicsTileItem(QtWidgets.QGraphicsPolygonItem):
  ''' A graphical description of a single hexagonal cell.
  '''

  # To minimize storage size and paint time, factor common values out into class variables.
  hexagon_qpolyf = None
  hexagon_qpainterpath = None
  selection_pen = None
  _oldLOD = None

  @classmethod
  def InitClassVariables(cls):
    cls.hexagon_qpolyf = RegularPolygon(n=6, apothem=simulation.CELL_APOTHEM, rotate=-math.pi/2)
    cls.hexagon_qpainterpath = QtGui.QPainterPath()
    cls.hexagon_qpainterpath.addPolygon(cls.hexagon_qpolyf)
    cls.selectionPen = QtGui.QPen(QtCore.Qt.white, .05)

  def __init__(self, cell, parent):
    QtWidgets.QGraphicsPolygonItem.__init__(self, self.hexagon_qpolyf, parent)
    self._cell = cell
    self._renderSpec = ()   # a list of instructions on how to render this cell
    self._renderCache = {}  # map from (renderSpec,level_of_detail) to QPixMap
    self.setFlags( self.flags()
                 | QtWidgets.QGraphicsItem.ItemIsSelectable
                 | QtWidgets.QGraphicsItem.ItemIsFocusable
                #| QtWidgets.QGraphicsItem.ItemIgnoresTransformations
                #| QtWidgets.QGraphicsItem.ItemClipsToShape
                #| QtWidgets.QGraphicsItem.ItemIsMovable
                 )
    # speeds window sizing and repainting, but not zooming or rotating
    self.setCacheMode(QtWidgets.QGraphicsItem.DeviceCoordinateCache)
    #self.setCacheMode(QtWidgets.QGraphicsItem.ItemCoordinateCache)   # looks hideous, but it is even faster
    self.setPen(QtGui.QPen(QtGui.QColor(31,31,31), .05))
    self.setBrush(QtCore.Qt.yellow)
    self.UpdateRenderSpec()

  def UpdateRenderSpec(self):
    self._renderSpec = tuple(self._cell.GetRenderSpec())

  def paint(self, painter, option, widget=0):
    # TODO: For a given zoom level and rotation and cell contents,
    # cache tile rendering in a bitmap.  Since many tiles are often identical
    # this should provide a substatial speedup.
    # TODO: Strategy: Using the given painter's transformation,
    # extract size and orientation, then reset the transform and
    # either blit from cache or manually scale and rotate painting into
    # a QPixMap, and then blit it.
    # TODO: Extend the above technique so that in the same way, alpha-masked
    # pixmaps of the various component drawing operations are cached.
    lod = option.levelOfDetailFromTransform(painter.worldTransform())
    if lod != GraphicsTileItem._oldLOD:
      GraphicsTileItem._oldLOD = lod
      print "GraphicsTileItem level of detail = {0}".format(lod)
    #painter.resetTransform()  # restore to device coordinates, 1 = 1 pixel
    #key = (self._renderSpec, lod, orientation)
    #if key in self._renderCache:
    #  bitBlt
    #else:
    #  pixm = QPixMap(svgr.defaultSize())
    #  painter = QPainter(pixm)
    if lod >= 23:
      painter.setClipPath(self.hexagon_qpainterpath)
    painter.setPen(QtCore.Qt.NoPen)
    for (renderObj, arg) in self._renderSpec:
      if renderObj == simulation.RenderObjects.BG:
        painter.setBrush(QBrush(QtGui.QColor.fromHsv(*Texture2HSV(arg, self._cell.Pos()))))
        if self.isSelected():
          painter.setPen(self.selectionPen)
        elif lod >= 23:
          painter.setPen(self.pen())
        painter.drawConvexPolygon(self.polygon())
        painter.setPen(QtCore.Qt.NoPen)
      elif renderObj == simulation.RenderObjects.TARGETING:
        brush = QBrush(QtGui.QColor(255,127,0), QtCore.Qt.Dense4Pattern)
        brush.setTransform(QtGui.QTransform.fromScale(.1,.1))
        painter.setBrush(brush)
        painter.drawConvexPolygon(self.polygon())
      elif renderObj == simulation.RenderObjects.NPC or renderObj == simulation.RenderObjects.PLAYER:
        painter.setBrush(QtGui.QColor.fromHsv(*arg))
        r = simulation.CELL_APOTHEM*3/4.0
        painter.drawEllipse(QPointF(0,0), r, r)
    if False:
      # paint some debugging text
      painter.setPen(QtCore.Qt.white)
      painter.setBrush(self.brush())
      #painter.setFont(QtGui.QFont("Helvetica", 8))
      scale = .02
      painter.scale(scale,scale)
      r = QtCore.QRectF(-.5/scale,-.5/scale,1/scale,1/scale)
      #txt = "{0},{1},{2}".format(self._cell.Pos().x, self._cell.Pos().y, self._cell.Pos().z)
      txt = "{0}".format( vexor5.uniform3coloring(self._cell.Pos()) )
      #txt = str(self._cell._region)
      painter.drawText(r, QtCore.Qt.AlignCenter, txt)

GraphicsTileItem.InitClassVariables()  # move this into main() if it stops working here

class HexTileGraphicsScene(QtWidgets.QGraphicsScene):
  '''
    The graphical description of (a portion) of a hex tiled model.
    It is NOT the model, nor the view.
    One of it's jobs is to cooperate with the model in maintaining sane coordinate indexing?
    Deal with selection (& focus?)

    Model is in regular mathematical coordinates.
    Sceen (and View) is in screen coordinates.
  '''
  def __init__(self, model):
    QtWidgets.QGraphicsScene.__init__(self)
    self._model = model  # simulation
    self._vexor2item = { } # map from Vexor to [list of] GraphicsTileItem
    self._layers = {}    # map from z values to GraphicsItem layer master objects
    self._currentLayer = 0
    self.setSceneRect(-75,-75,150,150)
    self.setBackgroundBrush(QtCore.Qt.black)
    #self.addAxisLines()
    self.CreateLayers(self._model._cells)
    assert self.itemIndexMethod() == QtWidgets.QGraphicsScene.BspTreeIndex
    #self.setItemIndexMethod(QtWidgets.QGraphicsScene.NoIndex)
    print "HexTileGraphicsScene.bspTreeDepth = {0}".format(self.bspTreeDepth())
    self.addCells(self._model._cells)
    print "HexTileGraphicsScene.bspTreeDepth = {0}".format(self.bspTreeDepth())
    #if self.bspTreeDepth() == 0:
    #  self.setBspTreeDepth(6)
    #  print "HexTileGraphicsScene.bspTreeDepth = {0}".format(self.bspTreeDepth())
  def addAxisLines(self):
    xaxis = QtWidgets.QGraphicsLineItem(-10,0,10,0)
    yaxis = QtWidgets.QGraphicsLineItem(0,-10,0,10)
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
      self._vexor2item.setdefault(v,[]).append(h)

      #if cells[v]._objects:
      #  # create player circle object
      #  r = CELL_APOTHEM/2.0
      #  e = QtWidgets.QGraphicsEllipseItem(-r,-r,r*2,r*2, h)
      #  e.setBrush(QtGui.QColor.fromHsv(60,255,255))
      #  #e.setPen(QtGui.QPen(QtGui.QColor(0,0,0)))

      if False:
        # add Vexor labels
        textItem = QtWidgets.QGraphicsSimpleTextItem("% 2d,% 2d,% 2d"%(round(v.x),round(v.y),round(v.z)))
        textItem = QtWidgets.QGraphicsSimpleTextItem("% 2d,% 2d"% v.toSkewXY())
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
      #x,y, _z, _w = c.Pos().toRectCoords()
      #itms = self.items(QPointF(x,-y), QtCore.Qt.IntersectsItemBoundingRect, QtCore.Qt.AscendingOrder)
      #itms = [self.itemAt(x,-y)]
      itms = self._vexor2item[c.Pos()]
      #if len(itms) > 3:
      #  print "{n} items at {x},{y}: {items}".format(n=len(itms),x=x,y=-y,items=itms)
      for i in itms:   # this iterates all z depths
        #print i, i.boundingRect()
        #i.update()
        i.UpdateRenderSpec()
        i.update(i.boundingRect())
    if not self._model._centerOn is None:
      for v in self.views():
        v.CenterOnCell(self._model._centerOn)
      self._model._centerOn = None

