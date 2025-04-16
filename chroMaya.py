import sys
import maya.api.OpenMaya as om
from maya import OpenMayaUI as omui
import maya.cmds as cmds
from PySide2 import QtWidgets, QtCore, QtGui
from shiboken2 import wrapInstance
import numpy as np

plugin_name = "chroMayaUI"

def maya_useNewAPI():
   pass

# Get Maya main window
def get_maya_main_window():
   main_window_ptr = omui.MQtUtil.mainWindow()
   return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)


class MixingDishWidget(QtWidgets.QWidget):
    colorSelected = QtCore.Signal(QtGui.QColor)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.blobs = []
        self.setMinimumSize(400, 400)
        self.current_radius = 30
        self.mixing_radius = 60  
        self.dragging_blob = None
        self.drag_offset = None
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setMouseTracking(True)  # Enable mouse tracking for hover effects
        self.waiting_for_blob_placement = False
        self.pending_blob_color = None
        
    def addBlob(self, pos, color):
        self.blobs.append({
            'pos': pos,
            'color': color,
            'radius': self.current_radius
        })
        self.update()
        
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        buffer = QtGui.QImage(self.size(), QtGui.QImage.Format_ARGB32_Premultiplied)
        buffer.fill(QtCore.Qt.transparent)
        buffer_painter = QtGui.QPainter(buffer)
        buffer_painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        width = self.width()
        height = self.height()
        resolution = 3  # Increase for better quality, decrease for better performance
        
        for x in range(0, width, resolution):
            for y in range(0, height, resolution):
                field = 0.0
                colors = []
                weights = []
                
                for blob in self.blobs:
                    dx = x - blob['pos'].x()
                    dy = y - blob['pos'].y()
                    dist = (dx * dx + dy * dy) ** 0.5
                    influence_radius = blob['radius'] * 3.0
                    
                    if dist <= influence_radius:
                        t = dist / influence_radius
                        t = t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
                        weight = max(0.0, 1.0 - t)
                        field += weight
                        
                        colors.append([
                            blob['color'].redF(),
                            blob['color'].greenF(),
                            blob['color'].blueF()
                        ])
                        weights.append(weight)
                
                if field > 0.5:  
                    total_weight = sum(weights)
                    if total_weight > 0:
                        weights = [w / total_weight for w in weights]
                        gamma = 2.2
                        final_color = [0, 0, 0]
                        for color, weight in zip(colors, weights):
                            linear = [pow(c, gamma) for c in color]
                            final_color = [
                                final_color[i] + linear[i] * weight 
                                for i in range(3)
                            ]
                        final_color = [pow(c, 1/gamma) for c in final_color]
                        color = QtGui.QColor.fromRgbF(
                            min(1.0, max(0.0, final_color[0])),
                            min(1.0, max(0.0, final_color[1])),
                            min(1.0, max(0.0, final_color[2])),
                            min(1.0, field)  
                        )
                        buffer_painter.fillRect(
                            x, y, resolution, resolution, 
                            color
                        )
        buffer_painter.end()
    
        passes = [
            (QtGui.QPainter.CompositionMode_Plus, 0.8),
            (QtGui.QPainter.CompositionMode_Screen, 0.4)
        ]
        
        for composition_mode, opacity in passes:
            painter.setOpacity(opacity)
            painter.setCompositionMode(composition_mode)
            painter.drawImage(0, 0, buffer)
        
    def mousePressEvent(self, event):
        # Handle blob placement mode
        if self.waiting_for_blob_placement and event.button() == QtCore.Qt.LeftButton:
            self.addBlob(event.pos(), self.pending_blob_color)
            self.waiting_for_blob_placement = False
            self.pending_blob_color = None
            QtWidgets.QApplication.restoreOverrideCursor()
            return

        # Shift + Left Click for color sampling
        if event.button() == QtCore.Qt.LeftButton and event.modifiers() == QtCore.Qt.ShiftModifier:
            pos = event.pos()
            color = self.getMixedColorAt(pos)
            if color:
                self.colorSelected.emit(color)
                om.MGlobal.displayInfo("ChroMaya: Color sampled successfully")
                return

        # Regular left click for blob manipulation
        if event.button() == QtCore.Qt.LeftButton:
            blob_index = self.find_blob_at_position(event.pos())
            if blob_index is not None:
                self.dragging_blob = blob_index
                blob_pos = self.blobs[blob_index]['pos']
                self.drag_offset = event.pos() - blob_pos
            else:
                color = QtWidgets.QColorDialog.getColor()
                if color.isValid():
                    self.addBlob(event.pos(), color)
        elif event.button() == QtCore.Qt.RightButton:
            pos = event.pos()
            color = self.getMixedColorAt(pos)
            if color:
                self.colorSelected.emit(color)
                
    def mouseMoveEvent(self, event):
        if self.dragging_blob is not None:
            # Update blob position while dragging
            new_pos = event.pos() - self.drag_offset
            self.blobs[self.dragging_blob]['pos'] = new_pos
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.dragging_blob = None
            self.drag_offset = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            blob_index = self.find_blob_at_position(event.pos())
            if blob_index is not None:
                self.blobs.pop(blob_index)
                self.update()
                om.MGlobal.displayInfo(f"Deleted blob at index {blob_index}")

    def find_blob_at_position(self, pos):
        for i, blob in enumerate(self.blobs):
            dx = pos.x() - blob['pos'].x()
            dy = pos.y() - blob['pos'].y()
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= blob['radius']:
                return i
        return None

    def getMixedColorAt(self, pos):
        """Enhanced color mixing with better interpolation"""
        colors = []
        weights = []
        
        for blob in self.blobs:
            dx = pos.x() - blob['pos'].x()
            dy = pos.y() - blob['pos'].y()
            distance = (dx * dx + dy * dy) ** 0.5
            max_distance = blob['radius'] + self.mixing_radius
            
            if distance <= max_distance:
                t = distance / max_distance
                t = t * t * (3 - 2 * t) 
                weight = 1.0 - t

                colors.append([
                    blob['color'].redF(),
                    blob['color'].greenF(),
                    blob['color'].blueF()
                ])
                weights.append(weight * weight) 
                
        if not weights:
            return None
        
        total_weight = sum(weights)
        if total_weight == 0:
            return None
            
        weights = [w / total_weight for w in weights]
        gamma = 2.2
        mixed_color = [0, 0, 0]
        
        for color, weight in zip(colors, weights):
            linear_color = [pow(c, gamma) for c in color]
        
            mixed_color = [
                mixed + weight * linear
                for mixed, linear in zip(mixed_color, linear_color)
            ]
        final_color = [pow(c, 1/gamma) for c in mixed_color]
        return QtGui.QColor.fromRgbF(
            min(1.0, max(0.0, final_color[0])),
            min(1.0, max(0.0, final_color[1])),
            min(1.0, max(0.0, final_color[2]))
        )

# Our ChroMaya GUI
class ChroMayaWindow(QtWidgets.QMainWindow):
   def __init__(self, parent=get_maya_main_window()):
       super(ChroMayaWindow, self).__init__(parent)
       self.setWindowTitle("ChroMaya")
       self.setMinimumSize(900, 500)
       self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
       central_widget = QtWidgets.QWidget()
       self.setCentralWidget(central_widget)
       self.build_ui(central_widget)

   def build_ui(self, parent_widget):
       layout = QtWidgets.QVBoxLayout(parent_widget)

       # Title
       title_label = QtWidgets.QLabel("ChroMaya")
       title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
       title_label.setAlignment(QtCore.Qt.AlignLeft)
       layout.addWidget(title_label)

       # Horizontal layout for left/right panels
       content_layout = QtWidgets.QHBoxLayout()
       layout.addLayout(content_layout)

       # === LEFT PANEL ===
       left_panel = QtWidgets.QVBoxLayout()
       content_layout.addLayout(left_panel, 1)

       # Add Color Blobs Section
       add_color_label = QtWidgets.QLabel("Add Color Blobs:")
       left_panel.addWidget(add_color_label)
       add_color_label.setStyleSheet("font-weight: bold;")

       color_picker_btn = QtWidgets.QPushButton("Add New Color Blob")
       color_picker_btn.setToolTip("Click to add a new color blob to the mixing dish")
       color_picker_btn.clicked.connect(self.open_color_picker)
       left_panel.addWidget(color_picker_btn)

       # === Divider Line ===
       divider = QtWidgets.QFrame()
       divider.setFrameShape(QtWidgets.QFrame.HLine)
       divider.setFrameShadow(QtWidgets.QFrame.Sunken)
       left_panel.addWidget(divider)

       # Current Swatch Section
       swatch_label = QtWidgets.QLabel("Current Swatch:")
       swatch_label.setStyleSheet("font-weight: bold; margin-top: 1px;")
       left_panel.addWidget(swatch_label)

       swatch_instructions = QtWidgets.QLabel("Shift + Left Click anywhere on the mixing dish\nto sample colors")
       swatch_instructions.setStyleSheet("font-size: 10px; color: #666;")
       left_panel.addWidget(swatch_instructions)

       self.color_preview = QtWidgets.QLabel()
       self.color_preview.setFixedHeight(30)
       self.color_preview.setStyleSheet("background-color: #ffffff; border: 2px solid #aaa; border-radius: 4px;")
       left_panel.addWidget(self.color_preview)

       # === Divider Line ===
       divider = QtWidgets.QFrame()
       divider.setFrameShape(QtWidgets.QFrame.HLine)
       divider.setFrameShadow(QtWidgets.QFrame.Sunken)
       left_panel.addWidget(divider)

       # === Subheader2===
       history_label = QtWidgets.QLabel("Palette History:")
       history_label.setStyleSheet("font-weight: bold; margin-top: 1px;")
       left_panel.addWidget(history_label)


       # === Palette History Buttons ===
       undo_button = QtWidgets.QPushButton("Undo Color")
       redo_button = QtWidgets.QPushButton("Redo Color")
       left_panel.addWidget(undo_button)
       left_panel.addWidget(redo_button)

       # === RIGHT PANEL (Mixing Dish) ===
       right_panel = QtWidgets.QVBoxLayout()
       content_layout.addLayout(right_panel, 2)

       self.mixing_dish = MixingDishWidget()
       self.mixing_dish.colorSelected.connect(self.set_maya_brush_color)
       self.mixing_dish.colorSelected.connect(self.handle_mixing_dish_color)  # Add this line
       right_panel.addWidget(self.mixing_dish)


   def open_color_picker(self):
       """Modified to handle only adding new color blobs"""
       color = QtWidgets.QColorDialog.getColor(parent=self)
       if color.isValid():
           # Let user click where to place the blob
           QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CrossCursor)
           self.mixing_dish.waiting_for_blob_placement = True
           self.mixing_dish.pending_blob_color = color

   def set_maya_brush_color(self, qcolor):
       r = qcolor.redF()
       g = qcolor.greenF()
       b = qcolor.blueF()

       try:
           current_ctx = cmds.currentCtx()

           # 1. Activate 3D Paint Tool if not already active
           if not current_ctx.startswith("art3dPaintCtx") and current_ctx != "art3dPaintContext":
               om.MGlobal.displayWarning("ChroMaya: 3D Paint Tool is not active. Switching to it now.")
               cmds.Art3dPaintTool()
               current_ctx = cmds.currentCtx()

           # 2. Check if something paintable is selected
           selection = cmds.ls(selection=True, long=True)
           if not selection:
               om.MGlobal.displayWarning("ChroMaya: No mesh selected. Select a mesh before painting.")
               return
           else:
               shape = cmds.listRelatives(selection[0], shapes=True, fullPath=True)
               if not shape or cmds.nodeType(shape[0]) != 'mesh':
                   om.MGlobal.displayWarning("ChroMaya: Selection is not a paintable mesh.")
                   return
           # 3. Set brush color
           if cmds.art3dPaintCtx(current_ctx, exists=True):
               cmds.art3dPaintCtx(current_ctx, edit=True, rgb=(r, g, b))
               om.MGlobal.displayInfo(f"ChroMaya: Brush color set to ({r:.2f}, {g:.2f}, {b:.2f}) ✅")
           else:
               om.MGlobal.displayWarning("ChroMaya: Paint context not found.")
       except Exception as e:
           om.MGlobal.displayError(f"ChroMaya: Failed to set brush color: {e}")

   def handle_mixing_dish_color(self, color):
       """Handle when a color is selected from mixing dish"""
       self.color_preview.setStyleSheet(
           f"background-color: {color.name()}; border: 1px solid #aaa;"
       )
       self.set_maya_brush_color(color)

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

# Command creator
def cmdCreator():
   return ChroMayaCommand()

# Plugin load
def initializePlugin(plugin):
   plugin_fn = om.MFnPlugin(plugin)
   try:
       plugin_fn.registerCommand(plugin_name, cmdCreator)
       om.MGlobal.displayInfo("ChroMaya Plugin Loaded.")
   except:
       om.MGlobal.displayError("Failed to register ChroMaya command.")

# Plugin unload
def uninitializePlugin(plugin):
   plugin_fn = om.MFnPlugin(plugin)
   try:
       plugin_fn.deregisterCommand(plugin_name)
       om.MGlobal.displayInfo("ChroMaya Plugin Unloaded.")
   except:
       om.MGlobal.displayError("Failed to unregister ChroMaya command.")



