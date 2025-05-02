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
        # Parameters for metaball function as described in paper
        self.ideal_radius = 0.2
        self.falloff_margin = 0.3
        
    def addBlob(self, pos, color):
        self.blobs.append({
            'pos': pos,
            'color': color,
            'radius': self.current_radius
        })
        self.update()
    
    def metaball_function(self, distance, radius):
        """
        Implementation of the metaball function from the paper.
        Uses a Gaussian approximation with finite extent.
        """
        # Transform distance to standardize falloff
        scale_factor = self.ideal_radius / radius if radius > 0 else 1.0
        d = distance * scale_factor
        
        # Calculate b parameter (ideal_radius + falloff_margin)
        b = self.ideal_radius + self.falloff_margin
        
        # Return influence value
        if d <= b:
            return 1 - (4 * (d**6)) / (9 * (b**6)) + (17 * (d**4)) / (9 * (b**4)) - (22 * (d**2)) / (9 * (b**2))
        else:
            return 0.0
        
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        buffer = QtGui.QImage(self.size(), QtGui.QImage.Format_ARGB32_Premultiplied)
        buffer.fill(QtCore.Qt.transparent)
        buffer_painter = QtGui.QPainter(buffer)
        buffer_painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        width = self.width()
        height = self.height()
        resolution = 2  # Increase for better quality, decrease for better performance
        
        # Threshold for rendering as defined in paper (Eq. 1)
        threshold = 0.5
        
        for x in range(0, width, resolution):
            for y in range(0, height, resolution):
                field_sum = 0.0
                colors = []
                weights = []
                
                for blob in self.blobs:
                    dx = x - blob['pos'].x()
                    dy = y - blob['pos'].y()
                    dist = (dx * dx + dy * dy) ** 0.5
                    
                    # Calculate influence using metaball function
                    influence = self.metaball_function(dist, blob['radius'])
                    
                    if influence > 0:
                        field_sum += influence
                        colors.append([
                            blob['color'].redF(),
                            blob['color'].greenF(),
                            blob['color'].blueF()
                        ])
                        weights.append(influence)
                
                # Only render if influence sum is above threshold (Eq. 1)
                if field_sum >= threshold:
                    # Calculate color using weighted average (Eq. 2)
                    total_weight = sum(weights)
                    
                    if total_weight > 0:
                        weights = [w / total_weight for w in weights]
                        
                        # Use sRGB linear interpolation
                        gamma = 2.2
                        final_color = [0, 0, 0]
                        
                        for color, weight in zip(colors, weights):
                            # Convert to linear space for mixing
                            linear = [pow(c, gamma) for c in color]
                            
                            # Linear interpolation
                            final_color = [
                                final_color[i] + linear[i] * weight 
                                for i in range(3)
                            ]
                        
                        # Convert back to sRGB
                        final_color = [pow(c, 1/gamma) for c in final_color]
                        
                        # Create color for rendering
                        color = QtGui.QColor.fromRgbF(
                            min(1.0, max(0.0, final_color[0])),
                            min(1.0, max(0.0, final_color[1])),
                            min(1.0, max(0.0, final_color[2])),
                            1.0  # Solid color as in paper
                        )
                        
                        buffer_painter.fillRect(
                            x, y, resolution, resolution, 
                            color
                        )
        
        buffer_painter.end()
        
        # Render the buffer directly without composition modes
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
        """
        Get mixed color at position using the metaball function from the paper
        """
        colors = []
        weights = []
        total_influence = 0.0
        
        # Threshold for valid color sampling
        threshold = 0.01
        
        for blob in self.blobs:
            dx = pos.x() - blob['pos'].x()
            dy = pos.y() - blob['pos'].y()
            distance = (dx * dx + dy * dy) ** 0.5
            
            # Calculate influence using metaball function
            influence = self.metaball_function(distance, blob['radius'])
            
            if influence > threshold:
                colors.append([
                    blob['color'].redF(),
                    blob['color'].greenF(),
                    blob['color'].blueF()
                ])
                weights.append(influence)
                total_influence += influence
        
        if total_influence < threshold:
            return None
            
        # Normalize weights
        weights = [w / total_influence for w in weights]
        
        # Use sRGB linear interpolation
        gamma = 2.2
        mixed_color = [0, 0, 0]
        
        for color, weight in zip(colors, weights):
            # Convert to linear space for mixing
            linear_color = [pow(c, gamma) for c in color]
            
            # Linear interpolation
            mixed_color = [
                mixed + weight * linear
                for mixed, linear in zip(mixed_color, linear_color)
            ]
            
        # Convert back to sRGB
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



