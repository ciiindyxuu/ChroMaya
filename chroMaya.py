import sys
import maya.api.OpenMaya as om
from maya import OpenMayaUI as omui
import maya.cmds as cmds
from PySide2 import QtWidgets, QtCore, QtGui
from shiboken2 import wrapInstance
import numpy as np
import json
import os

plugin_name = "chroMayaUI"

def maya_useNewAPI():
   pass

# Get Maya main window
def get_maya_main_window():
   main_window_ptr = omui.MQtUtil.mainWindow()
   return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)

# adding state persistence functions
def get_state_file_path():
    """Get the path to the state file"""
    maya_app_dir = cmds.internalVar(userAppDir=True)
    state_dir = os.path.join(maya_app_dir, "chroMaya")
    if not os.path.exists(state_dir):
        os.makedirs(state_dir)
    return os.path.join(state_dir, "chroMaya_state.json")

def serialize_point(point):
    """Convert QPoint to serializable dict"""
    return {'x': point.x(), 'y': point.y()}

def serialize_color(color):
    """Convert QColor to serializable string"""
    return color.name()

def serialize_palette_data(palette_data):
    """Convert palette data to serializable format"""
    serialized = []
    for blob in palette_data:
        serialized.append({
            'pos': serialize_point(blob['pos']),
            'color': serialize_color(blob['color']),
            'radius': blob['radius']
        })
    return serialized

def save_state(palettes, color_history):
    """Save the current state to a file"""
    # Convert QPoint objects to dictionaries
    serializable_palettes = []
    for palette in palettes:
        serializable_palette = {
            'name': palette['name'],
            'palette_data': []
        }
        for blob in palette['palette_data']:
            # Handle pos being either a QPoint/QPointF or a dict with x, y
            pos_dict = {}
            pos = blob['pos']
            if isinstance(pos, (QtCore.QPoint, QtCore.QPointF)):
                pos_dict = {'x': pos.x(), 'y': pos.y()}
            elif isinstance(pos, dict) and 'x' in pos and 'y' in pos:
                pos_dict = {'x': pos['x'], 'y': pos['y']}
            else:
                om.MGlobal.displayWarning(f"ChroMaya: Unsupported position format in save_state")
                continue  # Skip this blob if position format is invalid
                
            # Handle color being either a QColor or a string
            color_str = ""
            if isinstance(blob['color'], QtGui.QColor):
                color_str = blob['color'].name()
            else:
                color_str = str(blob['color'])
                
            serializable_blob = {
                'pos': pos_dict,
                'color': color_str,
                'radius': blob['radius']
            }
            serializable_palette['palette_data'].append(serializable_blob)
        serializable_palettes.append(serializable_palette)
    
    # Handle color history - convert QColor objects to strings
    serialized_color_history = []
    for color in color_history:
        if isinstance(color, QtGui.QColor):
            serialized_color_history.append(color.name())
        else:
            # Handle case where color might already be a string
            serialized_color_history.append(str(color))
    
    state = {
        'palettes': serializable_palettes,
        'color_history': serialized_color_history
    }
    
    try:
        state_path = get_state_file_path()
        with open(state_path, 'w') as f:
            json.dump(state, f)
        om.MGlobal.displayInfo(f"ChroMaya: State saved successfully to {state_path}")
    except Exception as e:
        om.MGlobal.displayError(f"ChroMaya: Failed to save state: {e}")

def deserialize_point(point_dict):
    """Convert serialized point dict back to QPoint"""
    return QtCore.QPoint(point_dict['x'], point_dict['y'])

def deserialize_color(color_str):
    """Convert serialized color string back to QColor"""
    return QtGui.QColor(color_str)

def deserialize_palette_data(palette_data):
    """Convert serialized palette data back to original format"""
    deserialized = []
    for blob in palette_data:
        deserialized.append({
            'pos': deserialize_point(blob['pos']),
            'color': deserialize_color(blob['color']),
            'radius': blob['radius']
        })
    return deserialized

def load_state():
    """Load the state from file"""
    try:
        state_path = get_state_file_path()
        if os.path.exists(state_path):
            with open(state_path, 'r') as f:
                state = json.load(f)
            return state
    except Exception as e:
        om.MGlobal.displayError(f"ChroMaya: Failed to load state: {e}")
    return None

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
        """Load palette data, handling different possible formats"""
        try:
            self.blobs = []
            for b in palette_data:
                blob = {}
                # Handle pos being either a QPoint/QPointF or a dict with x, y
                if isinstance(b['pos'], (QtCore.QPoint, QtCore.QPointF)):
                    blob['pos'] = QtCore.QPoint(b['pos'])
                elif isinstance(b['pos'], dict) and 'x' in b['pos'] and 'y' in b['pos']:
                    blob['pos'] = QtCore.QPoint(b['pos']['x'], b['pos']['y'])
                else:
                    continue  # Skip this blob if pos is invalid
                
                # Handle color being either a QColor or a string
                if isinstance(b['color'], QtGui.QColor):
                    blob['color'] = QtGui.QColor(b['color'])
                else:
                    blob['color'] = QtGui.QColor(b['color'])
                
                blob['radius'] = b['radius']
                self.blobs.append(blob)
            
            self.save_state()
            self.update()
        except Exception as e:
            om.MGlobal.displayError(f"ChroMaya: Failed to load palette: {e}")

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
    paletteSelected = QtCore.Signal(list)  # Emitted with palette data when a palette is selected
    paletteDeleted = QtCore.Signal(str, bool)  # Emitted with (palette_name, should_clear_mixing_dish) when deleted
    newPaletteRequested = QtCore.Signal()  # Emitted when the new palette button is clicked

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
        self.scroll_area.setFixedHeight(110)  # Adjust height to fit your thumbnails

        self.layout.addWidget(self.scroll_area)
        
        # Add the "New Palette" button
        self.add_new_palette_button()

    def add_new_palette_button(self):
        """Add the "+" button for creating a new palette at the end of the list"""
        self.new_palette_btn = NewPaletteButton()
        self.new_palette_btn.clicked.connect(self.request_new_palette)
        self.scroll_layout.addWidget(self.new_palette_btn)
        
    def request_new_palette(self):
        """Emit signal to request a new palette creation"""
        self.newPaletteRequested.emit()

    def add_palette(self, name, palette_data, mark_as_latest=False):
        try:
            # Validate palette data
            if not isinstance(palette_data, list):
                om.MGlobal.displayWarning(f"ChroMaya: Invalid palette data format for '{name}'")
                return

            # Remove the new palette button temporarily
            self.scroll_layout.removeWidget(self.new_palette_btn)
            self.new_palette_btn.setParent(None)

            self.saved_palettes.append((name, palette_data))
            thumb = PaletteThumbnailWidget(name, palette_data)

            def emit_and_mark():
                try:
                    self.mark_active_thumb(thumb)
                    self.paletteSelected.emit(palette_data)
                except Exception as e:
                    om.MGlobal.displayError(f"ChroMaya: Error selecting palette: {e}")

            thumb.clicked.connect(emit_and_mark)
            
            # Connect delete signal
            thumb.delete_requested.connect(lambda t=thumb: self.delete_palette(t))
            
            self.scroll_layout.addWidget(thumb)
            
            # Add the new palette button back at the end
            self.scroll_layout.addWidget(self.new_palette_btn)

            if mark_as_latest:
                self.last_saved_index = len(self.saved_palettes) - 1
                self.mark_active_thumb(thumb)
        except Exception as e:
            om.MGlobal.displayError(f"ChroMaya: Failed to add palette: {e}")
            # Ensure the new palette button is always added back
            if self.new_palette_btn.parent() is None:
                self.scroll_layout.addWidget(self.new_palette_btn)

    def delete_palette(self, thumb_widget):
        """Delete a palette thumbnail"""
        try:
            # Confirm deletion with a dialog
            result = QtWidgets.QMessageBox.question(
                self,
                "Delete Palette",
                f"Are you sure you want to delete the palette '{thumb_widget.name}'?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            
            if result == QtWidgets.QMessageBox.Yes:
                # Find the index in the layout
                for i in range(self.scroll_layout.count()):
                    # Skip the new palette button (which is always the last widget)
                    if i == self.scroll_layout.count() - 1:
                        continue
                        
                    if self.scroll_layout.itemAt(i).widget() == thumb_widget:
                        # Check if this is the active palette
                        was_active = (self.active_thumb == thumb_widget)
                        
                        # Remove from saved_palettes list
                        palette_name = thumb_widget.name
                        if i < len(self.saved_palettes):
                            self.saved_palettes.pop(i)
                        
                        # Remove from layout and delete
                        self.scroll_layout.removeWidget(thumb_widget)
                        thumb_widget.setParent(None)
                        thumb_widget.deleteLater()
                        
                        # Adjust last_saved_index if needed
                        if self.last_saved_index is not None:
                            if i == self.last_saved_index:
                                self.last_saved_index = None  # No "last saved" anymore
                            elif i < self.last_saved_index:
                                self.last_saved_index -= 1  # Adjust index
                        
                        # Handle active palette changes
                        if was_active:
                            self.active_thumb = None
                            
                            # Try to select next palette if available
                            count = self.scroll_layout.count() - 1  # Exclude the new palette button
                            next_palette = None
                            
                            if count > 0:
                                # Try to get the palette at the same index (or the last one if index was the last)
                                next_index = min(i, count - 1)
                                next_palette = self.scroll_layout.itemAt(next_index).widget()
                                
                                if next_palette and next_palette != self.new_palette_btn:
                                    # Set this palette as active
                                    self.mark_active_thumb(next_palette)
                                    # Emit signal to load this palette
                                    self.paletteSelected.emit(next_palette.palette_data)
                            
                            # If no palette was found or selected, emit a signal to clear the mixing dish
                            if not next_palette or next_palette == self.new_palette_btn:
                                # Emit signal that palette was deleted with no replacement
                                self.paletteDeleted.emit(palette_name, True)
                        else:
                            # Just emit the regular deleted signal
                            self.paletteDeleted.emit(palette_name, False)
                        
                        om.MGlobal.displayInfo(f"ChroMaya: Deleted palette '{palette_name}'")
                        return
                
                om.MGlobal.displayWarning(f"ChroMaya: Could not find palette in layout to delete")
        except Exception as e:
            om.MGlobal.displayError(f"ChroMaya: Error deleting palette: {e}")
    
    def mark_active_thumb(self, thumb_widget):
        try:
            if self.active_thumb and self.active_thumb != thumb_widget:
                self.active_thumb.set_active(False)
            thumb_widget.set_active(True)
            self.active_thumb = thumb_widget
        except Exception as e:
            om.MGlobal.displayError(f"ChroMaya: Error marking active thumbnail: {e}")
        
    def handle_thumb_clicked(self, thumb_widget, palette_data):
        try:
            self.mark_active_thumb(thumb_widget)
            self.paletteSelected.emit(palette_data)
        except Exception as e:
            om.MGlobal.displayError(f"ChroMaya: Error handling thumbnail click: {e}")

    def update_last_saved(self, palette_data):
        try:
            if self.last_saved_index is not None and 0 <= self.last_saved_index < len(self.saved_palettes):
                name, _ = self.saved_palettes[self.last_saved_index]
                self.saved_palettes[self.last_saved_index] = (name, palette_data)

                # Remove old thumbnail widget
                item = self.scroll_layout.itemAt(self.last_saved_index)
                if item is not None:
                    old_thumb = item.widget()
                    if old_thumb:
                        self.scroll_layout.removeWidget(old_thumb)
                        old_thumb.setParent(None)
                        old_thumb.deleteLater()

                # Create new updated thumbnail
                new_thumb = PaletteThumbnailWidget(name, palette_data)

                def handle_click():
                    try:
                        self.handle_thumb_clicked(new_thumb, palette_data)
                    except Exception as e:
                        om.MGlobal.displayError(f"ChroMaya: Error in thumbnail click handler: {e}")

                new_thumb.clicked.connect(handle_click)
                
                # Connect delete signal
                new_thumb.delete_requested.connect(lambda t=new_thumb: self.delete_palette(t))

                # Insert it at the same index
                self.scroll_layout.insertWidget(self.last_saved_index, new_thumb)
                self.mark_active_thumb(new_thumb)
            else:
                om.MGlobal.displayWarning("ChroMaya: Cannot update palette - invalid index")
        except Exception as e:
            om.MGlobal.displayError(f"ChroMaya: Failed to update palette: {e}")

# multiple palette rendering thumbnails
class PaletteThumbnailWidget(QtWidgets.QFrame):
    clicked = QtCore.Signal(object, list)  # emit self + palette_data
    delete_requested = QtCore.Signal(object)  # emit self for deletion


    def __init__(self, name, palette_data, parent=None):
        super().__init__(parent)
        self.setFixedSize(70, 70)
        self.name = name
        
        # Validate palette data
        try:
            if not isinstance(palette_data, list):
                om.MGlobal.displayWarning(f"ChroMaya: Invalid palette data format for '{name}'")
                self.palette_data = []
            else:
                # Safely store palette data
                self.palette_data = palette_data
        except Exception as e:
            om.MGlobal.displayError(f"ChroMaya: Error initializing palette thumbnail: {e}")
            self.palette_data = []
        
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setStyleSheet("border: 1px solid #888;")
        self.setToolTip(f"Click to load palette: {name}\nClick on 'X' to delete")
        
        # Track mouse hover state for showing delete button
        self.mouse_over = False
        self.delete_hover = False
        self.setMouseTracking(True)  # Enable tracking mouse movements

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            # Check if click is in the delete button area (top-left corner)
            if self.delete_button_rect().contains(event.pos()) and self.mouse_over:
                self.delete_requested.emit(self)
            else:
                self.clicked.emit(self, self.palette_data)

    def delete_button_rect(self):
        """Return the rectangle for the delete button"""
        return QtCore.QRect(0, 0, 16, 16)
                
    def enterEvent(self, event):
        self.mouse_over = True
        self.update()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self.mouse_over = False
        self.delete_hover = False
        self.update()
        super().leaveEvent(event)
        
    def mouseMoveEvent(self, event):
        # Update delete_hover state based on mouse position
        prev_hover = self.delete_hover
        self.delete_hover = self.delete_button_rect().contains(event.pos())
        if prev_hover != self.delete_hover:
            self.update()  # Repaint if hover state changed
        super().mouseMoveEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Draw blobs scaled into thumbnail space
        try:
            for blob in self.palette_data:
                try:
                    # Handle color
                    if isinstance(blob.get('color'), QtGui.QColor):
                        color = blob['color']
                    else:
                        color = QtGui.QColor(blob.get('color', '#FF0000'))  # Default to red if missing
                        
                    painter.setBrush(QtGui.QBrush(color))
                    painter.setPen(QtCore.Qt.NoPen)
    
                    # Handle position - safely extract QPoint or dict
                    pos_obj = blob.get('pos')
                    if isinstance(pos_obj, (QtCore.QPoint, QtCore.QPointF)):
                        x, y = pos_obj.x(), pos_obj.y()
                    elif isinstance(pos_obj, dict) and 'x' in pos_obj and 'y' in pos_obj:
                        x, y = pos_obj['x'], pos_obj['y']
                    else:
                        continue  # Skip this blob if position is invalid
    
                    # Convert pos from full widget space (e.g., 400x400) to thumbnail size
                    scale_factor = self.width() / 400.0
                    pos = QtCore.QPointF(x * scale_factor, y * scale_factor)
                    
                    # Get radius with fallback
                    radius = blob.get('radius', 30) * scale_factor
                    
                    # Draw the blob
                    painter.drawEllipse(pos, radius, radius)
                except Exception as e:
                    om.MGlobal.displayError(f"ChroMaya: Error drawing blob: {e}")
                    continue  # Skip to next blob on error
        except Exception as e:
            om.MGlobal.displayError(f"ChroMaya: Error in thumbnail rendering: {e}")

        # Draw label
        try:
            painter.setPen(QtGui.QPen(QtCore.Qt.white))
            painter.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            painter.drawText(5, 12, self.name)
        except Exception as e:
            om.MGlobal.displayError(f"ChroMaya: Error drawing thumbnail label: {e}")
            
        # Draw delete button when mouse is over the widget
        if self.mouse_over:
            delete_rect = self.delete_button_rect()
            
            # Draw delete button background
            if self.delete_hover:
                painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0, 200)))  # Bright red when hovering
            else:
                painter.setBrush(QtGui.QBrush(QtGui.QColor(200, 0, 0, 170)))  # Darker red normally
                
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRect(delete_rect)
            
            # Draw X
            painter.setPen(QtGui.QPen(QtCore.Qt.white, 2))
            margin = 4
            painter.drawLine(
                delete_rect.left() + margin, 
                delete_rect.top() + margin,
                delete_rect.right() - margin, 
                delete_rect.bottom() - margin
            )
            painter.drawLine(
                delete_rect.right() - margin, 
                delete_rect.top() + margin,
                delete_rect.left() + margin, 
                delete_rect.bottom() - margin
            )
    
    # highlights current palette user is working
    def set_active(self, is_active):
        if is_active:
            self.setStyleSheet("border: 2px solid white;")
        else:
            self.setStyleSheet("border: 1px solid #888;")

class NewPaletteButton(QtWidgets.QFrame):
    """Button to create a new empty palette"""
    clicked = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(70, 70)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setStyleSheet("""
            QFrame {
                border: 1px dashed #888;
                border-radius: 4px;
                background-color: rgba(80, 80, 80, 50);
            }
            QFrame:hover {
                border: 2px dashed #aaa;
                background-color: rgba(100, 100, 100, 80);
            }
        """)
        self.setToolTip("Create a new empty palette")
        
        # Mouse hover state
        self.mouse_over = False
        self.setMouseTracking(True)

    def enterEvent(self, event):
        self.mouse_over = True
        self.update()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self.mouse_over = False
        self.update()
        super().leaveEvent(event)
        
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
            
    def paintEvent(self, event):
        super().paintEvent(event)
        
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Draw plus sign
        pen_width = 3 if self.mouse_over else 2
        plus_color = QtGui.QColor(230, 230, 230) if self.mouse_over else QtGui.QColor(200, 200, 200)
        
        painter.setPen(QtGui.QPen(plus_color, pen_width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        
        # Calculate center and size of plus
        center_x = self.width() / 2
        center_y = self.height() / 2
        plus_size = min(self.width(), self.height()) * 0.35
        
        # Draw horizontal line
        painter.drawLine(
            QtCore.QPointF(center_x - plus_size, center_y),
            QtCore.QPointF(center_x + plus_size, center_y)
        )
        
        # Draw vertical line
        painter.drawLine(
            QtCore.QPointF(center_x, center_y - plus_size),
            QtCore.QPointF(center_x, center_y + plus_size)
        )
        
        # Add "New" text below the plus sign
        if self.mouse_over:
            painter.setPen(plus_color)
            painter.setFont(QtGui.QFont("Arial", 9, QtGui.QFont.Bold))
            painter.drawText(
                QtCore.QRectF(0, center_y + plus_size + 5, self.width(), 20),
                QtCore.Qt.AlignHCenter,
                "New"
            )

# Our ChroMaya GUI
class ChroMayaWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=get_maya_main_window()):
        super(ChroMayaWindow, self).__init__(parent)
        self.setWindowTitle("ChroMaya")
        self.setMinimumSize(700, 500)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        self.build_ui(central_widget)
        self.selected_colors = []
        
        # Don't load saved state automatically - user should import manually
        # self.load_saved_state()
        
        # Set up auto-save timer
        self.auto_save_timer = QtCore.QTimer(self)
        self.auto_save_timer.timeout.connect(self.auto_save_state)
        self.auto_save_timer.start(300000)  # Auto-save every 5 minutes

    def auto_save_state(self):
        """Auto-save the current state"""
        palettes = []
        for i in range(self.saved_palette_manager.scroll_layout.count()):
            thumb = self.saved_palette_manager.scroll_layout.itemAt(i).widget()
            if thumb:
                palettes.append({
                    'name': thumb.name,
                    'palette_data': thumb.palette_data
                })
        
        color_history = self.color_history.colors
        save_state(palettes, color_history)
        
    def load_saved_state_from_default(self):
        """Manually load the saved state from the default location"""
        try:
            # Get the default state file path
            state_path = get_state_file_path()
            if not os.path.exists(state_path):
                om.MGlobal.displayWarning(f"ChroMaya: No saved state found at {state_path}")
                return
                
            # Load the state file
            with open(state_path, 'r') as f:
                state = json.load(f)
                
            # Clear current palettes
            while self.saved_palette_manager.scroll_layout.count():
                item = self.saved_palette_manager.scroll_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                    
            # Clear color history
            self.color_history.colors.clear()
                
            # Process the loaded state
            try:
                # Load palettes
                for i, palette in enumerate(state.get('palettes', [])):
                    self.saved_palette_manager.add_palette(
                        palette['name'],
                        palette['palette_data'],
                        mark_as_latest=(i == 0)  # Mark the first palette as latest
                    )
                
                # Set the last_saved_index to the first palette
                if state.get('palettes'):
                    self.saved_palette_manager.last_saved_index = 0
                
                # Load color history
                for color_name in state.get('color_history', []):
                    color = QtGui.QColor(color_name)
                    if color.isValid():
                        self.color_history.addColor(color)
                
                # Update the mixing dish with the first palette if available
                if state.get('palettes'):
                    first_palette = state['palettes'][0]['palette_data']
                    self.mixing_dish.load_palette(first_palette)
                    
                    # Enable the Save Current Palette button if we loaded any palettes
                    if len(state.get('palettes')) > 0:
                        self.save_palette_btn.setEnabled(True)
                
                om.MGlobal.displayInfo(f"ChroMaya: State loaded successfully from {state_path}")
            except Exception as e:
                om.MGlobal.displayError(f"ChroMaya: Error processing loaded state: {e}")
        except Exception as e:
            om.MGlobal.displayError(f"ChroMaya: Error loading saved state: {e}")

    def closeEvent(self, event):
        """Save state when window is closed"""
        self.auto_save_state()
        super().closeEvent(event)

    def build_ui(self, parent_widget):
        layout = QtWidgets.QVBoxLayout(parent_widget)

        # Title and Save Button Layout
        title_layout = QtWidgets.QHBoxLayout()
        
        # Title
        title_label = QtWidgets.QLabel("ChroMaya")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        title_layout.addWidget(title_label)
        
        # Add spacer to push buttons to the right
        title_layout.addStretch()
        
        # Import Palettes Button with context menu
        self.import_palettes_btn = QtWidgets.QPushButton("Import Palettes")
        self.import_palettes_btn.setToolTip("Import palettes and merge with existing ones")
        self.import_palettes_btn.clicked.connect(self.import_state)
        self.import_palettes_btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.import_palettes_btn.customContextMenuRequested.connect(self.show_import_menu)
        self.import_palettes_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                margin-right: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
        """)
        
        # Export Palette Button
        self.export_palette_btn = QtWidgets.QPushButton("Export Palette")
        self.export_palette_btn.setToolTip("Export the currently active palette")
        self.export_palette_btn.clicked.connect(self.export_active_palette)
        self.export_palette_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        
        title_layout.addWidget(self.import_palettes_btn)
        title_layout.addWidget(self.export_palette_btn)

        layout.addLayout(title_layout)

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

        color_instructions = QtWidgets.QLabel("Click anywhere on the mixing dish to add a\ncolor blob")
        color_instructions.setStyleSheet("font-size: 10px; color: #666;")
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
        palette_history_label = QtWidgets.QLabel("Palette History")
        palette_history_label.setStyleSheet("font-weight: bold; margin-top: 1px;")
        left_panel.addWidget(palette_history_label)

        undo_button = QtWidgets.QPushButton("Undo Mixing Dish Action")
        undo_button.setToolTip("Undo last palette change")
        undo_button.clicked.connect(self.undo_palette)
        
        redo_button = QtWidgets.QPushButton("Redo Mixing Dish Action")
        redo_button.setToolTip("Redo last undone palette change")
        redo_button.clicked.connect(self.redo_palette)
        
        left_panel.addWidget(undo_button)
        left_panel.addWidget(redo_button)

        # multiple palettes
        self.save_as_new_palette_btn = QtWidgets.QPushButton("Save As New Palette")
        self.save_as_new_palette_btn.clicked.connect(self.save_as_new_palette)
        left_panel.addWidget(self.save_as_new_palette_btn)

        self.save_palette_btn = QtWidgets.QPushButton("Save Current Palette")
        self.save_palette_btn.clicked.connect(self.save_current_palette)
        self.save_palette_btn.setEnabled(False)  # initially disabled
        left_panel.addWidget(self.save_palette_btn)

        # palette thumbnails
        self.saved_palette_manager = SavedPaletteManagerWidget()
        self.saved_palette_manager.paletteSelected.connect(self.load_saved_palette)
        self.saved_palette_manager.paletteDeleted.connect(self.handle_palette_deleted)
        self.saved_palette_manager.newPaletteRequested.connect(self.create_new_palette)
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
            
    def create_new_palette(self):
        """Handle the signal when a new palette is requested from the + button
        
        This creates a new empty palette and selects it
        """
        # Clear the mixing dish for a fresh start
        self.clear_mixing_dish()
        
        # Ask for a palette name (with "New Palette" as default)
        name, ok = QtWidgets.QInputDialog.getText(
            self, 
            "New Palette", 
            "Enter a name for this palette:",
            text="New Palette"
        )
        
        if not ok:
            return  # User cancelled
            
        # Use default name if user didn't enter anything
        if not name.strip():
            name = "New Palette"
        
        # Add the new palette
        self.saved_palette_manager.add_palette(
            name,
            [],  # Empty palette data
            mark_as_latest=True
        )
        
        # Enable the save button
        self.save_palette_btn.setEnabled(True)
        
        om.MGlobal.displayInfo(f"ChroMaya: Created new empty palette '{name}'")
        
        # Prompt the user with a tooltip
        QtWidgets.QToolTip.showText(
            QtGui.QCursor.pos(),
            "Click on the mixing dish to add color blobs to your new palette",
            self
        )

    def load_saved_palette(self, palette_data):
        """Load a saved palette into the mixing dish"""
        try:
            self.mixing_dish.load_palette(palette_data)
            om.MGlobal.displayInfo("ChroMaya: Loaded saved palette")
        except Exception as e:
            om.MGlobal.displayError(f"ChroMaya: Error loading palette: {e}")
            
    def clear_mixing_dish(self):
        """Clear the mixing dish of all blobs"""
        self.mixing_dish.blobs = []
        self.mixing_dish.save_state()  # Save empty state to history
        self.mixing_dish.update()
        om.MGlobal.displayInfo("ChroMaya: Mixing dish cleared")

    def handle_palette_deleted(self, palette_name, should_clear_mixing_dish=False):
        """Handle when a palette is deleted
        
        Args:
            palette_name (str): The name of the deleted palette
            should_clear_mixing_dish (bool): Whether the mixing dish should be cleared
        """
        # Auto-save the state after deletion
        self.auto_save_state()
        
        # Check if any palettes remain, if not, disable save button
        if self.saved_palette_manager.scroll_layout.count() == 0:
            self.save_palette_btn.setEnabled(False)
        
        # Clear mixing dish if requested or no palettes remain
        if should_clear_mixing_dish or self.saved_palette_manager.scroll_layout.count() == 0:
            self.clear_mixing_dish()
            om.MGlobal.displayInfo(f"ChroMaya: Palette '{palette_name}' deleted and mixing dish cleared")

    def manual_save_state(self):
        """Save the current state (used for auto-save)"""
        try:
            palettes = []
            for i in range(self.saved_palette_manager.scroll_layout.count()):
                try:
                    thumb = self.saved_palette_manager.scroll_layout.itemAt(i).widget()
                    if thumb:
                        palettes.append({
                            'name': thumb.name,
                            'palette_data': thumb.palette_data
                        })
                except Exception as e:
                    om.MGlobal.displayWarning(f"ChroMaya: Error reading palette {i}: {e}")
                    continue
            
            color_history = self.color_history.colors
            save_state(palettes, color_history)
            
            # Show a temporary success message with the path (only in script editor)
            state_path = get_state_file_path()
            om.MGlobal.displayInfo(f"ChroMaya: State auto-saved to {state_path}")
        except Exception as e:
            om.MGlobal.displayError(f"ChroMaya: Failed to auto-save state: {e}")

    def import_state(self, use_default_path=False):
        """Import palettes and merge with existing ones
        
        Args:
            use_default_path (bool): If True, import from default save location instead of asking for file
        """
        try:
            # Determine the file path to import from
            file_path = ""
            if use_default_path:
                file_path = get_state_file_path()
                if not os.path.exists(file_path):
                    om.MGlobal.displayWarning(f"ChroMaya: No saved state found at {file_path}")
                    return
            else:
                # Get the default directory (Maya user directory)
                default_dir = os.path.dirname(get_state_file_path())
                
                # Open file dialog
                selected_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                    self,
                    "Import ChroMaya Palettes",
                    default_dir,
                    "JSON Files (*.json);;All Files (*.*)"
                )
                
                if not selected_path:
                    return  # User cancelled
                
                file_path = selected_path
            
            # Read and parse the state file
            with open(file_path, 'r') as f:
                state = json.load(f)
            
            # Process color history - add to existing rather than replacing
            for color_name in state.get('color_history', []):
                color = QtGui.QColor(color_name)
                if color.isValid():
                    self.color_history.addColor(color)
            
            # Get existing palette names to avoid duplicates
            existing_names = set()
            for i in range(self.saved_palette_manager.scroll_layout.count()):
                item = self.saved_palette_manager.scroll_layout.itemAt(i)
                if item and item.widget():
                    thumb = item.widget()
                    existing_names.add(thumb.name)
            
            # Add new palettes (but don't replace existing ones with same name)
            palettes_added = 0
            for palette in state.get('palettes', []):
                name = palette['name']
                
                # If name exists, create a unique name
                original_name = name
                counter = 1
                while name in existing_names:
                    name = f"{original_name} ({counter})"
                    counter += 1
                
                # Add with the (potentially renamed) palette
                self.saved_palette_manager.add_palette(
                    name,
                    palette['palette_data'],
                    mark_as_latest=False
                )
                existing_names.add(name)
                palettes_added += 1
            
            # Update the mixing dish with the first new palette if available and no existing palette was loaded
            if palettes_added > 0 and self.saved_palette_manager.active_thumb is None:
                # Find the first added palette
                count = self.saved_palette_manager.scroll_layout.count()
                if count > 0:
                    # Set the last added palette as active
                    last_added = self.saved_palette_manager.scroll_layout.itemAt(count - 1).widget()
                    if last_added:
                        self.saved_palette_manager.mark_active_thumb(last_added)
                        self.mixing_dish.load_palette(last_added.palette_data)
            
            # Enable the Save Current Palette button if we have any palettes
            if self.saved_palette_manager.scroll_layout.count() > 0:
                self.save_palette_btn.setEnabled(True)
            
            # Show success message
            om.MGlobal.displayInfo(f"ChroMaya: Added {palettes_added} palettes from {file_path}")
            
            # Show temporary success message on button
            self.import_palettes_btn.setText("Imported!")
            QtCore.QTimer.singleShot(2000, lambda: self.import_palettes_btn.setText("Import Palettes"))
                
        except Exception as e:
            om.MGlobal.displayError(f"ChroMaya: Failed to import palettes: {e}")
            self.import_palettes_btn.setText("Import Failed!")
            QtCore.QTimer.singleShot(2000, lambda: self.import_palettes_btn.setText("Import Palettes"))

    def show_import_menu(self, pos):
        """Show context menu for import button"""
        menu = QtWidgets.QMenu()
        
        import_from_file = menu.addAction("Import from File")
        import_from_file.triggered.connect(lambda: self.import_state(False))
        
        import_from_default = menu.addAction("Import from Default Location")
        import_from_default.triggered.connect(lambda: self.import_state(True))
        
        # Position the menu
        menu.exec_(self.import_palettes_btn.mapToGlobal(pos))

    def export_active_palette(self):
        """Export the currently active palette to a file"""
        try:
            # Make sure there's an active palette
            if not self.saved_palette_manager.active_thumb:
                om.MGlobal.displayWarning("ChroMaya: No active palette to export")
                return
            
            # Get the active palette data
            active_palette = self.saved_palette_manager.active_thumb
            palette_name = active_palette.name
            palette_data = active_palette.palette_data
            
            # Ask the user where to save the file
            default_dir = os.path.dirname(get_state_file_path())
            default_filename = f"{palette_name.replace(' ', '_')}.json"
            
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Export Palette",
                os.path.join(default_dir, default_filename),
                "JSON Files (*.json);;All Files (*.*)"
            )
            
            if not file_path:
                return  # User cancelled
            
            # Convert palette data to a serializable format
            serializable_palette_data = []
            for blob in palette_data:
                # Handle pos being either a QPoint/QPointF or a dict with x, y
                pos_dict = {}
                pos = blob['pos']
                if isinstance(pos, (QtCore.QPoint, QtCore.QPointF)):
                    pos_dict = {'x': pos.x(), 'y': pos.y()}
                elif isinstance(pos, dict) and 'x' in pos and 'y' in pos:
                    pos_dict = {'x': pos['x'], 'y': pos['y']}
                else:
                    om.MGlobal.displayWarning(f"ChroMaya: Unsupported position format in export_active_palette")
                    continue  # Skip this blob if position format is invalid
                    
                # Handle color being either a QColor or a string
                color_str = ""
                if isinstance(blob['color'], QtGui.QColor):
                    color_str = blob['color'].name()
                else:
                    color_str = str(blob['color'])
                    
                serializable_blob = {
                    'pos': pos_dict,
                    'color': color_str,
                    'radius': blob['radius']
                }
                serializable_palette_data.append(serializable_blob)
            
            # Create a simplified export with just this palette
            export_data = {
                'palettes': [
                    {
                        'name': palette_name,
                        'palette_data': serializable_palette_data
                    }
                ],
                'color_history': []  # Not including color history in palette export
            }
            
            # Save to the selected file
            with open(file_path, 'w') as f:
                json.dump(export_data, f, indent=2)  # Use indentation for readable files
            
            # Show success message
            self.export_palette_btn.setText("Exported!")
            om.MGlobal.displayInfo(f"ChroMaya: Palette '{palette_name}' exported to {file_path}")
            QtCore.QTimer.singleShot(2000, lambda: self.export_palette_btn.setText("Export Palette"))
            
        except Exception as e:
            om.MGlobal.displayError(f"ChroMaya: Error exporting palette: {e}")
            self.export_palette_btn.setText("Export Failed!")
            QtCore.QTimer.singleShot(2000, lambda: self.export_palette_btn.setText("Export Palette"))

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
       # Save state before unloading
       for widget in QtWidgets.QApplication.allWidgets():
           if isinstance(widget, ChroMayaWindow):
               widget.auto_save_state()
               break
               
       plugin_fn.deregisterCommand(plugin_name)
       om.MGlobal.displayInfo("ChroMaya Plugin Unloaded.")
   except:
       om.MGlobal.displayError("Failed to unregister ChroMaya command.")

