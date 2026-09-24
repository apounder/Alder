"""Native calculation inputs stay light even when the initial system palette is dark."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtGui import QColor,QPalette
from PySide6.QtWidgets import QApplication,QCheckBox,QDialog,QLineEdit,QPlainTextEdit,QTextEdit,QVBoxLayout
from alder.ui import configure_app

app=QApplication.instance() or QApplication([])
dark=QPalette();dark.setColor(QPalette.ColorRole.Base,QColor('#101010'));dark.setColor(QPalette.ColorRole.Text,QColor('#eee'))
app.setPalette(dark);configure_app(app)
dialog=QDialog();layout=QVBoxLayout(dialog)
for cls in (QLineEdit,QPlainTextEdit,QTextEdit):
    for state in ('editable','read only','disabled'):
        w=cls();w.setText(state+' calculation settings') if hasattr(w,'setText') else w.setPlainText(state+' calculation settings')
        if state=='read only':w.setReadOnly(True)
        if state=='disabled':w.setEnabled(False)
        layout.addWidget(w);w.ensurePolished()
        assert w.palette().color(QPalette.ColorRole.Base).lightness()>220
        assert w.palette().color(QPalette.ColorRole.Text).lightness()<130
for checked,enabled in ((False,True),(True,True),(True,False)):
    w=QCheckBox('Calculation option');w.setChecked(checked);w.setEnabled(enabled);layout.addWidget(w)
dialog.resize(550,820);dialog.show();app.processEvents()
if len(sys.argv)>1:dialog.grab().save(sys.argv[1])
print('Light text fields, disabled/read-only values, and checkbox states passed.')
dialog.close()
