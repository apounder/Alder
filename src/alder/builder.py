"""Native Studio controls for the shared, offline molecule editor engine."""
import json
from pathlib import Path
import re

from PySide6.QtCore import QObject, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGridLayout,
    QHBoxLayout, QLineEdit, QPushButton, QSlider, QVBoxLayout, QWidget, QMenu, QWidgetAction, QToolButton, QScrollArea,
)
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from .data import ELEMENTS
from .render_export import ExportBridge
from .sketch import SketchMixin
from .fragment_preview import FragmentPreview
from .ui import inspector_page, label

SAMPLES = {
    "Aspirin": "CC(=O)Oc1ccccc1C(=O)O", "Caffeine": "CN1C=NC2=C1C(=O)N(C)C(=O)N2C",
    "Benzene": "c1ccccc1", "Ibuprofen": "CC(C)Cc1ccc(C(C)C(=O)O)cc1",
}
HINTS = {
    "select": "Click up to four atoms to measure. Shift-click to select a larger group.",
    "add": "Click an atom to replace it with the selected element; hydrogens adjust automatically. Click empty space to place an atom, or a bond to change its order. Drag to rotate.",
    "move": "Drag an atom to move it and the active selection in the view plane.",
    "delete": "Click an atom or bond to erase it. Deleting a hydrogen leaves an open valence.",
    "bond": "Click an atom to attach a new atom with the selected bond order. Drag to grow a bond or connect atoms. Click a bond to change its order. Choosing an element returns to Replace atom.",
    "rect": "Drag a rectangle to select atoms. Shift adds to the selection; double-click clears it.",
    "lasso": "Draw around atoms to select them. Shift adds to the selection; double-click clears it.",
    "rotate": "Drag to rotate the selected atoms about their center. Undo restores the previous geometry.",
    "fragment": "Choose a fragment and its green joining atom, then click your structure. Replace shares that atom; Attach adds a bond. Click empty space to place separately. Esc exits.",
}


class BuilderBridge(ExportBridge):
    command = Signal(str)
    initialized = Signal()
    state = Signal(str)
    structure = Signal(str)
    message = Signal(str, str)
    error = Signal(str)
    text = Signal(str)
    image = Signal(str)

    @Slot()
    def ready(self):
        self.initialized.emit()

    @Slot(str)
    def stateChanged(self, value):
        self.state.emit(value)

    @Slot(str)
    def structureChanged(self, value):
        self.structure.emit(value)

    @Slot(str, str)
    def notice(self, text, kind):
        self.message.emit(text, kind)

    @Slot(str)
    def reportError(self, message):
        self.error.emit(message)

    @Slot(str)
    def imageReady(self, data):
        self.image.emit(data)

    @Slot(str)
    def textReady(self, text):
        self.text.emit(text)


class BuilderMixin(SketchMixin):
    def init_builder(self):
        self.builder_ready = False
        self.builder_active = False
        self.builder_editing = False
        self.builder_model = {"name": "Untitled molecule", "atoms": [], "bonds": []}
        self.builder_state = {}
        self.builder_pending = []
        self.builder_export_path = None
        self.builder_actions = []

    def install_builder(self, assets):
        root_side = inspector_page(self.inspector, "Build")
        root_side.setContentsMargins(14, 16, 14, 16)
        self.builder_3d_panel = QWidget()
        root_side.addWidget(self.builder_3d_panel)
        side = QVBoxLayout(self.builder_3d_panel)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(8)
        self.build_tab = self.inspector.count() - 1
        side.addWidget(label("3D structure editor", "sectionTitle"))
        side.addWidget(label("Build a new structure or edit a copy of a calculated geometry.", "muted"))
        row = QHBoxLayout()
        self.builder_new = QPushButton("New molecule")
        self.builder_new.clicked.connect(lambda: self.builder_command(type="new"))
        row.addWidget(self.builder_new)
        self.builder_copy = QPushButton("Edit geometry")
        self.builder_copy.setToolTip("Copy the selected calculation step into an editable draft")
        self.builder_copy.clicked.connect(self.copy_selected_geometry)
        self.builder_copy.setEnabled(False)
        row.addWidget(self.builder_copy)
        side.addLayout(row)
        side.addWidget(label("Select tool", "sectionTitle"))
        self.builder_tools = {}
        tools = QGridLayout()
        for i, (key, title) in enumerate(zip(HINTS, ("Default", "Replace atom", "Move selected", "Erase", "Attach atom", "Rect. select", "Lasso select", "Rotate selected", "Rings / groups"))):
            button = QPushButton(title)
            button.setCheckable(True)
            button.setToolTip(f"{title} · {i + 1}")
            button.clicked.connect(lambda _checked, button=button: button.setChecked(True))
            button.clicked.connect(lambda checked=False, key=key: self.choose_builder_tool(key))
            button.setObjectName("builderTool")
            tools.addWidget(button, i // 2, i % 2, 1, 2 if key=='fragment' else 1)
            self.builder_tools[key] = button
        side.addLayout(tools)
        tool_side = side
        self.builder_atom_options = QWidget()
        side = QVBoxLayout(self.builder_atom_options)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(8)
        self.builder_order = QComboBox()
        for name, order in (("Single bond", 1), ("Double bond", 2), ("Triple bond", 3), ("Dative arrow", "dative"), ("TS contact", "ts")):
            self.builder_order.addItem(name, order)
        self.builder_order.setAccessibleName("Bond order")
        self.builder_order.setToolTip("Ordinary bonds: click a bond to change it. Dative/TS: click two atoms; donor first for dative.")
        self.builder_order.currentIndexChanged.connect(lambda: self.builder_command(type="bondOrder", order=self.builder_order.currentData()))
        side.addWidget(self.builder_order)
        self.builder_auto_h = QCheckBox("Adjust hydrogens when editing")
        self.builder_auto_h.setChecked(True)
        self.builder_auto_h.setToolTip("Neutral main-group valences; charged atoms and metals are left for manual editing")
        self.builder_auto_h.toggled.connect(lambda value: self.builder_command(type="autoHydrogens", enabled=value))
        tool_side.addWidget(self.builder_auto_h)
        side.addWidget(label("Element", "small"))
        side.addWidget(label("Choose an element, then click an atom to replace it.", "muted"))
        palette = QGridLayout()
        self.builder_elements = {}
        for i, el in enumerate(("H", "C", "N", "O", "F", "S", "P", "Cl", "Br", "I")):
            button = QPushButton(el)
            button.setCheckable(True)
            button.setAccessibleName(f"Choose element {el}")
            button.clicked.connect(lambda _checked, button=button: button.setChecked(True))
            button.clicked.connect(lambda checked=False, el=el: self.builder_command(type="element", element=el))
            palette.addWidget(button, i // 5, i % 5)
            self.builder_elements[el] = button
        side.addLayout(palette)
        self.builder_more = QComboBox()
        self.builder_more.addItem("Full periodic table…", None)
        for el in ELEMENTS[1:]:
            if el:
                self.builder_more.addItem(el, el)
        self.builder_more.activated.connect(self.builder_element_changed)
        side.addWidget(self.builder_more)
        self.builder_apply = QPushButton("Apply element to selection")
        self.builder_apply.clicked.connect(lambda: self.builder_command(type="apply"))
        side.addWidget(self.builder_apply)
        side = tool_side
        side.addWidget(self.builder_atom_options)
        self.fragment_library = json.loads((assets / 'fragments.json').read_text(encoding='utf-8'))
        self.builder_fragment_options = QWidget()
        fragment_side = QVBoxLayout(self.builder_fragment_options)
        fragment_side.setContentsMargins(0, 0, 0, 0)
        fragment_side.setSpacing(6)
        fragment_side.addWidget(label("Rings and functional groups", "sectionTitle"))
        self.builder_fragment = QComboBox()
        for entry in self.fragment_library:
            self.builder_fragment.addItem(f"{entry['category']} · {entry['name']}", entry['name'])
        self.builder_fragment.setAccessibleName("Fragment to insert")
        self.builder_fragment.currentIndexChanged.connect(self.builder_fragment_changed)
        fragment_side.addWidget(self.builder_fragment)
        self.builder_fragment_preview = FragmentPreview()
        fragment_side.addWidget(self.builder_fragment_preview)
        self.builder_fragment_root = QComboBox()
        self.builder_fragment_root.setAccessibleName("Joining atom in the fragment")
        self.builder_fragment_root.currentIndexChanged.connect(self.builder_fragment_root_changed)
        self.builder_fragment_preview.atomClicked.connect(self.builder_fragment_root.setCurrentIndex)
        fragment_side.addWidget(self.builder_fragment_root)
        self.builder_fragment_caption = label('', 'muted')
        fragment_side.addWidget(self.builder_fragment_caption)
        self.builder_fragment_mode = QComboBox()
        self.builder_fragment_mode.addItem('Replace atom · share junction', 'replace')
        self.builder_fragment_mode.addItem('Attach group · add a bond', 'attach')
        self.builder_fragment_mode.setAccessibleName('Fragment placement mode')
        self.builder_fragment_mode.currentIndexChanged.connect(lambda: self.choose_fragment())
        fragment_side.addWidget(self.builder_fragment_mode)
        row = QHBoxLayout()
        self.builder_insert = QPushButton('Replace selected')
        self.builder_insert.clicked.connect(lambda: self.choose_fragment('selected'))
        row.addWidget(self.builder_insert)
        self.builder_place_fragment = QPushButton('Place separately')
        self.builder_place_fragment.clicked.connect(lambda: self.choose_fragment('separate'))
        row.addWidget(self.builder_place_fragment)
        fragment_side.addLayout(row)
        fragment_side.addWidget(label('Pick any numbered atom as the junction. Attach adds a bond and replaces hydrogens as needed. Replace shares the junction atom (for example, to make a spiro ring).', 'muted'))
        side.addWidget(self.builder_fragment_options)
        self.builder_fragment_changed(arm=False)
        side.addWidget(label("Selected atoms", "sectionTitle"))
        row = QHBoxLayout()
        for title, command in (("Clear selection", "escape"), ("Delete selected", "delete")):
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, command=command: self.builder_command(type=command))
            row.addWidget(button)
            self.builder_actions.append(button)
        side.addLayout(row)
        row = QHBoxLayout()
        self.builder_undo = QPushButton("Undo")
        self.builder_redo = QPushButton("Redo")
        self.builder_tidy = QPushButton("Tidy geometry")
        for button, command in ((self.builder_undo, "undo"), (self.builder_redo, "redo"), (self.builder_tidy, "tidy")):
            button.clicked.connect(lambda checked=False, command=command: self.builder_command(type=command))
            row.addWidget(button)
        side.addLayout(row)
        self.builder_hint = label(HINTS["select"], "muted")
        side.addWidget(self.builder_hint)
        self.builder_measure = label("Select 2 / 3 / 4 atoms for distance / angle / dihedral.", "small")
        self.builder_measure.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        side.addWidget(self.builder_measure)
        self.builder_stats = label("No atoms yet", "small")
        side.addWidget(self.builder_stats)
        self.builder_notice = label("", "notice")
        self.builder_notice.hide()
        side.addWidget(self.builder_notice)

        self.builder_preset = QComboBox()
        self.builder_preset.addItems([self.preset.itemText(i) for i in range(self.preset.count())])
        self.builder_preset.setCurrentText(self.preset.currentText())
        self.builder_preset.currentTextChanged.connect(self.preset.setCurrentText)
        self.preset.currentTextChanged.connect(self.builder_preset.setCurrentText)
        self.builder_preset.hide()
        self.builder_hydrogens = QCheckBox("Show hydrogens")
        self.builder_hydrogens.setChecked(True)
        self.builder_labels = QCheckBox("Element labels")
        self.builder_spin = QCheckBox("Auto-rotate")
        for control, key in ((self.builder_hydrogens, "hydrogens"), (self.builder_labels, "labels"), (self.builder_spin, "spin")):
            control.toggled.connect(lambda value, key=key: self.send(type="style", **{key: value}))
            side.addWidget(control)
        self.builder_size = QSlider(Qt.Orientation.Horizontal)
        self.builder_size.setRange(50, 180)
        self.builder_size.setValue(100)
        self.builder_size.setAccessibleName("Builder atom size")
        self.builder_size.valueChanged.connect(lambda value: self.send(type="style", size=value / 100))
        side.addWidget(self.builder_size)
        self.builder_figure = QPushButton("Preview figure in Studio")
        self.builder_figure.setObjectName("primary")
        self.builder_figure.clicked.connect(self.preview_builder_figure)
        side.addWidget(self.builder_figure)
        row = QHBoxLayout()
        for fmt in ("xyz", "mol", "pdb"):
            button = QPushButton(fmt.upper())
            button.setToolTip(f"Export draft as {fmt.upper()}")
            button.clicked.connect(lambda checked=False, fmt=fmt: self.export_builder(fmt))
            row.addWidget(button)
            self.builder_actions.append(button)
        side.addLayout(row)
        side.addWidget(label("XYZ carries no bond orders; use MOL to preserve them. Figure preview uses Studio's presets and PNG/TIFF export.", "muted"))
        self.builder_add_h = QPushButton("Complete hydrogens")
        self.builder_add_h.clicked.connect(lambda: self.builder_command(type="hydrogens"))
        side.addWidget(self.builder_add_h)
        smiles_toggle = QPushButton("SMILES and sample molecules ▸")
        smiles_toggle.setCheckable(True)
        side.addWidget(smiles_toggle)
        smiles_box = QWidget()
        smiles_layout = QVBoxLayout(smiles_box)
        smiles_layout.setContentsMargins(0, 0, 0, 0)
        self.builder_smiles = QLineEdit()
        self.builder_smiles.setPlaceholderText("Paste SMILES, e.g. CCO")
        self.builder_smiles.setAccessibleName("SMILES string")
        self.builder_smiles.returnPressed.connect(self.build_smiles)
        smiles_layout.addWidget(self.builder_smiles)
        self.builder_generate = QPushButton("Build from SMILES")
        self.builder_generate.setObjectName("primary")
        self.builder_generate.clicked.connect(self.build_smiles)
        smiles_layout.addWidget(self.builder_generate)
        samples = QGridLayout()
        for i, name in enumerate(SAMPLES):
            button = QPushButton(name)
            button.clicked.connect(lambda checked=False, name=name: self.build_smiles(name))
            samples.addWidget(button, i // 2, i % 2)
            self.builder_actions.append(button)
        smiles_layout.addLayout(samples)
        smiles_box.hide()
        smiles_toggle.toggled.connect(smiles_box.setVisible)
        smiles_toggle.toggled.connect(lambda opened: smiles_toggle.setText("SMILES and sample molecules ▾" if opened else "SMILES and sample molecules ▸"))
        side.addWidget(smiles_box)
        side.addStretch()

        self.builder_web = QWebEngineView()
        self.builder_web.setMinimumHeight(280)
        self.builder_web.setAcceptDrops(True)
        self.builder_web.installEventFilter(self)
        self.builder_web.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        self.builder_web.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self.builder_bridge = BuilderBridge(self)
        self.builder_bridge.initialized.connect(self.builder_initialized)
        self.builder_bridge.state.connect(self.builder_state_changed)
        self.builder_bridge.structure.connect(self.builder_structure_changed)
        self.builder_bridge.message.connect(self.builder_message)
        self.builder_bridge.error.connect(self.render_error)
        self.builder_bridge.text.connect(self.save_builder_text)
        self.builder_bridge.image.connect(self.save_image)
        self.connect_export_bridge(self.builder_bridge)
        self.builder_channel = QWebChannel(self.builder_web.page())
        self.builder_channel.registerObject("builder", self.builder_bridge)
        self.builder_web.page().setWebChannel(self.builder_channel)
        self.viewer_stack.addWidget(self.builder_web)
        self.builder_web.load(QUrl.fromLocalFile(str(assets / "builder.html")))
        self.inspector.currentChanged.connect(self.studio_tab_changed)
        for key, tool in {"1": "select", "V": "select", "2": "add", "A": "add", "3": "move", "M": "move", "4": "delete", "D": "delete", "5": "bond", "B": "bond", "6": "rect", "7": "lasso", "8": "rotate", "R": "rotate", "9": "fragment", "G": "fragment"}.items():
            shortcut = QShortcut(QKeySequence(key), self.builder_web)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(lambda tool=tool: self.choose_builder_tool(tool))
        for key, command in (("Escape", "escape"), ("Delete", "delete"), ("Ctrl+Z", "undo"), ("Ctrl+Shift+Z", "redo")):
            shortcut = QShortcut(QKeySequence(key), self.builder_web)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(lambda command=command: self.builder_command(type=command))
        self.install_view_options()
        self.install_sketch(assets, root_side)
        self.builder_state_changed('{}')

    def install_view_options(self):
        # One set of controls for Calculation, Figure, and Build.
        self.view_options = QToolButton()
        self.view_options.setText("View ▾")
        self.view_options.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.view_options)
        panel = QWidget()
        panel.setMinimumWidth(300)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        layout.addWidget(label("Shared 3D appearance", "sectionTitle"))
        for widget in (self.preset, self.preset_note, self.outlines, self.ambient_occlusion, self.orthographic,
                       self.builder_hydrogens, self.builder_labels, self.builder_spin):
            layout.addWidget(widget)
        self.preset_note.setMaximumWidth(290)
        layout.addWidget(label("Atom size", "small"))
        layout.addWidget(self.builder_size)
        self.builder_size.setAccessibleName("Atom size in all 3D views")
        self.view_background = QComboBox()
        for title, value in (("Light background", "light"), ("Dark background", "dark"), ("Transparent background", "transparent")):
            self.view_background.addItem(title, value)
        self.view_background.currentIndexChanged.connect(lambda: self.send(type="style", background=self.view_background.currentData()))
        layout.addWidget(self.view_background)
        self.fog_enabled = QCheckBox('Fog / depth cue')
        self.fog_enabled.toggled.connect(self.fog_changed)
        layout.addWidget(self.fog_enabled)
        self.fog_strength = QSlider(Qt.Orientation.Horizontal)
        self.fog_strength.setRange(0, 100)
        self.fog_strength.setValue(35)
        self.fog_strength.setAccessibleName('Fog strength')
        self.fog_strength.valueChanged.connect(self.fog_changed)
        layout.addWidget(label('Fog strength', 'small'))
        layout.addWidget(self.fog_strength)
        self.fog_depth = QSlider(Qt.Orientation.Horizontal)
        self.fog_depth.setRange(-100, 200)
        self.fog_depth.setValue(0)
        self.fog_depth.setAccessibleName('Fog start depth')
        self.fog_depth.valueChanged.connect(self.fog_changed)
        layout.addWidget(label('Fog start depth', 'small'))
        layout.addWidget(self.fog_depth)
        self.depth_cue = QPushButton('Depth cue')
        self.depth_cue.setCheckable(True)
        self.depth_cue.setToolTip('Enable fog, then click an atom to set where fading starts. Escape cancels picking.')
        self.depth_cue.clicked.connect(self.choose_depth_cue)
        self.viewbar.insertWidget(self.viewbar.count()-1, self.depth_cue)
        layout.addWidget(label('Drag to rotate · Scroll to zoom. With fog on, right-drag empty space to move the fog; Shift + right-drag pans. With fog off, right-drag pans.', 'muted'))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(panel)
        scroll.setFixedSize(340, min(panel.sizeHint().height()+4, max(300, self.screen().availableGeometry().height()-100)))
        action = QWidgetAction(menu)
        action.setDefaultWidget(scroll)
        menu.addAction(action)
        self.view_options.setMenu(menu)
        self.viewbar.insertWidget(self.viewbar.count()-1, self.view_options)

    def fog_options(self):
        return dict(enabled=self.fog_enabled.isChecked(), strength=self.fog_strength.value()/100,
                    offset=self.fog_depth.value()/100)

    def fog_changed(self, state=None):
        if isinstance(state, str):
            data = json.loads(state)
            for control, value in ((self.fog_enabled, bool(data['enabled'])),
                                   (self.fog_strength, round(data['strength']*100)),
                                   (self.fog_depth, round(data['offset']*100))):
                control.blockSignals(True)
                if isinstance(control, QCheckBox):
                    control.setChecked(value)
                else:
                    control.setValue(value)
                control.blockSignals(False)
            self.depth_cue.setChecked(bool(data.get('armed')))
        if not self.fog_enabled.isChecked():
            self.depth_cue.setChecked(False)
        self.send(type='fog', **self.fog_options())

    def choose_depth_cue(self, checked):
        if checked:
            self.fog_enabled.setChecked(True)
            if self.fog_strength.value() == 0:
                self.fog_strength.setValue(35)
            self.statusBar().showMessage('Click an atom to start the depth cue at its position. Escape cancels.')
        self.send(type='fogPick', enabled=checked)

    def builder_initialized(self):
        self.builder_ready = True
        if self.builder_web.focusProxy():
            self.builder_web.focusProxy().setAcceptDrops(True)
            self.builder_web.focusProxy().installEventFilter(self)
        self.builder_command(type="style", style=self.style.currentText())
        self.builder_command(type="fog", **self.fog_options())
        self.builder_command(type="appearance", preset=self.preset.currentText(), outline=self.outlines.isChecked(), ao=self.ambient_occlusion.isChecked(), orthographic=self.orthographic.isChecked())
        self.builder_command(type="figureAddons", **self.figure_addon_options())
        pending, self.builder_pending = self.builder_pending, []
        for payload in pending:
            self.builder_command(**payload)
        self.builder_state_changed(json.dumps(self.builder_state))

    def builder_command(self, **payload):
        if self.builder_ready:
            self.builder_bridge.command.emit(json.dumps(payload, allow_nan=False))
        else:
            self.builder_pending.append(payload)

    def builder_message(self, text, kind="info"):
        self.builder_notice.setText(text)
        self.builder_notice.setVisible(bool(text))
        self.statusBar().showMessage(text)
        if kind == "error":
            self.builder_export_path = None

    def builder_state_changed(self, text):
        self.builder_state = state = json.loads(text)
        enabled = self.builder_ready and not state.get("busy", False)
        atoms = state.get("atoms", 0)
        for control in [self.builder_new, self.builder_generate, self.builder_smiles, self.builder_more,
                        self.builder_order, self.builder_auto_h, self.builder_fragment, self.builder_fragment_root,
                        self.builder_fragment_mode, self.builder_fragment_preview, self.builder_place_fragment, self.builder_add_h,
                        *self.builder_tools.values(), *self.builder_elements.values(), *self.builder_actions]:
            control.setEnabled(enabled)
        self.builder_copy.setEnabled(enabled and self.calculation is not None and not self.busy)
        self.builder_apply.setEnabled(enabled and bool(state.get("selection")))
        self.builder_insert.setEnabled(enabled and state.get('selection')==1)
        self.builder_insert.setText('Replace selected' if self.builder_fragment_mode.currentData()=='replace' else 'Attach to selected')
        self.builder_undo.setEnabled(enabled and bool(state.get("undo")))
        self.builder_redo.setEnabled(enabled and bool(state.get("redo")))
        self.builder_tidy.setEnabled(enabled and bool(atoms))
        self.builder_figure.setEnabled(enabled and bool(atoms) and self.renderer_ready)
        tool = state.get("tool", "select")
        for name, button in self.builder_tools.items():
            button.setChecked(name == tool)
        for el, button in self.builder_elements.items():
            button.setChecked(el == state.get("element", "C"))
        self.builder_more.setCurrentIndex(self.builder_more.findData(state.get("element", "C")))
        self.builder_auto_h.blockSignals(True)
        self.builder_auto_h.setChecked(state.get("autoHydrogens", True))
        self.builder_auto_h.blockSignals(False)
        self.builder_order.blockSignals(True)
        self.builder_order.setCurrentIndex(self.builder_order.findData(state.get("bondKind") or state.get("bondOrder", 1)))
        self.builder_order.blockSignals(False)
        self.builder_apply.setText(f"Apply {state.get('element', 'C')} to selection")
        self.builder_spin.setEnabled(not self.builder_editing or (enabled and tool == "select"))
        if self.builder_editing and not state.get("spin", False) and self.builder_spin.isChecked():
            self.builder_spin.setChecked(False)
        self.builder_atom_options.setVisible(tool!='fragment')
        self.builder_fragment_options.setVisible(tool=='fragment')
        hint = HINTS.get(tool, HINTS["select"])
        if tool == "bond" and state.get("bondKind"):
            hint = ("Click the donor atom, then the acceptor atom to add a dative arrow."
                    if state["bondKind"] == "dative" else "Click two atoms to add a dashed TS contact.")
            hint += " Geometry and hydrogens are preserved. Undo restores the previous bond."
        self.builder_hint.setText(hint)
        self.builder_measure.setText(state.get("measurement") or "Select 2 / 3 / 4 atoms for distance / angle / dihedral.")
        self.builder_stats.setText(f"{state.get('formula', '')} · {atoms} atoms · {state.get('bonds', 0)} bonds")
        if self.builder_active:
            self.filename.setText(f"Draft · {state.get('name', 'Untitled molecule')}")
            self.export_button.setEnabled(enabled and bool(atoms) and self.renderer_ready and not self.exporting)
        self.update_builder_mode_ui()

    def builder_structure_changed(self, text):
        self.builder_model = json.loads(text)

    def builder_element_changed(self, index):
        el = self.builder_more.itemData(index)
        if el:
            self.builder_command(type="element", element=el)

    def choose_builder_tool(self, tool):
        if tool=='fragment':
            self.choose_fragment()
        else:
            self.builder_command(type='tool', tool=tool)

    def builder_fragment_changed(self, _index=None, arm=True):
        fragment = self.fragment_library[self.builder_fragment.currentIndex()]
        self.builder_fragment_preview.set_fragment(fragment)
        self.builder_fragment_root.blockSignals(True)
        self.builder_fragment_root.clear()
        for i in range(len(fragment['points'])):
            atom = fragment['model']['atoms'][i]
            bonds = [b for b in fragment['model']['bonds'] if i in (b['a'], b['b'])]
            carbonyl = atom['el']=='C' and any(b['order']==2 and fragment['model']['atoms'][b['b'] if b['a']==i else b['a']]['el']=='O' for b in bonds)
            self.builder_fragment_root.addItem(f"Join at {atom['el']}{i+1}" + (' · carbonyl carbon' if carbonyl else ''), i)
        self.builder_fragment_root.setCurrentIndex(fragment['root'])
        self.builder_fragment_root.blockSignals(False)
        self.builder_fragment_root_changed(fragment['root'], arm=arm)

    def builder_fragment_root_changed(self, index, arm=True):
        if index<0:return
        self.builder_fragment_preview.set_root(index)
        model = self.fragment_library[self.builder_fragment.currentIndex()]['model']
        available = model['atoms'][index].get('radical', 0) + sum(b['order'] for b in model['bonds']
            if index in (b['a'], b['b']) and model['atoms'][b['b'] if b['a']==index else b['a']]['el']=='H')
        self.builder_fragment_caption.setText(
            f'Green junction · {available} replaceable H / open valence' + ('' if available==1 else 's') + '.'
            if available else 'This atom has no replaceable H or open valence. Choose another joining atom to attach.')
        if arm:self.choose_fragment()

    def choose_fragment(self, action='choose'):
        fragment = self.fragment_library[self.builder_fragment.currentIndex()]
        self.builder_command(type='fragment', action=action, fragment=dict(name=fragment['name'], model=fragment['model'],
            root=self.builder_fragment_root.currentData(), mode=self.builder_fragment_mode.currentData()))

    def build_smiles(self, name=None):
        if isinstance(name, str) and name in SAMPLES:
            self.builder_smiles.setText(SAMPLES[name])
        else:
            name = "Built molecule"
        self.builder_command(type="smiles", smiles=self.builder_smiles.text().strip(), name=name)

    def copy_selected_geometry(self):
        if not self.calculation or self.busy:
            return
        self.send(type="copyToBuilder", xyz=self.calculation.xyz(self.step, self.display_coords),
                  annotationKey=str(id(self.calculation)), name=f"{self.calculation.name} · geometry {self.step + 1}")

    def receive_geometry_copy(self, text):
        model = json.loads(text)
        self.inspector.setCurrentIndex(self.build_tab)
        self.set_builder_mode('3d')
        self.builder_command(type="restore", model=model)
        self.statusBar().showMessage('Copied geometry and edited bonds into Build. Export MOL to save the bond styles.')

    def studio_tab_changed(self, index):
        if self.depth_cue.isChecked():
            self.depth_cue.setChecked(False)
            self.send(type='fogPick', enabled=False)
        if index == getattr(self, 'compare_tab', -1):
            self.show_comparison()
            self.update_builder_mode_ui()
            return
        was_comparison = getattr(self, 'comparison_active', False)
        if index != 2:
            self.comparison_active = False
        if index == 1:
            self.stop_vibration()
        if index == self.build_tab:
            self.stop_vibration(restore=False)
            self.builder_command(type="readonly", enabled=False)
            self.builder_active = self.builder_editing = True
            self.play.setChecked(False)
            self.viewer_stack.setCurrentWidget(self.builder_web)
            self.timeline_widget.hide()
            self.results.hide()
            if self.builder_mode == "2d":
                self.viewer_stack.setCurrentWidget(self.sketch_web)
            self.builder_command(type="visibility", visible=self.builder_mode == "3d")
            self.builder_state_changed(json.dumps(self.builder_state))
        elif index == 2 and self.builder_active:
            self.show_builder_figure()
        elif index in (0, 1):
            was_draft = self.builder_active
            self.builder_active = self.builder_editing = False
            self.viewer_stack.setCurrentWidget(self.web)
            self.timeline_widget.show()
            self.results.show()
            self.builder_command(type="visibility", visible=False)
            if self.calculation:
                self.filename.setText(self.calculation.name)
                if was_draft or was_comparison:
                    if was_comparison:
                        entry = next((d for d in self.documents if d['calculation'] is self.calculation), None)
                        if entry is not None:
                            self.step = entry['step']
                            self.slider.blockSignals(True)
                            self.slider.setValue(self.step)
                            self.slider.blockSignals(False)
                    self.select_step(self.step, fit=True)
                    self.refresh_surface(reload=True)
            else:
                self.filename.setText("Untitled calculation")
                self.send(type="geometry", xyz="0\nNo calculation loaded\n", fit=True, surface=False)
            self.export_button.setEnabled(bool(self.calculation) and self.renderer_ready and not self.exporting)
        self.send(type="visibility", visible=not self.builder_active)
        self.builder_spin.setEnabled(not self.builder_editing or self.builder_state.get("tool")=="select")
        self.update_builder_mode_ui()

    def preview_builder_figure(self):
        if self.inspector.currentIndex() == 2:
            if self.builder_active:
                self.show_builder_figure()
        else:
            self.inspector.setCurrentIndex(2)

    def show_builder_figure(self):
        self.builder_editing = False
        self.viewer_stack.setCurrentWidget(self.builder_web)
        self.builder_command(type="readonly", enabled=True)
        self.builder_command(type="visibility", visible=True)
        self.send(type="visibility", visible=False)
        self.filename.setText(f"Draft · {self.builder_model['name']} · figure preview")
        self.timeline_widget.hide()
        self.results.hide()

    def export_builder(self, fmt="mol", path=None):
        if not self.builder_ready or self.builder_state.get("busy") or not self.builder_model["atoms"]:
            return
        if path is None:
            name = re.sub(r"[^A-Za-z0-9_-]+", "_", self.builder_model["name"])[:80] or "molecule"
            path, _ = QFileDialog.getSaveFileName(self, "Export built structure", name + "." + fmt, f"{fmt.upper()} (*.{fmt})")
        if path:
            self.builder_export_path = Path(path)
            if not self.builder_export_path.suffix:
                self.builder_export_path = self.builder_export_path.with_suffix("." + fmt)
            self.builder_command(type="export", format=fmt)

    def save_builder_text(self, text):
        if self.builder_export_path is not None:
            try:
                self.builder_export_path.write_text(text, encoding="utf-8")
                self.builder_message(f"Saved {self.builder_export_path.name}")
            except OSError as error:
                self.builder_message(str(error), "error")
            self.builder_export_path = None
