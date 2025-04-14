import sys
import maya.api.OpenMaya as om
from maya import OpenMayaUI as omui
import maya.cmds as cmds
from PySide2 import QtWidgets, QtCore, QtOpenGL
from shiboken2 import wrapInstance
import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
from geometry import Blob
from shader_renderer import ShaderMetaballRenderer

plugin_name = "chroMayaUI"

def maya_useNewAPI():
    pass

def get_maya_main_window():
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)

class MetaballWidget(QtOpenGL.QGLWidget):
    def __init__(self, parent=None):
        super(MetaballWidget, self).__init__(parent)
        self.setMouseTracking(True)
        self.is_dragging = False
        self.selected_blob = None
        self.blobs = []
        self.metaball_renderer = None
        self.current_color = np.array([1.0, 0.0, 0.0])  # Default red
        
    def initializeGL(self):
        glClearColor(1.0, 1.0, 1.0, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self.metaball_renderer = ShaderMetaballRenderer()
        
    def resizeGL(self, w, h):
        device_w = int(w * self.devicePixelRatio())
        device_h = int(h * self.devicePixelRatio())
        glViewport(0, 0, device_w, device_h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(-1, 1, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        
    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if self.blobs:
            device_w = int(self.width() * self.devicePixelRatio())
            device_h = int(self.height() * self.devicePixelRatio())
            self.metaball_renderer.render(self.blobs, device_w, device_h)
            
    def get_clip_space_position(self, pos):
        ratio = self.devicePixelRatio()
        device_x = pos.x() * ratio
        device_y = pos.y() * ratio
        x = (device_x / (self.width() * ratio)) * 2 - 1
        y = -((device_y / (self.height() * ratio)) * 2 - 1)
        return np.array([x, y, 0])
            
    def mousePressEvent(self, event):
        pos = self.get_clip_space_position(event.pos())
        
        if event.button() == QtCore.Qt.LeftButton:
            for blob in reversed(self.blobs):
                dx = pos[0] - blob.position[0]
                dy = pos[1] - blob.position[1]
                distance = np.sqrt(dx * dx + dy * dy)
                
                if distance < blob.radius:
                    self.is_dragging = True
                    self.selected_blob = blob
                    return
                    
            self.blobs.append(Blob(
                pos,
                self.current_color,
                0.1
            ))
            self.update()
            
    def mouseMoveEvent(self, event):
        if self.is_dragging and self.selected_blob:
            pos = self.get_clip_space_position(event.pos())
            self.selected_blob.position[0] = pos[0]
            self.selected_blob.position[1] = pos[1]
            self.update()
            
    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.is_dragging = False
            self.selected_blob = None
            
    def mouseDoubleClickEvent(self, event):
        pos = self.get_clip_space_position(event.pos())
        
        for blob in reversed(self.blobs):
            dx = pos[0] - blob.position[0]
            dy = pos[1] - blob.position[1]
            distance = np.sqrt(dx * dx + dy * dy)
            
            if distance < blob.radius:
                color = QtWidgets.QColorDialog.getColor()
                if color.isValid():
                    blob.color = np.array([
                        color.redF(),
                        color.greenF(),
                        color.blueF()
                    ])
                    self.update()
                return
                
    def contextMenuEvent(self, event):
        pos = self.get_clip_space_position(event.pos())
        
        for i, blob in enumerate(reversed(self.blobs)):
            dx = pos[0] - blob.position[0]
            dy = pos[1] - blob.position[1]
            distance = np.sqrt(dx * dx + dy * dy)
            
            if distance < blob.radius:
                self.blobs.pop(len(self.blobs) - 1 - i)
                self.update()
                return
                
    def set_color(self, color):
        self.current_color = np.array([
            color.redF(),
            color.greenF(),
            color.blueF()
        ])

class ChroMayaWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=get_maya_main_window()):
        super(ChroMayaWindow, self).__init__(parent)
        self.setWindowTitle("ChroMaya")
        self.setMinimumSize(600, 500)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        self.build_ui(central_widget)

    def build_ui(self, parent_widget):
        layout = QtWidgets.QVBoxLayout(parent_widget)

        title_label = QtWidgets.QLabel("ChroMaya")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        title_label.setAlignment(QtCore.Qt.AlignLeft)
        layout.addWidget(title_label)

        content_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(content_layout)

        # === LEFT PANEL ===
        left_panel = QtWidgets.QVBoxLayout()
        content_layout.addLayout(left_panel, 1)

        # Color Picker
        select_color = QtWidgets.QLabel("Select a Color:")
        left_panel.addWidget(select_color)
        select_color.setStyleSheet("font-weight: bold; margin-top: 5px;")

        color_picker_btn = QtWidgets.QPushButton("Open Color Picker")
        color_picker_btn.clicked.connect(self.open_color_picker)

        self.color_preview = QtWidgets.QLabel()
        self.color_preview.setFixedSize(60, 30)
        self.color_preview.setStyleSheet("background-color: #ffffff; border: 1px solid #aaa;")

        left_panel.addWidget(color_picker_btn)
        left_panel.addWidget(self.color_preview)
        divider = QtWidgets.QFrame()
        divider.setFrameShape(QtWidgets.QFrame.HLine)
        divider.setFrameShadow(QtWidgets.QFrame.Sunken)
        left_panel.addWidget(divider)
        edit_label = QtWidgets.QLabel("Edit Colors:")
        edit_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        left_panel.addWidget(edit_label)
        delete_button = QtWidgets.QPushButton("Delete Color")
        radius_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        radius_slider.setMinimum(1)
        radius_slider.setMaximum(100)
        radius_slider.setValue(50)
        radius_label = QtWidgets.QLabel("Change Blob Radius")

        left_panel.addWidget(delete_button)
        left_panel.addWidget(radius_label)
        left_panel.addWidget(radius_slider)

        left_panel.addStretch()

        right_panel = QtWidgets.QVBoxLayout()
        content_layout.addLayout(right_panel, 2)

        # Replace the mixing dish label with our OpenGL widget
        self.metaball_widget = MetaballWidget()
        self.metaball_widget.setMinimumSize(400, 400)
        self.metaball_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        right_panel.addWidget(self.metaball_widget)

        # Connect radius slider to metaball widget
        radius_slider.valueChanged.connect(lambda value: self.update_blob_radius(value))

    def open_color_picker(self):
        color = QtWidgets.QColorDialog.getColor(parent=self)
        if color.isValid():
            hex_color = color.name()
            self.color_preview.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #aaa;")
            self.metaball_widget.set_color(color)
            self.set_maya_brush_color(color)

    def update_blob_radius(self, value):
        # Convert slider value (1-100) to radius (0.05-0.2)
        radius = 0.05 + (value / 100.0) * 0.15
        for blob in self.metaball_widget.blobs:
            blob.radius = radius
        self.metaball_widget.update()

    def set_maya_brush_color(self, qcolor):
        r = qcolor.redF()
        g = qcolor.greenF()
        b = qcolor.blueF()

        try:
            current_ctx = cmds.currentCtx()
            if not current_ctx.startswith("art3dPaintCtx") and current_ctx != "art3dPaintContext":
                om.MGlobal.displayWarning("ChroMaya: 3D Paint Tool is not active. Switching to it now.")
                cmds.Art3dPaintTool()
                current_ctx = cmds.currentCtx()

            selection = cmds.ls(selection=True, long=True)
            if not selection:
                om.MGlobal.displayWarning("ChroMaya: No mesh selected. Select a mesh before painting.")
                return
            else:
                shape = cmds.listRelatives(selection[0], shapes=True, fullPath=True)
                if not shape or cmds.nodeType(shape[0]) != 'mesh':
                    om.MGlobal.displayWarning("ChroMaya: Selection is not a paintable mesh.")
                    return

            if cmds.art3dPaintCtx(current_ctx, exists=True):
                cmds.art3dPaintCtx(current_ctx, edit=True, rgb=(r, g, b))
                om.MGlobal.displayInfo(f"ChroMaya: Brush color set to ({r:.2f}, {g:.2f}, {b:.2f}) ✅")
            else:
                om.MGlobal.displayWarning("ChroMaya: Paint context not found.")
        except Exception as e:
            om.MGlobal.displayError(f"ChroMaya: Failed to set brush color: {e}")

# The command that shows the GUI
class ChroMayaCommand(om.MPxCommand):
    def __init__(self):
        super(ChroMayaCommand, self).__init__()

    def doIt(self, args):
        try:
            for widget in QtWidgets.QApplication.allWidgets():
                if isinstance(widget, ChroMayaWindow):
                    widget.close()
                    widget.deleteLater()
        except:
            pass

        self.window = ChroMayaWindow()
        self.window.show()

def cmdCreator():
    return ChroMayaCommand()

def initializePlugin(plugin):
    plugin_fn = om.MFnPlugin(plugin)
    try:
        plugin_fn.registerCommand(plugin_name, cmdCreator)
        om.MGlobal.displayInfo("ChroMaya Plugin Loaded.")
    except:
        om.MGlobal.displayError("Failed to register ChroMaya command.")

def uninitializePlugin(plugin):
    plugin_fn = om.MFnPlugin(plugin)
    try:
        plugin_fn.deregisterCommand(plugin_name)
        om.MGlobal.displayInfo("ChroMaya Plugin Unloaded.")
    except:
        om.MGlobal.displayError("Failed to unregister ChroMaya command.")
