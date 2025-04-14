import sys
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QHBoxLayout, QPushButton, QLabel, QColorDialog, QSlider, QFrame
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QColor
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
from geometry import Blob
from shader_renderer import ShaderMetaballRenderer
from palette import PaletteHistory, MixingDish

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChroMaya - PyQt Version")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)  # Changed to VBoxLayout
        
        # Create content widget with HBoxLayout
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        
        # Create OpenGL widget
        self.gl_widget = GLWidget()
        content_layout.addWidget(self.gl_widget, stretch=1)
        
        # Create control panel
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        
        # Add controls
        self.add_controls(control_layout)
        
        content_layout.addWidget(control_panel, stretch=0)
        
        # Add content widget to main layout
        layout.addWidget(content_widget, stretch=1)
        
        # Create color swatch at the bottom
        self.color_swatch = QFrame()
        self.color_swatch.setMinimumHeight(50)
        self.color_swatch.setStyleSheet("background-color: red; border: 2px solid black;")
        layout.addWidget(self.color_swatch)
        
        # Initialize state
        self.blobs = []
        self.current_brush_color = np.array([1.0, 0.0, 0.0])  # Default red
        self.palette_history = PaletteHistory()
        self.active_mixing_dish = self.palette_history.active_dish
        
    def add_controls(self, layout):
        # Blob controls
        blob_group = QWidget()
        blob_layout = QVBoxLayout(blob_group)
        
        # Color picker
        color_btn = QPushButton("Blob Color")
        color_btn.clicked.connect(self.choose_blob_color)
        blob_layout.addWidget(color_btn)
        
        # Blob radius slider
        radius_label = QLabel("Blob Radius")
        radius_slider = QSlider(Qt.Orientation.Horizontal)
        radius_slider.setRange(5, 20)
        radius_slider.setValue(10)
        radius_slider.valueChanged.connect(self.update_blob_radius)
        blob_layout.addWidget(radius_label)
        blob_layout.addWidget(radius_slider)
        
        # Add blob group to main layout
        layout.addWidget(blob_group)
        layout.addStretch()
        
    def choose_blob_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.current_brush_color = np.array([
                color.redF(),
                color.greenF(),
                color.blueF()
            ])
            # Update color swatch
            self.update_color_swatch()
            
    def update_color_swatch(self):
        """Update the color swatch with the current color."""
        r = int(self.current_brush_color[0] * 255)
        g = int(self.current_brush_color[1] * 255)
        b = int(self.current_brush_color[2] * 255)
        self.color_swatch.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: 2px solid black;")
            
    def update_blob_radius(self, value):
        radius = value / 100.0  # Convert to 0.05-0.2 range
        for blob in self.blobs:
            blob.radius = radius

class GLWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.metaball_renderer = None
        # Enable high DPI scaling
        self.setMouseTracking(True)
        self.is_dragging = False
        self.selected_blob = None
        
    def get_main_window(self):
        """Get the main window instance."""
        parent = self.parent()
        while parent is not None and not isinstance(parent, MainWindow):
            parent = parent.parent()
        return parent
        
    def initializeGL(self):
        # Initialize OpenGL context
        glClearColor(1.0, 1.0, 1.0, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        # Initialize shader-based renderer
        self.metaball_renderer = ShaderMetaballRenderer()
        
    def resizeGL(self, w, h):
        # Convert to integers for glViewport
        device_w = int(w * self.devicePixelRatio())
        device_h = int(h * self.devicePixelRatio())
        glViewport(0, 0, device_w, device_h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(-1, 1, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        
    def paintGL(self):
        # Clear the framebuffer
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        main_window = self.get_main_window()
        if not main_window:
            return
            
        # Render metaballs using shader with integer dimensions
        if main_window.blobs:
            device_w = int(self.width() * self.devicePixelRatio())
            device_h = int(self.height() * self.devicePixelRatio())
            self.metaball_renderer.render(main_window.blobs, device_w, device_h)
            
    def get_clip_space_position(self, pos):
        """Convert screen coordinates to clip space, accounting for device pixel ratio"""
        # Get the device pixel ratio
        ratio = self.devicePixelRatio()
        
        # Convert from screen coordinates to device coordinates
        device_x = pos.x() * ratio
        device_y = pos.y() * ratio
        
        # Convert to clip space (-1 to 1)
        x = (device_x / (self.width() * ratio)) * 2 - 1
        y = -((device_y / (self.height() * ratio)) * 2 - 1)
        
        return np.array([x, y, 0])
            
    def mousePressEvent(self, event):
        main_window = self.get_main_window()
        if not main_window:
            return
            
        pos = self.get_clip_space_position(event.pos())
        
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if we clicked on an existing blob
            for blob in reversed(main_window.blobs):  # Check from newest to oldest
                dx = pos[0] - blob.position[0]
                dy = pos[1] - blob.position[1]
                distance = np.sqrt(dx * dx + dy * dy)
                
                if distance < blob.radius:
                    self.is_dragging = True
                    self.selected_blob = blob
                    return
                    
            # If no blob was clicked, create a new one
            main_window.blobs.append(Blob(
                pos,
                main_window.current_brush_color,
                0.1  # Default radius
            ))
            self.update()
            
    def mouseMoveEvent(self, event):
        if self.is_dragging and self.selected_blob:
            pos = self.get_clip_space_position(event.pos())
            self.selected_blob.position[0] = pos[0]
            self.selected_blob.position[1] = pos[1]
            self.update()
            
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self.selected_blob = None
            
    def mouseDoubleClickEvent(self, event):
        main_window = self.get_main_window()
        if not main_window:
            return
            
        pos = self.get_clip_space_position(event.pos())
        
        # Check if we double-clicked on a blob
        for blob in reversed(main_window.blobs):  # Check from newest to oldest
            dx = pos[0] - blob.position[0]
            dy = pos[1] - blob.position[1]
            distance = np.sqrt(dx * dx + dy * dy)
            
            if distance < blob.radius:
                # Show color picker for this blob
                color = QColorDialog.getColor()
                if color.isValid():
                    blob.color = np.array([
                        color.redF(),
                        color.greenF(),
                        color.blueF()
                    ])
                    self.update()
                return
                
    def contextMenuEvent(self, event):
        main_window = self.get_main_window()
        if not main_window:
            return
            
        pos = self.get_clip_space_position(event.pos())
        
        # Check if we right-clicked on a blob
        for i, blob in enumerate(reversed(main_window.blobs)):  # Check from newest to oldest
            dx = pos[0] - blob.position[0]
            dy = pos[1] - blob.position[1]
            distance = np.sqrt(dx * dx + dy * dy)
            
            if distance < blob.radius:
                # Remove the blob
                main_window.blobs.pop(len(main_window.blobs) - 1 - i)
                self.update()
                return
                
    def closeEvent(self, event):
        # Clean up OpenGL resources
        if self.metaball_renderer:
            self.metaball_renderer.cleanup()
        super().closeEvent(event)

def main():
    # Initialize GLUT for OpenGL context
    glutInit()
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 