#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math
from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import QPoint, QPointF, QRect, QRectF
import qtmath, vexor5

def Hexagon(aRect, duodectant=0, antialiasing=False):
  "Return a hexagonal QPolygon fitting a rectangle."
  # Note that QRects are inherently oriented to a +y=down coordinate system
  xc = aRect.center().x()
  yc = aRect.center().y()
  if duodectant % 2:
    # points up and down, flats to the sides
    yq = round(aRect.height() / 4.0)
    pts = [ QPoint(aRect.right(), yc-yq)
          , QPoint(xc, aRect.top())
          , QPoint(aRect.left(), yc-yq)
          , QPoint(aRect.left(), yc+yq)
          , QPoint(xc, aRect.bottom())
          , QPoint(aRect.right(), yc+yq)
          ]
  else:
    # points left and right, flats top and bottom
    xq = round(aRect.width() / 4.0)
    pts = [ QPoint(aRect.right(), yc)
          , QPoint(xc+xq, aRect.top())
          , QPoint(xc-xq, aRect.top())
          , QPoint(aRect.left(), yc)
          , QPoint(xc-xq, aRect.bottom())
          , QPoint(xc+xq, aRect.bottom())
          ]
  print "right={0},top={1},left={2},bottom={3}".format(aRect.right(), aRect.top(), aRect.left(), aRect.bottom())
  print "pts =", pts
  if antialiasing:
    return QtGui.QPolygonF(map(lambda p: QPointF(p)+QPointF(0.5,0.5), pts))
  return QtGui.QPolygon(pts)

class Tile(object):
  def __init__(self, vexorPos):
    super(Tile, self).__init__()
    self._vexorPos = vexorPos
    self._bgcolor = QtCore.Qt.black
    self._pen = QtGui.QPen(QtCore.Qt.red)
    self._pen.setWidth(1)
    #self._pen = QtCore.Qt.NoPen
    self._brush = QtGui.QBrush(QtCore.Qt.cyan)
  def Draw(self, painter, aRect, antialiasing=False):
    #painter.fillRect(-width/2,-height/2,width,height, self._bgcolor)
    if antialiasing:
      painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(self._pen)
    painter.setBrush(self._brush)
    #a = aRect.height()/2
    #hexagon = qtmath.RegularPolygon(n=6, apothem=a, rotate=-math.pi/2)
    hexagon = Hexagon(aRect, antialiasing=antialiasing)
    painter.drawConvexPolygon(hexagon)
    r = 8
    painter.setBrush(QtGui.QBrush(QtCore.Qt.blue))
    painter.drawEllipse(aRect.center(), r, r)

class HexTileView(QtGui.QWidget):
  def __init__(self, parent, theSimulation):
    QtGui.QWidget.__init__(self, parent)
    self._simulation = theSimulation
    self._tiles = {}   # map from Vexor to Tile
    self._SetTileSize(32)
    self.AddCells(self._simulation._cells)
  def AddCells(self, cells):
    for vex in cells.iterkeys():
      t = Tile(cells[vex])
      self._tiles[vex] = t
  def _SetTileSize(self, height):
    self._tileSize = (int(round(height*2/math.sqrt(3))), height)
    print "tileSize = {0}".format(self._tileSize)
  def Vexor2PixelCoords(self, v):
    x = self._tileSize[0] * v.x
    y = self._tileSize[1] * (v.y - v.z)/2.0
    return (x,y)
  def paintEvent(self, evt):
    widgetPainter = QtGui.QPainter(self)
    widgetPainter.setWindow(-self.width()/2, -self.height()/2, self.width(), self.height())
    # Set widget/window coordinate system: +y = up, center is (0,0)
    #widgetPainter.setWindow(-self.width()/2, self.height()/2, self.width(), -self.height())

    antialiasing = True
    sz = QtCore.QSize(*self._tileSize)
    hexRect = QRect(QPoint(0,0), sz)  # extends right and *down*
    img = QtGui.QImage(sz, QtGui.QImage.Format_ARGB32_Premultiplied)
    assert img.rect() == hexRect
    img.fill(0)  # creating a QPainter on uninitialized pixel data is undefined, in theory
    #img.fill(0xFFFFFFFF)  # creating a QPainter on uninitialized pixel data is undefined, in theory
    #for y in range(self._tileSize[1]):
    #  img.setPixel(y,y, 0xFF00FF00)
    #  img.setPixel(self._tileSize[0]-self._tileSize[1]+y,y, 0xFF00FF00)
    img.setPixel(self._tileSize[0]-1, self._tileSize[1]-1, 0xFFFF00FF)

    imgPainter = QtGui.QPainter(img)
    #imgPainter.setWindow(-self._tileSize[0]/2.0, -self._tileSize[1]/2.0, self._tileSize[0], self._tileSize[1])
    hexPath = QtGui.QPainterPath()
    hexPath.addPolygon(QtGui.QPolygonF(Hexagon(hexRect, antialiasing=antialiasing)))
    hexPath.closeSubpath()
    if antialiasing:
      imgPainter.setRenderHint(QtGui.QPainter.Antialiasing)
    imgPainter.setClipPath(hexPath)

    for vex in self._tiles:
      t = self._tiles[vex]
      imgPainter.setPen(t._pen)
      imgPainter.drawPath(hexPath)
      #t.Draw(imgPainter, hexRect, antialiasing=antialiasing)
      x,y = self.Vexor2PixelCoords(vex)
      widgetPainter.drawImage(x,y,img)
      #widgetPainter.drawImage(int(round(self._tileSize[0]*3/4.0)),self._tileSize[1]/2,img)
      #widgetPainter.drawImage(self._tileSize[0]*2+1, self._tileSize[1], img.scaled(sz*4))

    del imgPainter
    del img
    del widgetPainter

