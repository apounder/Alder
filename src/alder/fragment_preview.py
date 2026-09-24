"""Small, clickable chemical depiction with an explicit joining atom."""
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget


class FragmentPreview(QWidget):
    atomClicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(160)
        self.setMinimumWidth(260)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName('Fragment preview. Choose the joining atom using the dropdown or click its numbered label.')
        self.renderer = QSvgRenderer(self)
        self.points, self.root = [], 0

    def set_fragment(self, fragment):
        self.points = fragment['points']
        self.root = fragment['root']
        self.renderer.load(fragment['svg'].encode())
        self.update()

    def set_root(self, index):
        self.root = index
        self.update()

    def drawing_rect(self):
        scale = min(self.width()/320, self.height()/160)
        return QRectF((self.width()-320*scale)/2, (self.height()-160*scale)/2, 320*scale, 160*scale)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.drawing_rect()
        self.renderer.render(painter, rect)
        if self.points:
            x, y = self.points[self.root]
            scale = rect.width()/320
            painter.setPen(QPen(QColor('#14793b'), 2.5))
            painter.setBrush(QColor(20, 121, 59, 24))
            painter.drawEllipse(QRectF(rect.x()+(x-16)*scale, rect.y()+(y-16)*scale, 32*scale, 32*scale))

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self.points:
            return
        rect = self.drawing_rect()
        x, y = (event.position().x()-rect.x())*320/rect.width(), (event.position().y()-rect.y())*160/rect.height()
        index = min(range(len(self.points)), key=lambda i: (x-self.points[i][0])**2+(y-self.points[i][1])**2)
        if (x-self.points[index][0])**2+(y-self.points[index][1])**2 < 24**2:
            self.atomClicked.emit(index)
