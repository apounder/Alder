"""Desktop layout: compact inspectors and a large, quiet molecular canvas."""
from pathlib import Path
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QPushButton, QScrollArea, QSlider,
    QSpinBox, QSplitter, QTabWidget, QTableWidget, QVBoxLayout, QWidget, QSizePolicy, QStackedWidget,
)
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

MODES = {
    "orbital": ("Orbital / signed field", "A single cube. Positive and negative lobes use separate colors.", 0.03),
    "density": ("Electron density", "An electron-density isosurface from a single cube.", 0.002),
    "esp": ("ESP on electron density", "Surface: electron density. Color: electrostatic potential, in atomic units.", 0.002),
    "esp_vdw": ("ESP on van der Waals", "Use an ESP cube as the surface field. Color is mapped onto atomic van der Waals radii; this is not an electron-density surface.", 0.002),
    "nci": ("NCI · reduced density gradient", "Surface: RDG. Color: sign(λ₂)ρ. Use precomputed, appropriately masked RDG cubes.", 0.5),
    "igm": ("IGM / IGMH · δg", "Surface: δg, δg_inter, or δg_intra. Color: sign(λ₂)ρ. Adjust the isovalue for your system.", 0.005),
    "custom": ("Custom mapped surface", "Choose any scalar isosurface and a second cube for its colors.", 0.01),
}


def label(text, name=None):
    result = QLabel(text)
    result.setTextFormat(Qt.TextFormat.PlainText)
    result.setWordWrap(True)
    if name:
        result.setObjectName(name)
    return result


def inspector_page(tabs, title):
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(18, 22, 18, 18)
    layout.setSpacing(14)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(content)
    tabs.addTab(scroll, title)
    return layout


def number(minimum, maximum, value, decimals=4):
    control = QDoubleSpinBox()
    control.setDecimals(decimals)
    control.setRange(minimum, maximum)
    control.setValue(value)
    control.setKeyboardTracking(False)
    return control


def build_ui(self, assets, bridge_class, units):
    root = QWidget()
    root.setObjectName("workspace")
    self.setCentralWidget(root)
    outer = QVBoxLayout(root)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)
    header = QWidget()
    header.setObjectName("appHeader")
    bar = QHBoxLayout(header)
    bar.setContentsMargins(24, 14, 24, 14)
    bar.setSpacing(12)
    bar.addWidget(label("◈", "brandMark"))
    bar.addWidget(label("Molecule Studio", "brand"))
    subtitle = label("/  Molecular workspace", "muted")
    subtitle.setWordWrap(False)
    bar.addWidget(subtitle)
    bar.addStretch()
    bar.addWidget(label("●  Local", "localBadge"))
    self.open_button = QPushButton("Open files")
    self.open_button.clicked.connect(self.choose_files)
    bar.addWidget(self.open_button)
    from .job_setup import open_setup
    self.setup_button = QPushButton('Calculation setup')
    self.setup_button.clicked.connect(lambda: open_setup(self))
    bar.addWidget(self.setup_button)
    from .mlip_ui import open_mlip
    self.mlip_button = QPushButton('Local MLIP')
    self.mlip_button.clicked.connect(lambda: open_mlip(self))
    bar.addWidget(self.mlip_button)
    self.export_button = QPushButton("Export figure")
    self.export_button.setObjectName("primary")
    self.export_button.clicked.connect(self.export_image)
    self.export_button.setEnabled(False)
    bar.addWidget(self.export_button)
    outer.addWidget(header)

    content = QHBoxLayout()
    content.setContentsMargins(20, 20, 20, 16)
    outer.addLayout(content, 1)
    body = QSplitter(Qt.Orientation.Horizontal)
    self.body = body
    body.setChildrenCollapsible(False)
    content.addWidget(body)
    self.inspector = QTabWidget()
    self.inspector.setObjectName("inspector")
    self.inspector.setMinimumWidth(330)
    self.inspector.setMaximumWidth(440)
    body.addWidget(self.inspector)

    side = inspector_page(self.inspector, "Calculation")
    self.calculation_picker = QComboBox()
    self.calculation_picker.setToolTip('Switch between loaded outputs; each retains its selected geometry.')
    self.calculation_picker.currentIndexChanged.connect(self.choose_calculation)
    side.addWidget(self.calculation_picker)
    side.addWidget(label("Calculation details", "sectionTitle"))
    self.details = label("Open a Gaussian or ORCA output to explore its structure and energies.")
    self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    side.addWidget(self.details)
    self.warning = label("", "notice")
    self.warning.hide()
    side.addWidget(self.warning)
    side.addSpacing(10)
    side.addWidget(label("Selected geometry", "sectionTitle"))
    self.energy_label = label("—", "energyValue")
    side.addWidget(self.energy_label)
    self.relative_label = label("SCF / DFT electronic energy", "muted")
    side.addWidget(self.relative_label)
    side.addWidget(label("Optimization convergence", "sectionTitle"))
    self.convergence_label = label("Available after loading an optimization.", "small")
    side.addWidget(self.convergence_label)
    side.addStretch()
    side.addWidget(label("Click a point in the energy plot to inspect that geometry.", "muted"))

    side = inspector_page(self.inspector, "Surfaces")
    side.addWidget(label("Surface analysis", "sectionTitle"))
    self.surface_mode = QComboBox()
    for key, (title, _, _) in MODES.items():
        self.surface_mode.addItem(title, key)
    self.surface_mode.currentIndexChanged.connect(self.mode_changed)
    side.addWidget(self.surface_mode)
    self.surface_help = label(MODES["orbital"][1], "muted")
    side.addWidget(self.surface_help)
    fields = QFormLayout()
    fields.setSpacing(10)
    fields.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
    self.surface_field = QComboBox()
    self.surface_field.setMinimumContentsLength(16)
    self.surface_field.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    self.surface_field.addItem("Drop or open a cube…", None)
    self.surface_field.currentIndexChanged.connect(self.field_changed)
    fields.addRow("Surface field", self.surface_field)
    self.color_field = QComboBox()
    self.color_field.addItem("None · uniform color", None)
    self.color_field.currentIndexChanged.connect(self.field_changed)
    fields.addRow("Color field", self.color_field)
    side.addLayout(fields)
    self.cube_label = label("Drop your cube files together, then choose their roles above.", "small")
    side.addWidget(self.cube_label)
    self.surface_message = label("", "notice")
    self.surface_message.hide()
    side.addWidget(self.surface_message)
    self.surface_controls = QWidget()
    controls = QFormLayout(self.surface_controls)
    self.surface_form = controls
    controls.setContentsMargins(0, 0, 0, 0)
    controls.setVerticalSpacing(12)
    controls.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    self.surface_visible = QCheckBox("Show surface")
    self.surface_visible.setChecked(True)
    self.surface_visible.toggled.connect(self.schedule_surface)
    controls.addRow(self.surface_visible)
    self.isovalue = number(0.000001, 10000, 0.03, 6)
    self.isovalue.setSingleStep(0.005)
    self.isovalue.valueChanged.connect(self.schedule_surface)
    controls.addRow("Isovalue", self.isovalue)
    self.opacity = QSlider(Qt.Orientation.Horizontal)
    self.opacity.setRange(5, 100)
    self.opacity.setValue(75)
    self.opacity.valueChanged.connect(self.schedule_surface)
    controls.addRow("Opacity", self.opacity)
    self.signed_surface = QCheckBox("Positive + negative lobes")
    self.signed_surface.setChecked(True)
    self.signed_surface.toggled.connect(self.schedule_surface)
    controls.addRow(self.signed_surface)
    self.color_min = number(-1e6, 1e6, -0.05, 5)
    self.color_max = number(-1e6, 1e6, 0.05, 5)
    self.color_min.valueChanged.connect(self.schedule_surface)
    self.color_max.valueChanged.connect(self.schedule_surface)
    controls.addRow("Color minimum", self.color_min)
    controls.addRow("Color maximum", self.color_max)
    self.color_scale = QComboBox()
    self.color_scale.addItem("Native values / atomic units", 1.0)
    self.color_scale.addItem("NCIPLOT signed density ×100", 0.01)
    self.color_scale.currentIndexChanged.connect(self.schedule_surface)
    controls.addRow("Input scaling", self.color_scale)
    self.gradient = QComboBox()
    self.gradient.addItem("Red → white → blue", "esp")
    self.gradient.addItem("Blue → green → red", "nci")
    self.gradient.currentIndexChanged.connect(self.schedule_surface)
    controls.addRow("Color palette", self.gradient)
    self.show_legend = QCheckBox("Show color scale in figure")
    self.show_legend.setChecked(True)
    self.show_legend.toggled.connect(self.schedule_surface)
    controls.addRow(self.show_legend)
    self.surface_controls.setEnabled(False)
    side.addWidget(self.surface_controls)
    self.remove_cube = QPushButton("Clear cube files")
    self.remove_cube.clicked.connect(self.clear_cube)
    side.addWidget(self.remove_cube)
    side.addStretch()

    side = inspector_page(self.inspector, "Figure")
    side.addWidget(label("Use View above the canvas to style all 3D views. These settings also apply to exported figures.", "muted"))
    self.preset = QComboBox()
    self.preset.addItems(["Studio", "Paton-inspired", "Soft studio"])
    self.preset.currentTextChanged.connect(self.appearance_changed)
    side.addWidget(self.preset)
    self.preset_note = label("A clean ball-and-stick view on white.", "muted")
    side.addWidget(self.preset_note)
    self.outlines = QCheckBox("Fine outlines")
    self.outlines.setChecked(True)
    self.outlines.toggled.connect(self.appearance_changed)
    side.addWidget(self.outlines)
    self.ambient_occlusion = QCheckBox("Ambient occlusion")
    self.ambient_occlusion.toggled.connect(self.appearance_changed)
    side.addWidget(self.ambient_occlusion)
    self.orthographic = QCheckBox("Orthographic projection")
    self.orthographic.setChecked(True)
    self.orthographic.toggled.connect(self.appearance_changed)
    side.addWidget(self.orthographic)
    side.addWidget(label("Figure bonds", "sectionTitle"))
    side.addWidget(label("Select two atoms, donor first for a dative arrow. Bond edits stay with the loaded calculation, including trajectories, comparison overlays and figure exports. Geometry and hydrogens are unchanged. Use Edit geometry → Export MOL to save them as a structure.", "muted"))
    for choices in [[("Single", "single"), ("Double", "double"), ("Triple", "triple")],
                    [("Dative →", "dative"), ("TS ⋯", "ts"), ("Remove", "remove")]]:
        row = QHBoxLayout()
        for title, kind in choices:
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, kind=kind: self.send(type="annotation", kind=kind))
            row.addWidget(button)
        side.addLayout(row)
    side.addSpacing(12)
    side.addWidget(label("Image export", "sectionTitle"))
    export_form = QFormLayout()
    export_form.setSpacing(12)
    self.export_engine = QComboBox()
    self.export_engine.addItem("Studio", "studio")
    self.export_engine.addItem("Ray traced · physical lighting", "raytrace")
    export_form.addRow("Renderer", self.export_engine)
    self.ray_samples = QSpinBox()
    self.ray_samples.setRange(1, 1024)
    self.ray_samples.setValue(64)
    self.ray_samples.setSingleStep(32)
    self.ray_samples.setToolTip("Samples per pixel. Higher values reduce noise and take longer.")
    self.ray_samples.setEnabled(False)
    export_form.addRow("Ray samples", self.ray_samples)
    self.export_size = QSpinBox()
    self.export_size.setRange(400, 6000)
    self.export_size.setSingleStep(400)
    self.export_size.setValue(2400)
    self.export_size.setSuffix(" px")
    export_form.addRow("Longest edge", self.export_size)
    self.export_samples = QComboBox()
    self.export_samples.addItem("2× supersampling", 2)
    self.export_samples.addItem("Native resolution", 1)
    export_form.addRow("Antialiasing", self.export_samples)
    self.export_engine.currentIndexChanged.connect(lambda: (
        self.ray_samples.setEnabled(self.export_engine.currentData() == "raytrace"),
        self.export_samples.setEnabled(self.export_engine.currentData() != "raytrace")))
    self.export_dpi = QSpinBox()
    self.export_dpi.setRange(72, 1200)
    self.export_dpi.setValue(300)
    export_form.addRow("Print DPI", self.export_dpi)
    side.addLayout(export_form)
    self.transparent = QCheckBox("Transparent background")
    side.addWidget(self.transparent)
    side.addWidget(label("Renders at the requested size. PNG and TIFF retain transparency and print-resolution metadata.", "muted"))
    render = QPushButton("Export figure…")
    render.setObjectName("primary")
    render.clicked.connect(self.export_image)
    side.addWidget(render)
    side.addWidget(label("Ray tracing uses physical light, shadows and reflections with the current colors, radii and camera. Preview outlines and screen-space AO are replaced by physical shading.", "muted"))
    side.addWidget(label("Animation export", "sectionTitle"))
    video_form = QFormLayout()
    self.video_source = QComboBox()
    for title, key in [("Full calculation trajectory", "trajectory"), ("IRC / scan points", "path"), ("Selected vibrational mode", "vibration")]:
        self.video_source.addItem(title, key)
    video_form.addRow("Source", self.video_source)
    self.video_size = QComboBox()
    for edge in [720, 1280, 1920, 3840]:
        self.video_size.addItem(f"{edge} px", edge)
    self.video_size.setCurrentIndex(1)
    video_form.addRow("Longest edge", self.video_size)
    self.video_fps = QSpinBox()
    self.video_fps.setRange(1, 60)
    self.video_fps.setValue(24)
    video_form.addRow("Frames / second", self.video_fps)
    self.video_hold = QSpinBox()
    self.video_hold.setRange(1, 120)
    self.video_hold.setValue(3)
    video_form.addRow("Frames / geometry", self.video_hold)
    self.video_period = QSpinBox()
    self.video_period.setRange(8, 240)
    self.video_period.setValue(48)
    video_form.addRow("Frames / mode cycle", self.video_period)
    self.video_cycles = QSpinBox()
    self.video_cycles.setRange(1, 20)
    self.video_cycles.setValue(2)
    video_form.addRow("Mode cycles", self.video_cycles)
    def video_controls():
        vibration = self.video_source.currentData() == "vibration"
        self.video_hold.setEnabled(not vibration)
        self.video_period.setEnabled(vibration)
        self.video_cycles.setEnabled(vibration)
    self.video_source.currentIndexChanged.connect(video_controls)
    video_controls()
    side.addLayout(video_form)
    side.addWidget(label("Uses the renderer and ray samples above. Select the TS mode under Results → Vibrations; its amplitude is retained. WebM videos have an opaque background and show molecular geometry; cube surfaces are omitted. Every trajectory geometry is included.", "muted"))
    video_button = QPushButton("Export video…")
    video_button.clicked.connect(self.export_video)
    side.addWidget(video_button)
    side.addStretch()

    right = QSplitter(Qt.Orientation.Vertical)
    right.setChildrenCollapsible(False)
    body.addWidget(right)
    body.setSizes([340, 1000])
    body.setStretchFactor(1, 1)
    top = QFrame()
    top.setObjectName("viewerCard")
    top_layout = QVBoxLayout(top)
    top_layout.setContentsMargins(0, 0, 0, 0)
    top_layout.setSpacing(0)
    viewbar = QHBoxLayout()
    self.viewbar = viewbar
    viewbar.setContentsMargins(18, 12, 18, 12)
    self.filename = label("Untitled calculation", "fileTitle")
    viewbar.addWidget(self.filename, 1)
    self.style = QComboBox()
    self.style.addItems(["Ball and stick", "Stick", "Space filling"])
    self.style.currentTextChanged.connect(lambda value: self.send(type="style", style=value))
    viewbar.addWidget(self.style)
    fit = QPushButton("Fit view")
    self.fit_button = fit
    fit.clicked.connect(lambda: self.send(type="fit"))
    viewbar.addWidget(fit)
    self.measure_button = QPushButton("Measure")
    self.measure_button.setCheckable(True)
    self.measure_button.setToolTip("Measure a bond length, angle, or dihedral by clicking atoms in order. Escape clears the picks.")
    self.measure_button.clicked.connect(self.choose_measurement)
    viewbar.insertWidget(viewbar.count()-1, self.measure_button)
    top_layout.addLayout(viewbar)
    self.measurement_panel = QWidget()
    measurement_row = QHBoxLayout(self.measurement_panel)
    measurement_row.setContentsMargins(18, 4, 18, 10)
    self.measurement_kind = QComboBox()
    for title, count in (("Bond length · 2 atoms", 2), ("Angle · 3 atoms", 3), ("Dihedral · 4 atoms", 4)):
        self.measurement_kind.addItem(title, count)
    self.measurement_kind.setAccessibleName("Measurement type")
    self.measurement_kind.setToolTip("Bond length measures any two atoms. For an angle, pick the vertex second. For a dihedral, pick four atoms along the torsion.")
    self.measurement_kind.currentIndexChanged.connect(lambda: self.choose_measurement(True))
    measurement_row.addWidget(self.measurement_kind)
    self.measurement_readout = label("Pick 2 atoms in order (0/2).", "small")
    self.measurement_readout.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    measurement_row.addWidget(self.measurement_readout, 1)
    self.measurement_clear = QPushButton("Clear")
    self.measurement_clear.setAccessibleName("Clear measurement")
    self.measurement_clear.clicked.connect(lambda: self.choose_measurement(True))
    measurement_row.addWidget(self.measurement_clear)
    self.measurement_panel.hide()
    top_layout.addWidget(self.measurement_panel)
    self.web = QWebEngineView()
    self.web.setMinimumHeight(280)
    self.web.setAcceptDrops(True)
    self.web.installEventFilter(self)
    self.web.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
    self.web.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
    self.bridge = bridge_class(self)
    self.bridge.initialized.connect(self.renderer_initialized)
    self.bridge.error.connect(self.render_error)
    self.bridge.image.connect(self.save_image)
    self.bridge.copied.connect(self.receive_geometry_copy)
    self.connect_export_bridge(self.bridge)
    self.channel = QWebChannel(self.web.page())
    self.channel.registerObject("bridge", self.bridge)
    self.web.page().setWebChannel(self.channel)
    self.web.load(QUrl.fromLocalFile(str(assets / "viewer.html")))
    self.viewer_stack = QStackedWidget()
    self.viewer_stack.addWidget(self.web)
    top_layout.addWidget(self.viewer_stack, 1)
    self.timeline_widget = QWidget()
    timeline = QHBoxLayout(self.timeline_widget)
    timeline.setContentsMargins(18, 12, 18, 12)
    self.play = QPushButton("Play")
    self.play.setCheckable(True)
    self.play.setEnabled(False)
    self.play.toggled.connect(self.toggle_play)
    timeline.addWidget(self.play)
    self.trajectory_speed = QDoubleSpinBox()
    self.trajectory_speed.setRange(0.1, 10)
    self.trajectory_speed.setSingleStep(0.25)
    self.trajectory_speed.setValue(1)
    self.trajectory_speed.setSuffix('×')
    self.trajectory_speed.setToolTip('Trajectory playback speed; 1× is one geometry every 350 ms.')
    self.trajectory_speed.setAccessibleName('Trajectory playback speed')
    self.trajectory_speed.valueChanged.connect(lambda speed: self.timer.setInterval(round(350 / speed)))
    timeline.addWidget(self.trajectory_speed)
    self.slider = QSlider(Qt.Orientation.Horizontal)
    self.slider.setRange(0, 0)
    self.slider.valueChanged.connect(self.select_step)
    timeline.addWidget(self.slider, 1)
    self.step_label = label("No geometry", "muted")
    timeline.addWidget(self.step_label)
    top_layout.addWidget(self.timeline_widget)
    right.addWidget(top)

    tabs = QTabWidget()
    self.results = tabs
    tabs.setObjectName("results")
    profile = QWidget()
    profile_layout = QVBoxLayout(profile)
    profile_layout.setContentsMargins(16, 10, 16, 8)
    plotbar = QHBoxLayout()
    self.energy_profile_title = label("SCF / DFT energy", "small")
    plotbar.addWidget(self.energy_profile_title)
    plotbar.addStretch()
    self.units = QComboBox()
    self.units.addItems(units)
    self.units.currentTextChanged.connect(self.update_energy_view)
    plotbar.addWidget(self.units)
    self.reference = QComboBox()
    self.reference.addItems(["Relative to minimum", "Relative to first", "Absolute"])
    self.reference.currentTextChanged.connect(self.update_energy_view)
    plotbar.addWidget(self.reference)
    profile_layout.addLayout(plotbar)
    self.figure = Figure(figsize=(7, 2), layout="constrained", facecolor="#ffffff")
    self.canvas = FigureCanvasQTAgg(self.figure)
    self.canvas.setMinimumHeight(135)
    self.ax = self.figure.add_subplot()
    self.canvas.mpl_connect("button_press_event", self.plot_clicked)
    profile_layout.addWidget(self.canvas)
    tabs.addTab(profile, "Energy profile")
    tablepage = QWidget()
    tablelayout = QVBoxLayout(tablepage)
    self.table = QTableWidget(0, 3)
    self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    self.table.cellClicked.connect(lambda row, col: self.slider.setValue(row))
    tablelayout.addWidget(self.table)
    exports = QHBoxLayout()
    for title, callback in [("Export CSV", self.export_csv), ("Export XYZ", self.export_xyz)]:
        button = QPushButton(title)
        button.clicked.connect(callback)
        exports.addWidget(button)
    exports.addStretch()
    tablelayout.addLayout(exports)
    tabs.addTab(tablepage, "Step data")
    self.install_results(tabs)
    right.addWidget(tabs)
    right.setSizes([560, 275])
    self.draw_plot()
    menu = self.menuBar().addMenu("File")
    action = QAction("Open files…", self)
    action.setShortcut(QKeySequence.StandardKey.Open)
    action.triggered.connect(self.choose_files)
    menu.addAction(action)
    menu.addAction('Calculation setup…', lambda: open_setup(self))
    menu.addAction("Export figure…", self.export_image)
    menu.addAction("Export selected geometry…", self.export_xyz)
    menu.addAction("Export energies…", self.export_csv)
    menu.addSeparator()
    menu.addAction("Quit", self.close)
    for control in self.inspector.findChildren(QComboBox):
        control.setMinimumContentsLength(12)
        control.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        control.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        control.setMinimumWidth(0)
    self.install_builder(assets)
    self.install_comparison()
    self.mode_changed()


def configure_app(app):
    app.setApplicationName("Molecule Studio")
    app.setWindowIcon(QIcon(str(Path(__file__).parent / 'assets' / 'studio.ico')))
    app.setStyle("Fusion")
    # Fusion's standard palette can still follow the OS dark theme. Set every
    # native control surface explicitly, including editor viewports and checks.
    palette = QPalette()
    for role, color in {
        'Window':'#f5f7f5', 'WindowText':'#26382d', 'Base':'#f7f8f7',
        'AlternateBase':'#edf1ed', 'Text':'#26382d', 'Button':'#f7f8f7',
        'ButtonText':'#26382d', 'Highlight':'#dceee1', 'HighlightedText':'#173b25',
        'PlaceholderText':'#64726a', 'ToolTipBase':'#fffef5', 'ToolTipText':'#26382d',
        'Light':'#ffffff', 'Midlight':'#edf1ed', 'Mid':'#a6b4aa',
        'Dark':'#64726a', 'Shadow':'#26382d', 'Link':'#14793b', 'LinkVisited':'#385c45',
    }.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(color))
    for role in ('Text', 'WindowText', 'ButtonText'):
        palette.setColor(QPalette.ColorGroup.Disabled, getattr(QPalette.ColorRole, role), QColor('#64726a'))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, QColor('#edf1ed'))
    app.setPalette(palette)
    app.setStyleSheet("""
        QWidget { color:#26382d; font-size:13px; }
        QMainWindow, QDialog, QWidget#workspace { background:#f5f7f5; }
        QWidget#appHeader { background:white; border-bottom:1px solid #dfe6df; }
        QLabel { background:transparent; }
        QLabel#brand { font-size:20px; font-weight:600; }
        QLabel#brandMark { font-size:28px; color:#189143; }
        QLabel#muted { color:#718077; font-size:12px; }
        QLabel#small { color:#52645a; font-size:12px; }
        QLabel#sectionTitle { font-size:14px; font-weight:600; }
        QLabel#fileTitle { font-size:15px; font-weight:600; }
        QLabel#energyValue { font-size:21px; font-weight:500; color:#14793b; }
        QLabel#localBadge { color:#14793b; background:#edf7ee; border-radius:10px; padding:4px 10px; font-size:11px; }
        QLabel#notice { color:#945520; background:#fff8eb; border-radius:5px; padding:9px; font-size:12px; }
        QScrollArea, QScrollArea > QWidget > QWidget, QTabWidget::pane, QFrame#viewerCard { background:white; }
        QFrame#viewerCard, QTabWidget::pane { border:1px solid #dde5dd; border-radius:6px; }
        QPushButton, QToolButton { background:white; border:1px solid #d5dfd6; border-radius:5px; padding:8px 13px; min-height:16px; }
        QPushButton:hover, QToolButton:hover { background:#f0f7f1; border-color:#9bbba3; }
        QPushButton:pressed, QPushButton:checked { background:#e5f3e8; }
        QToolButton::menu-indicator { image:none; }
        QPushButton#builderTool { background:#d7e3eb; border-color:#d7e3eb; text-align:left; padding:7px 9px; }
        QPushButton#builderTool:checked { background:#afbfca; border-color:#96abb9; color:#142832; }
        QPushButton#builderTool:hover { background:#c6d8e3; }
        QPushButton#modeButton { min-width:38px; border-radius:4px; background:#f2f5f3; }
        QPushButton#modeButton:checked { color:#14793b; background:#e3f1e8; border-color:#96bca3; font-weight:600; }
        QPushButton#primary { background:#14793b; color:white; border:1px solid #14793b; font-weight:500; }
        QPushButton#primary:hover { background:#0c5c30; }
        QPushButton:disabled { color:#a6b1a8; background:#f3f6f3; border-color:#e2e8e2; }
        QComboBox, QSpinBox, QDoubleSpinBox { background:white; border:1px solid #d8e1d9; border-radius:5px; padding:7px 9px; min-height:16px; selection-background-color:#e2f3e6; selection-color:#26382d; }
        QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color:#189143; }
        QComboBox::drop-down { width:20px; border:0; }
        QComboBox::down-arrow { image:url("STUDIO_ASSETS/chevron-down.svg"); width:12px; height:12px; }
        QComboBox QAbstractItemView { background:#f7f8f7; color:#26382d; border:1px solid #d8e1d9; selection-background-color:#e6f4e9; selection-color:#173b25; outline:0; }
        QComboBox QAbstractItemView::item { background:#f7f8f7; color:#26382d; }
        QComboBox QAbstractItemView::item:selected { background:#e6f4e9; color:#173b25; }
        QComboBox QAbstractItemView::item:disabled { color:#758178; }
        QMenu { background:#f7f8f7; color:#26382d; border:1px solid #d8e1d9; padding:4px; }
        QMenu::item:selected { background:#e6f4e9; color:#173b25; }
        QMenu::item:disabled { color:#758178; }
        QMenu::separator { height:1px; background:#d8e1d9; margin:4px 8px; }
        QCheckBox, QRadioButton { spacing:8px; color:#26382d; background:transparent; }
        QCheckBox:disabled, QRadioButton:disabled { color:#64726a; }
        QCheckBox::indicator { width:16px; height:16px; border:1px solid #8b9d90; border-radius:3px; background:#f7f8f7; }
        QCheckBox::indicator:hover { border-color:#14793b; background:#eaf4ed; }
        QCheckBox::indicator:focus { border:2px solid #14793b; }
        QCheckBox::indicator:checked { background:#14793b; border-color:#14793b; image:url("STUDIO_ASSETS/checkmark.svg"); }
        QCheckBox::indicator:indeterminate { background:#14793b; border-color:#14793b; image:url("STUDIO_ASSETS/check-partial.svg"); }
        QCheckBox::indicator:disabled { background:#edf1ed; border-color:#bac6bd; }
        QCheckBox::indicator:checked:disabled, QCheckBox::indicator:indeterminate:disabled { background:#738a79; border-color:#738a79; }
        QTabBar::tab { padding:12px 14px; color:#758178; background:transparent; border-bottom:2px solid transparent; }
        QTabBar::tab:selected { color:#14793b; border-bottom:2px solid #189143; }
        QTabWidget#inspector QTabBar::tab { padding:12px 6px; font-size:12px; }
        QLineEdit, QPlainTextEdit, QTextEdit { background:#f7f8f7; color:#26382d; border:1px solid #d8e1d9; border-radius:5px; padding:8px; selection-background-color:#dceee1; selection-color:#173b25; }
        QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus { border-color:#189143; }
        QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled, QAbstractSpinBox:disabled, QComboBox:disabled { background:#edf1ed; color:#64726a; }
        QTabBar::tab:hover { color:#14793b; background:#edf4ed; }
        QTableWidget { background:white; gridline-color:#edf1ed; border:0; selection-background-color:#e3f2e6; selection-color:#173b25; }
        QHeaderView::section { background:#f5f8f5; padding:9px; border:0; color:#65756a; }
        QSlider::groove:horizontal { height:4px; background:#e0e9e1; border-radius:2px; }
        QSlider::handle:horizontal { width:13px; margin:-5px 0; background:#189143; border-radius:6px; }
        QSplitter::handle { background:transparent; width:14px; height:12px; }
        QStatusBar { color:#7b887e; background:#f5f7f5; font-size:11px; }
        QScrollBar:vertical { background:transparent; width:8px; }
        QScrollBar::handle:vertical { background:#d7e1d8; border-radius:4px; min-height:24px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
    """.replace("STUDIO_ASSETS", (Path(__file__).parent / "assets").as_posix()))
