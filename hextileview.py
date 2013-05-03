#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math
from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import QPoint, QPointF, QRect, QRectF, QSize, QSizeF
import qtmath, vexor5
import simulation

def Hexagon(aRect, duodectant=0, antialiasing=False):
  "Return a (slightly squashed or stretched) hexagonal QPolygon fitting a rectangle."
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
    # |<--->|  x spacing = width * 3/4
    #   ____  _
    #  /\  /\
    # /__\/__\   y spacing = height
    # \  /\  /
    #  \/__\/ _
    #
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

class Tile(object):
  "The rendering of a particular cell to a tile on the screen."
  def __init__(self, cell):
    super(Tile, self).__init__()
    self._cell = cell
    self._bgcolor = QtCore.Qt.black
    #self._pen = QtGui.QPen(QtGui.QColor(31,31,31), .05)
    self._pen = QtGui.QPen(QtGui.QColor(255,0,0), 2)
    #self._pen.setWidth(1)
    #self._pen = QtCore.Qt.NoPen
    self._selectionPen = QtGui.QPen(QtCore.Qt.white)
    #self._brush = QtGui.QBrush(QtCore.Qt.cyan)
    self._isSelected = False
    self.UpdateRenderSpec()
  def UpdateRenderSpec(self):
    self._renderSpec = tuple(self._cell.GetRenderSpec())
  def Draw(self, painter, aRect, antialiasing=False):
    "Draw cell representation into the given rect/hexagon"
    #painter.fillRect(-width/2,-height/2,width,height, self._bgcolor)
    #if antialiasing:
    #  painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtCore.Qt.NoPen)
    hexagon = Hexagon(aRect, antialiasing=antialiasing)
    for (renderObj, arg) in self._renderSpec:
      if renderObj == simulation.RenderObjects.BG:
        painter.setBrush(QtGui.QBrush(QtGui.QColor.fromHsv(*Texture2HSV(arg, self._cell.Pos()))))
        if self._isSelected:
          painter.setPen(self._selectionPen)
        painter.setPen(self._pen)
        painter.drawConvexPolygon(hexagon)
        painter.setPen(QtCore.Qt.NoPen)
      elif renderObj == simulation.RenderObjects.TARGETING:
        brush = QtGui.QBrush(QtGui.QColor(255,127,0), QtCore.Qt.Dense4Pattern)
        brush.setTransform(QtGui.QTransform.fromScale(.1,.1))
        painter.setBrush(brush)
        painter.drawConvexPolygon(hexagon)
      elif renderObj == simulation.RenderObjects.NPC or renderObj == simulation.RenderObjects.PLAYER:
        painter.setBrush(QtGui.QColor.fromHsv(*arg))
        #r = simulation.CELL_APOTHEM*3/8.0
        r = int(aRect.width()/2) * 2 / 3.0
        print "Tile.Draw() NCP or PLAYER: r = {0}, center = {1}".format(r, aRect.center())
        painter.drawEllipse(QRectF(aRect).center(), r, r)

class HexTileView(QtGui.QWidget):
  def __init__(self, parent, theSimulation):
    QtGui.QWidget.__init__(self, parent)
    self._simulation = theSimulation
    self._tiles = {}   # map from Vexor to Tile
    self._renderCache = {}  # map from (renderSpec, size, orientation) to QImage
    self._zoom = 4
    self._SetTileSize(self._zoom * 8)
    self._currentLayer = 0
    self.setFocusPolicy(QtCore.Qt.StrongFocus)
    self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent) # disable filling bg from parent widget
    #self.setAutoFillBackground(False)       # disable filling bg from widget palette (default is False)
    self.AddCells(self._simulation._cells)
  def AddCells(self, cells):
    for vex in cells.iterkeys():
      t = Tile(cells[vex])
      self._tiles[vex] = t
  def _SetZoom(self, z):
    self._zoom = z
    self._SetTileSize(self._zoom * 8)
    self.update()
  def Zoom(self, dz):
    z = self._zoom + dz
    if z > 0 and z < 128:
      self._SetZoom(z)
  def _SetTileSize(self, height):
    '''Given the height (in whole pixels) of a hexagonal tile, compute
    the width and round off (distort) to the nearest whole pixel, so that
    (slightly distorted) hexagons will tile nicely.'''
    s = round(height*2/math.sqrt(3)) / height
    self._tileSize = QSize(int(height*s), height)
    self._tileCenter = QPoint(int(height*s/2), int(height/2))
    self._tileSpacing = QSize(int(self._tileSize.width()*3/4.0), height-1)  # see Hexagon()
    print "tileSize = {0}, tileCenter= {1}, tileSpacing = {2}".format(
      self._tileSize, self._tileCenter, self._tileSpacing)
  def Vexor2PixelCoords(self, v):
    x = self._tileSpacing.width() * v.x
    y = -self._tileSpacing.height() * (v.y - v.z)/2.0
    return QPoint(x,y)  # +y = down
  def Pixel2Vexor(self, qpt):
    # qpt +y = down
    sx = qpt.x() / self._tileSpacing.width()
    sy = -qpt.y() / self._tileSpacing.height()
    y = sy - sx/2.0
    z = -sx/2.0 - sy
    return vexor5.Vexor(sx,y,z,0,0)
  def paintEvent(self, evt):
    widgetPainter = QtGui.QPainter(self)
    widgetPainter.fillRect(evt.rect(), QtCore.Qt.green)  # paint widget background
    wRect = self.rect()
    wRect.moveCenter(QPoint(0,0))  # (0,0) is now centered, +y is still down
    widgetPainter.setWindow(wRect) # translate window painting coordinates

    antialiasing = True
    #widgetPainter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
    hexRect = QRect(QPoint(0,0), self._tileSize)  # extends right and *down*
    hexPath = QtGui.QPainterPath()
    hexPath.addPolygon(QtGui.QPolygonF(Hexagon(hexRect, antialiasing=antialiasing)))
    hexPath.closeSubpath()

    imgPainter = QtGui.QPainter()

    for vex in self._tiles:  # TODO: only iterate through visible tiles
      if vex.v != self._currentLayer:
        continue
      t = self._tiles[vex]
      key = (t._renderSpec, self._zoom)
      xy = self.Vexor2PixelCoords(vex) - self._tileCenter
      if not key in self._renderCache:
        print "HexTileView.paintEvent(): _renderCache miss"
        img = QtGui.QImage(self._tileSize, QtGui.QImage.Format_ARGB32_Premultiplied)
        #assert img.rect() == hexRect
        # Fill image, because in theory
        # creating a QPainter on uninitialized pixel data is undefined,
        # even if every pixel will be subsequently be overwritten.
        # I would like to fill using transparent magenta, but under PyQt 4.6,
        # QImage.fill() won't accept QColors and seems to incorrectly
        # interpret Python long integers, introducing bad bits.
        #img.fill(QtGui.QColor(0xFF, 0, 0xFF, 0).rgba())
        img.fill(QtCore.Qt.transparent)
        #for y in range(self._tileSize[1]):
        #  img.setPixel(y,y, 0xFF00FF00)
        #  img.setPixel(self._tileSize[0]-self._tileSize[1]+y,y, 0xFF00FF00)
        #img.setPixel(self._tileSize[0]-1, self._tileSize[1]-1, 0xFFFF00FF)

        #imgPainter = QtGui.QPainter(img)  # TODO: compare performance of ctor/del vs begin/end
        imgPainter.begin(img)
        #imgPainter.setWindow(-self._tileSize[0]/2.0, -self._tileSize[1]/2.0, self._tileSize[0], self._tileSize[1])
        if antialiasing:
          imgPainter.setRenderHint(QtGui.QPainter.Antialiasing)
        imgPainter.setClipPath(hexPath)
        #imgPainter.setPen(t._pen)
        #imgPainter.drawPath(hexPath)
        t.Draw(imgPainter, hexRect, antialiasing=antialiasing)
        #del imgPainter
        imgPainter.end()

        self._renderCache[key] = img

      # Note that since the screen does not have an alpha channel,
      # any transparent pixels will at this point be made visible?
      widgetPainter.drawImage(xy, self._renderCache[key])
    if True:
      # draw centered crosshairs
      widgetPainter.setPen(QtCore.Qt.white)
      widgetPainter.drawLine(-100,0, 100,0)
      widgetPainter.drawLine(0,-100, 0,100)

  def mousePressEvent(self, evt):
    pos = evt.pos() - self.rect().center()
    vex = self.Pixel2Vexor(pos)
    print "HexTileView.mousePressEvent @ {0} -> {1}".format(pos, vex)

  def keyPressEvent(self, evt):
    k = evt.key()
    print "HexTileView.keyPressEvent(): {0}".format(k)
    if k == QtCore.Qt.Key_Plus:
      self.Zoom(1)
    elif k == QtCore.Qt.Key_Minus:
      self.Zoom(-1)
    QtGui.QWidget.keyPressEvent(self, evt) # pass unhandled events to parent class

