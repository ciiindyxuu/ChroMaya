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
        
        # History for undo/redo operations
        self.history = []
        self.history_position = -1
        self.max_history = 20
        self.save_state()  # Save initial empty state
        
        # Set up tooltip
        self.setToolTip(
            "Left click: Add a new color blob\n"
            "Drag: Move a blob\n"
            "Double-click: Delete a blob\n"
            "Shift + Double-click: Change blob color\n"
            "Shift + Left click: Sample mixed color\n"
            "Right click: Sample mixed color"
        )

    def save_state(self):
        """Save current palette state to history"""
        # Create deep copy of current blobs
        current_state = []
        for blob in self.blobs:
            current_state.append({
                'pos': QtCore.QPoint(blob['pos']),
                'color': QtGui.QColor(blob['color']),
                'radius': blob['radius']
            })
            
        # If we're in the middle of the history, truncate
        if self.history_position < len(self.history) - 1:
            self.history = self.history[:self.history_position + 1]
            
        # Add current state to history
        self.history.append(current_state)
        self.history_position = len(self.history) - 1
        
        # Limit history size
        if len(self.history) > self.max_history:
            self.history.pop(0)
            self.history_position -= 1
        
    def undo(self):
        """Undo last action"""
        if self.history_position > 0:
            self.history_position -= 1
            self.restore_state(self.history_position)
            return True
        return False
        
    def redo(self):
        """Redo last undone action"""
        if self.history_position < len(self.history) - 1:
            self.history_position += 1
            self.restore_state(self.history_position)
            return True
        return False
        
    def restore_state(self, position):
        """Restore palette to a specific state in history"""
        if 0 <= position < len(self.history):
            state = self.history[position]
            self.blobs = []
            for blob in state:
                self.blobs.append({
                    'pos': blob['pos'],
                    'color': blob['color'],
                    'radius': blob['radius']
                })
            self.update()
            
    def addBlob(self, pos, color):
        self.blobs.append({
            'pos': pos,
            'color': color,
            'radius': self.current_radius
        })
        self.save_state()  # Save state after adding a blob
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
        if event.button() == QtCore.Qt.LeftButton and self.dragging_blob is not None:
            # Save state after completing a drag operation
            self.save_state()
            self.dragging_blob = None
            self.drag_offset = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            blob_index = self.find_blob_at_position(event.pos())
            if blob_index is not None:
                # If pressing Shift, edit the blob color
                if event.modifiers() == QtCore.Qt.ShiftModifier:
                    current_color = self.blobs[blob_index]['color']
                    new_color = QtWidgets.QColorDialog.getColor(current_color)
                    if new_color.isValid():
                        self.blobs[blob_index]['color'] = new_color
                        self.save_state()  # Save state after changing color
                        self.update()
                        om.MGlobal.displayInfo(f"Changed blob color at index {blob_index}")
                # Otherwise delete the blob
                else:
                    self.blobs.pop(blob_index)
                    self.save_state()  # Save state after deleting a blob
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

    def get_current_palette(self):
        return [{'pos': blob['pos'], 'color': blob['color'], 'radius': blob['radius']} for blob in self.blobs]

    def load_palette(self, palette_data):
        self.blobs = [{'pos': QtCore.QPoint(b['pos']), 'color': QtGui.QColor(b['color']), 'radius': b['radius']} for b in palette_data]
        self.save_state()
        self.update()

class ColorHistoryWidget(QtWidgets.QWidget):
    """Widget that displays a history of recently used colors"""
    colorSelected = QtCore.Signal(QtGui.QColor)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.colors = []
        self.max_colors = 10
        self.setMinimumHeight(30)
        self.setMinimumWidth(100)
        
    def addColor(self, color):
        """Add a color to history, avoiding duplicates"""
        # Don't add if it's the same as the most recent color
        if self.colors and color.rgb() == self.colors[0].rgb():
            return
            
        # Add new color at the beginning
        self.colors.insert(0, QtGui.QColor(color))
        
        # Trim to max size
        if len(self.colors) > self.max_colors:
            self.colors.pop()
            
        self.update()
        
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        
        if not self.colors:
            # Draw empty state
            painter.setPen(QtGui.QPen(QtGui.QColor(180, 180, 180), 1))
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter, "No colors yet")
            return
            
        # Calculate swatch size
        width = self.width()
        height = self.height()
        count = len(self.colors)
        swatch_width = min(width / count if count > 0 else width, height * 1.5)
        
        # Draw color swatches
        for i, color in enumerate(self.colors):
            x = i * swatch_width
            rect = QtCore.QRectF(x, 0, swatch_width, height)
            
            # Draw color swatch
            painter.setPen(QtGui.QPen(QtGui.QColor(120, 120, 120), 1))
            painter.setBrush(QtGui.QBrush(color))
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
            
    def mousePressEvent(self, event):
        if not self.colors or event.button() != QtCore.Qt.LeftButton:
            return
            
        # Calculate which color was clicked
        width = self.width()
        count = len(self.colors)
        swatch_width = min(width / count if count > 0 else width, self.height() * 1.5)
        
        index = int(event.x() / swatch_width)
        if 0 <= index < len(self.colors):
            self.colorSelected.emit(self.colors[index])

# save multiple palettes
class SavedPaletteManagerWidget(QtWidgets.QWidget):
    paletteSelected = QtCore.Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.saved_palettes = []  # (name, palette_data)
        self.last_saved_index = None
        self.active_thumb = None  # Currently highlighted thumbnail
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setAlignment(QtCore.Qt.AlignTop)

        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QHBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(QtCore.Qt.AlignLeft)
        self.scroll_layout.setSpacing(8)
        self.scroll_area.setWidget(self.scroll_content)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll_area.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.scroll_area.setFixedHeight(80)  # Adjust height to fit your thumbnails

        self.layout.addWidget(self.scroll_area)

    def add_palette(self, name, palette_data, mark_as_latest=False):
        self.saved_palettes.append((name, palette_data))
        thumb = PaletteThumbnailWidget(name, palette_data)

        def emit_and_mark():
            self.mark_active_thumb(thumb)
            self.paletteSelected.emit(palette_data)

        thumb.clicked.connect(emit_and_mark)
        self.scroll_layout.addWidget(thumb)

        if mark_as_latest:
            self.last_saved_index = len(self.saved_palettes) - 1
            self.mark_active_thumb(thumb)
    
    def mark_active_thumb(self, thumb_widget):
        if self.active_thumb and self.active_thumb != thumb_widget:
            self.active_thumb.set_active(False)
        thumb_widget.set_active(True)
        self.active_thumb = thumb_widget
        
    def handle_thumb_clicked(self, thumb_widget, palette_data):
        self.mark_active_thumb(thumb_widget)
        self.paletteSelected.emit(palette_data)

    def update_last_saved(self, palette_data):
        if self.last_saved_index is not None:
            name, _ = self.saved_palettes[self.last_saved_index]
            self.saved_palettes[self.last_saved_index] = (name, palette_data)

            # Remove old thumbnail widget
            item = self.scroll_layout.itemAt(self.last_saved_index)
            if item is not None:
                old_thumb = item.widget()
                self.scroll_layout.removeWidget(old_thumb)
                old_thumb.setParent(None)
                old_thumb.deleteLater()

            # Create new updated thumbnail
            new_thumb = PaletteThumbnailWidget(name, palette_data)
            new_thumb.clicked.connect(lambda thumb_ref, data: self.handle_thumb_clicked(thumb_ref, data))

            # Insert it at the same index
            self.scroll_layout.insertWidget(self.last_saved_index, new_thumb)

            self.mark_active_thumb(new_thumb)


# multiple palette rendering thumbnails
class PaletteThumbnailWidget(QtWidgets.QFrame):
    clicked = QtCore.Signal(object, list)  # emit self + palette_data

    def __init__(self, name, palette_data, parent=None):
        super().__init__(parent)
        self.setFixedSize(50, 50)
        self.name = name
        self.palette_data = palette_data
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setStyleSheet("border: 1px solid #888;")
        self.setToolTip(f"Click to load palette: {name}")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit(self, self.palette_data)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Draw blobs scaled into thumbnail space
        for blob in self.palette_data:
            color = QtGui.QColor(blob['color'])
            painter.setBrush(QtGui.QBrush(color))
            painter.setPen(QtCore.Qt.NoPen)

            # Convert pos from full widget space (e.g., 400x400) to 90x90
            scale_factor = self.width() / 400.0
            pos = QtCore.QPointF(blob['pos']) * scale_factor
            radius = blob['radius'] * scale_factor
            painter.drawEllipse(pos, radius, radius)

        # Draw label
        painter.setPen(QtGui.QPen(QtCore.Qt.white))
        painter.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
        painter.drawText(5, 12, self.name)
    
    # highlights current palette user is working
    def set_active(self, is_active):
        if is_active:
            self.setStyleSheet("border: 2px solid white;")
        else:
            self.setStyleSheet("border: 1px solid #888;")


# Our ChroMaya GUI
class ChroMayaWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=get_maya_main_window()):
        super(ChroMayaWindow, self).__init__(parent)
        self.setWindowTitle("ChroMaya")
        self.setMinimumSize(600, 350)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        self.build_ui(central_widget)
        self.selected_colors = []

        # Automatically open 3D Paint Tool settings on plugin launch
        if not cmds.art3dPaintCtx('art3dPaintContext', exists=True):
            cmds.art3dPaintCtx('art3dPaintContext', t='art3dPaintCtx')

        cmds.setToolTo('art3dPaintContext')
        cmds.ToolSettingsWindow()


    def build_ui(self, parent_widget):
        layout = QtWidgets.QVBoxLayout(parent_widget)

        # Title
        title_label = QtWidgets.QLabel("ChroMaya")
        title_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        title_label.setAlignment(QtCore.Qt.AlignLeft)
        layout.addWidget(title_label)

        # Horizontal layout for left/right panels
        content_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(content_layout)

        # === LEFT PANEL ===
        left_panel = QtWidgets.QVBoxLayout()
        content_layout.addLayout(left_panel, 1)

        import_mesh_btn = QtWidgets.QPushButton("Import Paintable Mesh")
        import_mesh_btn.clicked.connect(self.import_paintable_mesh)
        left_panel.addWidget(import_mesh_btn)

        # Add Color Blobs Section
        color_instructions = QtWidgets.QLabel("Click anywhere on the mixing dish to add a\ncolor blob!")
        color_instructions.setStyleSheet("font-size: 10px; color: #888;")
        left_panel.addWidget(color_instructions)

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
        swatch_instructions.setStyleSheet("font-size: 10px; color: #888;")
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

        # === Color History ===
        history_label = QtWidgets.QLabel("Color History:")
        history_label.setStyleSheet("font-weight: bold; margin-top: 1px;")
        left_panel.addWidget(history_label)
        
        # Add color history widget
        self.color_history = ColorHistoryWidget()
        self.color_history.colorSelected.connect(self.handle_history_color_selected)
        self.color_history.setFixedHeight(30)
        left_panel.addWidget(self.color_history)

        # === Divider Line ===
        divider = QtWidgets.QFrame()
        divider.setFrameShape(QtWidgets.QFrame.HLine)
        divider.setFrameShadow(QtWidgets.QFrame.Sunken)
        left_panel.addWidget(divider)

        # === Palette History ===
        undo_redo_layout = QtWidgets.QHBoxLayout()
        palette_history_label = QtWidgets.QLabel("Palette History:")
        palette_history_label.setStyleSheet("font-weight: bold; margin-top: 1px;")
        left_panel.addWidget(palette_history_label)

        undo_button = QtWidgets.QPushButton("Undo")
        undo_button.setToolTip("Undo last palette change")
        undo_button.clicked.connect(self.undo_palette)
        undo_redo_layout.addWidget(undo_button)
        
        redo_button = QtWidgets.QPushButton("Redo")
        redo_button.setToolTip("Redo last undone palette change")
        redo_button.clicked.connect(self.redo_palette)
        undo_redo_layout.addWidget(redo_button)
        
        left_panel.addLayout(undo_redo_layout)

        # multiple palettes
        self.save_as_new_palette_btn = QtWidgets.QPushButton("Save As New Palette")
        self.save_as_new_palette_btn.clicked.connect(self.save_as_new_palette)
        left_panel.addWidget(self.save_as_new_palette_btn)

        self.save_palette_btn = QtWidgets.QPushButton("Save Palette")
        self.save_palette_btn.clicked.connect(self.save_current_palette)
        self.save_palette_btn.setEnabled(False)  # initially disabled
        left_panel.addWidget(self.save_palette_btn)

        # palette thumbnails
        self.saved_palette_manager = SavedPaletteManagerWidget()
        self.saved_palette_manager.paletteSelected.connect(self.load_saved_palette)
        left_panel.addWidget(self.saved_palette_manager)

        # === RIGHT PANEL (Mixing Dish) ===
        right_panel = QtWidgets.QVBoxLayout()
        content_layout.addLayout(right_panel, 2)

        self.mixing_dish = MixingDishWidget()
        self.mixing_dish.colorSelected.connect(self.set_maya_brush_color)
        self.mixing_dish.colorSelected.connect(self.handle_mixing_dish_color)
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

    def handle_history_color_selected(self, color):
        """Handle when a color is selected from the history"""
        self.handle_mixing_dish_color(color)
        om.MGlobal.displayInfo(f"ChroMaya: Selected color from history: {color.name()}")
        
    def handle_mixing_dish_color(self, color):
        """Handle when a color is selected from mixing dish"""
        self.color_preview.setStyleSheet(
            f"background-color: {color.name()}; border: 1px solid #aaa;"
        )
        self.color_history.addColor(color)
        self.set_maya_brush_color(color)

    def undo_palette(self):
        """Undo last palette action"""
        success = self.mixing_dish.undo()
        if success:
            om.MGlobal.displayInfo("ChroMaya: Undid last palette action")
        else:
            om.MGlobal.displayInfo("ChroMaya: Nothing to undo")

    def redo_palette(self):
        """Redo last undone palette action"""
        success = self.mixing_dish.redo()
        if success:
            om.MGlobal.displayInfo("ChroMaya: Redid last palette action")
        else:
            om.MGlobal.displayInfo("ChroMaya: Nothing to redo")

    def save_current_palette(self):
        palette = self.mixing_dish.get_current_palette()
        self.saved_palette_manager.update_last_saved(palette)
        om.MGlobal.displayInfo("ChroMaya: Updated last saved palette ✅")

    def save_as_new_palette(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "Save As New Palette", "Enter a name for this palette:")
        if ok and name:
            palette = self.mixing_dish.get_current_palette()
            self.saved_palette_manager.add_palette(name, palette, mark_as_latest=True)
            self.save_palette_btn.setEnabled(True)
            om.MGlobal.displayInfo(f"ChroMaya: Saved new palette '{name}' ✅")

    def load_saved_palette(self, palette_data):
        self.mixing_dish.load_palette(palette_data)
        om.MGlobal.displayInfo("ChroMaya: Loaded saved palette")

    def import_paintable_mesh(self):
        # 1. Open file dialog
        mesh_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import Mesh", "", "3D Files (*.obj *.fbx *.ma)")
        if not mesh_path:
            return

        # 2. Import mesh at origin
        before_import = set(cmds.ls(geometry=True))
        cmds.file(mesh_path, i=True, ignoreVersion=True, ra=True, mergeNamespacesOnClash=False, namespace="chroMesh", options="mo=1", pr=True)
        after_import = set(cmds.ls(geometry=True))
        new_meshes = list(after_import - before_import)
        if not new_meshes:
            om.MGlobal.displayError("No geometry found in import.")
            return

        mesh = new_meshes[0]
        cmds.select(mesh)
        cmds.move(0, 0, 0, mesh)

        # 3. Create new shader and file texture
        shader = cmds.shadingNode('lambert', asShader=True, name="chroShader")
        shading_group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="chroSG")
        cmds.connectAttr(f"{shader}.outColor", f"{shading_group}.surfaceShader", force=True)

        file_node = cmds.shadingNode('file', asTexture=True, name="chroFileTexture")
        place2d = cmds.shadingNode('place2dTexture', asUtility=True)
        cmds.connectAttr(f"{place2d}.outUV", f"{file_node}.uvCoord")
        cmds.connectAttr(f"{place2d}.outUvFilterSize", f"{file_node}.uvFilterSize")

        # 4. Create temp texture file
        texture_path = cmds.workspace(q=True, rd=True) + "images/chroTempTexture.png"
        if not os.path.exists(os.path.dirname(texture_path)):
            os.makedirs(os.path.dirname(texture_path))
        image = QtGui.QImage(1024, 1024, QtGui.QImage.Format_RGB32)
        image.fill(QtGui.QColor("white"))
        image.save(texture_path)

        cmds.setAttr(f"{file_node}.fileTextureName", texture_path, type="string")
        cmds.connectAttr(f"{file_node}.outColor", f"{shader}.color")

        # 5. Assign material to mesh
        cmds.select(mesh)
        cmds.hyperShade(assign=shader)

        # Force set mesh to show texture
        cmds.polyOptions(mesh, colorShadedDisplay=True)
        cmds.setAttr(mesh + ".displayColors", 1)

        # Set up 3D Paint Context
        if not cmds.art3dPaintCtx('art3dPaintContext', exists=True):
            cmds.art3dPaintCtx('art3dPaintContext', t='art3dPaintCtx')

        # Activate paint tool
        cmds.setToolTo('art3dPaintContext')

        # Now explicitly assign the mesh and its file texture to the paint context
        cmds.art3dPaintCtx('art3dPaintContext', edit=True,
            selProj=True,
            paintMode="attrib",
            colorMode="diffuse",  # or 'combined' if needed
            assignFile=True,
            targetSurfaces=mesh,
            fileTextures=[file_node],  # needs name of the file texture node
        )

        # 6. Connect texture to the 3D Paint Tool
        cmds.select(mesh)
        cmds.art3dPaintCtx('art3dPaintContext', edit=True, 
                        colorMode='diffuse',
                        paintTexture=texture_path)

        om.MGlobal.displayInfo(f"ChroMaya: Imported and prepared {mesh} for painting 🎨")

        # Open the 3D Paint Tool panel
        cmds.ToolSettingsWindow()
        cmds.setToolTo('art3dPaintContext')


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
       #self.window.show()

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

def show_chromaya_dock():
    import maya.cmds as cmds
    from maya import OpenMayaUI as omui
    from shiboken2 import wrapInstance
    from PySide2 import QtWidgets

    dock_name = "ChroMayaDockable"

    # Step 1: Safely remove old dock if it exists
    if cmds.workspaceControl(dock_name, q=True, exists=True):
        try:
            cmds.deleteUI(dock_name, control=True)
        except:
            cmds.deleteUI(dock_name)
        try:
            cmds.workspaceControlState(dock_name, remove=True)
        except:
            pass

    # Step 2: Create the workspaceControl FIRST (empty container)
    cmds.workspaceControl(dock_name,
                          label="ChroMaya",
                          retain=False,
                          loadImmediately=True)

    # Step 3: Find the workspaceControl's Qt widget
    from maya.OpenMayaUI import MQtUtil
    from shiboken2 import wrapInstance
    from PySide2.QtWidgets import QWidget

    control_ptr = MQtUtil.findControl(dock_name)
    if control_ptr is None:
        print("Error: Could not find dock control.")
        return

    dock_qwidget = wrapInstance(int(control_ptr), QWidget)

    # Step 4: Add your custom widget (AFTER dock exists!)
    plugin_widget = ChroMayaWindow()
    plugin_widget.setObjectName("ChroMayaUI")
    dock_qwidget.layout().addWidget(plugin_widget)

