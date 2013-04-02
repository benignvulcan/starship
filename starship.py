#!/usr/bin/env python
# -*- coding: utf-8 -*-
app_version = (0,0)
app_title = "Starship"
app_about_html = \
u'''<p>Version %d.%d
<p>Copyright &copy; 2012-2013 by Marty White under the GNU GPL V3
<p align="center"><i>&ldquo;To Boldly Simulate...&rdquo;</i>''' % app_version

import sys, time, unittest

from PyQt4 import QtCore, QtGui, uic
#from PyQt4 import QtOpenGL
from PyQt4.QtGui  import QBrush, QColor, QPen

import scene, simulation

if True:
  from starshipMainWindow_ui import Ui_StarshipMainWindow
  StarshipMainWindow_base = QtGui.QMainWindow
else:
  (Ui_StarshipMainWindow, StarshipMainWindow_base) = uic.loadUiType('starshipMainWindow.ui')

class StarshipMainWindow(Ui_StarshipMainWindow, StarshipMainWindow_base):
  def __init__(self):
    StarshipMainWindow_base.__init__(self)
    Ui_StarshipMainWindow.__init__(self)
    self.setupUi(self)  # instantiate widgets from .ui file, parenting to self

    self.menuBuild.setEnabled(False)

    #self.simulationParameters.setVisible(False) # does not toggle menu item
    self.actionSimulationParameters.activate(QtGui.QAction.Trigger)

    self._simModel = simulation.Simulation(qparent=self)

    self._scene = scene.HexTileGraphicsScene(self._simModel)
    self._scene.selectionChanged.connect(self.on__scene_selectionChanged)

    if False:
      self.textItem = QtGui.QGraphicsSimpleTextItem("Your text here!")
      self.textItem.setBrush(QtGui.QColor.fromHsv(240, 127, 255))
      self.textItem.scale(.05*SZ,.05*SZ)
      self.textItem.moveBy(-5*SZ,-6*SZ)
      self._scene.addItem(self.textItem)

    self.hexView.setScene(self._scene)
    #self.hexView.Zoom(128)
    #self.hexView.centerOn(0,0)
    #self.hexView.setAcceptDrops(True)
    self.hexView.model_event.connect(self.ExecSimCmd)

    # This single line of code causes rendering via OpenGL.
    # It's at least one order of magnitude faster.
    # See "-graphicssystem" option, and QApplication::setGraphicsSystem()
    #self.hexView.setViewport(QtOpenGL.QGLWidget())

    #self.simRateLimit.setValue(10000)
    self.simRateLimit.valueChanged.connect(self.on_action_simRateLimit_valueChanged)
    self.frameRateLimit.valueChanged.connect(self.on_action_frameRateLimit_valueChanged)

    self.cyclecount = 0
    self.simTimer = QtCore.QTimer(self)
    self.simTimer.timeout.connect(self.ExecSimulation)

    self.framecount = 0
    self.frameTimer = QtCore.QTimer(self)
    self.frameTimer.timeout.connect(self.frameUpdate)

    self.perfCycleStamp = 0
    self.perfFrameStamp = 0
    self.perfClockStamp = 0
    self.perfTimer = QtCore.QTimer(self)
    self.perfTimer.timeout.connect(self.perfUpdate)
    self.perfTimer.start(1000)

    self.actionAboutQt.triggered.connect(QtGui.qApp.aboutQt)
    self.actionSimRunning.setChecked(False)

    #f = self.statusBar().font()
    #f.setFixedPitch(True)
    #f.setKerning(False)
    #self.statusBar().setFont(f)
    self.performanceStatus = QtGui.QLabel()
    self.statusBar().addWidget(self.performanceStatus)

    print "simDockContents.sizeHint() =", self.simulationDockContents.sizeHint()
    print "simDockContents.size() =", self.simulationDockContents.size()

  #def event(self, event):
  #  if event.type == QtCore.QEvent.
  #    return True
  #  return MyMainWindowDesign.event(event)

  #@QtCore.pyqtSlot()
  def on__scene_selectionChanged(self):
    print "selectionChanged"
    selection = self._scene.selectedItems()
    self.menuBuild.setEnabled(len(selection)>0)

  @QtCore.pyqtSlot()
  def on_actionBuildDeck_triggered(self):
    print "actionBuildDeck"
    for gtile in self._scene.selectedItems():
      if not simulation.DECK in gtile._cell._objects:
        j = simulation.Construct(gtile._cell, simulation.DECK, timestamp=self._simModel.Now())
        self._simModel.PostJob(j)
      else: print "%s already contains deck" % (gtile._cell.Pos(),)
    self.frameUpdate()

  @QtCore.pyqtSlot()
  def on_actionBuildBulkhead_triggered(self):
    print "actionBuildBulkhead"
    for gtile in self._scene.selectedItems():
      if not simulation.BULKHEAD in gtile._cell._objects:
        self._simModel.PostJob( simulation.Construct(gtile._cell, simulation.BULKHEAD) )
      else: print "%s already contains bulkhead" % (gtile._cell.Pos(),)
    self.frameUpdate()

  @QtCore.pyqtSlot()
  def on_actionUnbuild_triggered(self):
    print "actionUnbuild"
    for gtile in self._scene.selectedItems():
      if simulation.BULKHEAD in gtile._cell._objects or simulation.DECK in gtile._cell._objects:
        self._simModel.PostJob( simulation.Unconstruct(gtile._cell) )
      else: print "%s is already empty" % (gtile._cell.Pos(),)
    self.frameUpdate()

  def keyPressEvent(self, event):
    k = event.key()
    if k == QtCore.Qt.Key_Escape:
      self.on_actionSimRunning_toggled(False)
      #QtGui.QMessageBox.information(self, "keyPressEvent", "Don't press Escape")
      #QtGui.QApplication.quit()
    #elif k == QtCore.Qt.Key_Space:
    #  self.action_SimRunning.toggle()
    elif k == QtCore.Qt.Key_G:
      selectedTiles = self._scene.selectedItems()
      if len(selectedTiles):
        self._simModel.Player().PostInput(simulation.GoTo([t._cell.Pos() for t in selectedTiles]))
        self.ExecSimCmd()
    else:
      print "StarshipMainWindow.keyPressEvent(%08x)" % k
      StarshipMainWindow_base.keyPressEvent(self, event)

  def ReceiveResult(self, *posargs, **kwargs):
    result = posargs[0]
    if result == "CenterOn":
      target = posargs[1]
      self.hexView.CenterOnCell(target)

  def ExecSimCmd(self):
    # Simulation has received user input, so run it a little, like taking a turn.
    # Problem:
    #   I want to be able to run limited time-slices of simulation (some of which may be uneventful)
    #     This requires preventing simTime from snapping to the first available event time.
    #   I want to be able to run the simulation until the Player object has done one thing.
    #     How to know how long one thing is?
    #       Wait until Player process has consumed (one item from?) input queue
    #         This does not advance time far enough
    #       Ask Player how long?  (It won't know until it's consumed some input)
    self.cyclecount += self._simModel.Scheduler().ExecEventsFor(dt=0)  # execute all immediate events
    dt = self._simModel.Player().DurationUntilNextCmd()  # now Player should know what's up
    print "ExecSimCmd: dt =", dt
    self.cyclecount += self._simModel.Scheduler().ExecEventsFor(dt)
    #self.cyclecount += self._simModel.Scheduler().ExecEventsFor(process=self._simModel.Player().GetCmdProcess())
    self.frameUpdate()

  # Each hundredth of a second, simulate a hundredth of a second, skewed by simRateLimit
  # Yield remaining time.
  SLICE = .01  # secs
  def ExecSimulation(self):
    et = QtCore.QTime()
    et.start()
    #sys.stdout.write('.')
    sRate = 60**self.simRateLimit.value() * self.SLICE
    sStart = self._simModel.Scheduler().Now()
    #print "sRate = %s, sStart = %s" % (sRate, sStart)
    while self._simModel.Scheduler().Now()-sStart < sRate and et.elapsed() < self.SLICE*1000:
      self.cyclecount += self._simModel.Scheduler().ExecEventsFor(sRate, 100)
    #elapsed = et.elapsed() / 1000.0

  def frameUpdate(self):
    self.framecount += 1
    self._scene.UpdateFromModel()  # calls update on each TileGraphicsItem that needs repainting
    #self.hexView.updateScene(list_of_QRectF)
    #self.hexView.viewport().update()  # seems to repaint entire view

  def setTimers(self):
    if self.actionSimRunning.isChecked():
      #sRate = 60**self.simRateLimit.value()
      #self.simTimer.start(1000/sRate)
      self.simTimer.start(self.SLICE*1000)
      self.frameTimer.start(1000/self.frameRateLimit.value())
      #self.hexView.setViewportUpdateMode(QtGui.QGraphicsView.NoViewportUpdate)
    else:
      self.simTimer.stop()
      self.frameTimer.stop()
      #self.hexView.viewport().update()

  def perfUpdate(self):
    now = time.time()
    dt = now - self.perfClockStamp
    if dt > 0:
      self.performanceStatus.setText("{0: >9} sim clock;  {1: >7.1f} events/sec;  {2: >5.1f} FPS;  {3: >2} jobs".format
        ( self._simModel.Scheduler().Now()
        , (self.cyclecount-self.perfCycleStamp)/dt
        , (self.framecount-self.perfFrameStamp)/dt
        , self._simModel.JobCount()
        )
      )
    self.perfClockStamp = now
    self.perfCycleStamp = self.cyclecount
    self.perfFrameStamp = self.framecount

  @QtCore.pyqtSlot(float)
  def on_action_simRateLimit_valueChanged(self, x):
    print "on_action_simRateLimit_valueChanged(%d)" % x
    self.setTimers()

  @QtCore.pyqtSlot(int)
  def on_action_frameRateLimit_valueChanged(self, i):
    print "on_action_frameRateLimit_valueChanged(%d)" % i
    self.setTimers()

  # pyqtSlot(*type(s), name="on_%(QObject_name)_%(signal)")
  @QtCore.pyqtSlot(bool)
  def on_actionSimRunning_toggled(self, newValue):
    self.setTimers()

  @QtCore.pyqtSlot(bool)
  def on_actionFullscreen_toggled(self, newValue):
    self.setWindowState(self.windowState() ^ QtCore.Qt.WindowFullScreen)
    #self.menubar.setVisible(not newValue) # hotkeys go away along with menubar visibility
    #if newValue:
    #  self.showFullScreen()
    #else:
    #  self.showNormal()

  @QtCore.pyqtSlot()
  def on_actionAbout_triggered(self):
    QtGui.QMessageBox.about(self, app_title, app_about_html)

def main():
  #print sys.argv
  # Note that executing with "-graphicssystem raster" can make it go faster,
  #   "-graphicssystem opengl" even faster still.
  #   default is "-graphicssystem native"
  # Translates into:
  #   QtGui.QApplication.setGraphicsSystem("raster") # must be done before constructing QApplication
  global_app = QtGui.QApplication(sys.argv)
  if '-h' in sys.argv or '--help' in sys.argv:
    print sys.argv
    print "usage: $0 -graphicssystem (raster|opengl)"
    return 0
  if '--fail' in sys.argv:
    return 7
  if '--unittest' in sys.argv:
    sys.argv.remove('--unittest')
    unittest.main()
    return 0
  i = QtGui.QIcon("resources/starburst.svg")
  # svgr = QSvgRenderer("starburst.svg")
  # pixm = QPixMap(svgr.defaultSize())
  # painter = QPainter(pixm)
  # svgr.render(painter)
  global_app.setWindowIcon(i)
  mainWnd = StarshipMainWindow()
  #mainWnd.setWindowIcon(i)
  mainWnd.show()
  #mainWnd.showMaximized()
  rc = global_app.exec_()

  # WORKAROUND: PyQt 4.7.2 frequently segfaults if the QApplication instance
  #   is garbage collected too soon (e.g., if it is not a global variable on
  #   exiting).
  global persistent_app
  persistent_app = global_app

  return rc

if __name__=='__main__': sys.exit(main())

