
from PyQt5 import QtCore, QtGui, QtWidgets

class DockContentsWidget(QtWidgets.QWidget):
  '''A QWidget that returns a sizeHint despite the lack of a layout for it.

  QDockWidget is so busy being a sometimes-docked-sometimes-floating window
  that it depends on the QWidget inside for sizing hints.  But QWidget won't
  return sizing hints unless it's in a QLayout.  But you can't set a QLayout
  on a QDockWidget!  Qt Designer automatically adds a QWidget inside every
  QDockWidget, named dockWidgetContents, and puts any child widgets inside
  that, apparently as part of a "solution" to this problem.  Seemingly the
  only way to get the dock to size right is to customize this top
  "dockWidgetContents" inside each QDockWidget.  But wait, there's more!
  `pyuic4` adds *ANOTHER* QWidget between the "dockWidgetContents" and anything
  inside!!!  This is cleverly named "widget", "widget1", etc., with no
  visibility, access, or control from Qt Designer.  (And an undocumented
  potential name clash to boot.)

  Solution: In Qt Designer, promote the QWidget inside a QDockWidget to this
  DockContentsWidget class.  This provides the sizeHint for a docked
  QDockWidget to be an appropriate size.

  TODO: A free-floating QDockWidget still does not seem to take the hint.
  '''
  def __init__(self, *posargs, **kwargs):
    super(DockContentsWidget,self).__init__(*posargs, **kwargs)
  def sizeHint(self):
    y = self.layout()
    if not y is None:
      return self.layout().sizeHint()
    kids = self.children()
    if len(kids) == 1:
      return kids[0].sizeHint()
    print "DockContentsWidget.sizeHint(): refusing to pick from among multiple children"
    return QtCore.QSize(-1,-1)
