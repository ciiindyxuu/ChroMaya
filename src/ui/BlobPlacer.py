from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QColorDialog, QSlider, QLabel
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
import numpy as np
from gl_matrix import vec3

from src.geometry.Blob import Blob
from src.palette.PaletteHistory import MixingDish

class BlobPlacer(QWidget):
    """Widget for placing and manipulating blobs in a mixing dish"""
    
    blobAdded = pyqtSignal(object)  # Signal emitted when a blob is added
    blobModified = pyqtSignal()     # Signal emitted when any blob is modified
    
    def __init__(self, paletteHistory, parent=None):
        super().__init__(parent)
        self.paletteHistory = paletteHistory
        self.currentColor = vec3.fromValues(1.0, 0.0, 0.0)  # Default red
        self.currentRadius = 0.1
        
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()
        
        # Color selection button
        colorLayout = QHBoxLayout()
        self.colorButton = QPushButton()
        self.colorButton.setFixedSize(40, 40)
        self.updateColorButton()
        self.colorButton.clicked.connect(self.selectColor)
        colorLayout.addWidget(QLabel("Blob Color:"))
        colorLayout.addWidget(self.colorButton)
        colorLayout.addStretch()
        layout.addLayout(colorLayout)
        
        # Radius slider
        radiusLayout = QHBoxLayout()
        self.radiusSlider = QSlider(Qt.Horizontal)
        self.radiusSlider.setMinimum(1)
        self.radiusSlider.setMaximum(30)
        self.radiusSlider.setValue(10)  # Default value
        self.radiusSlider.valueChanged.connect(self.updateRadius)
        self.radiusLabel = QLabel(f"Radius: {self.currentRadius:.2f}")
        radiusLayout.addWidget(QLabel("Blob Size:"))
        radiusLayout.addWidget(self.radiusSlider)
        radiusLayout.addWidget(self.radiusLabel)
        layout.addLayout(radiusLayout)
        
        # Add blob button
        self.addBlobButton = QPushButton("Add Blob")
        self.addBlobButton.clicked.connect(self.addBlob)
        layout.addWidget(self.addBlobButton)
        
        # Clear dish button
        self.clearDishButton = QPushButton("Clear Dish")
        self.clearDishButton.clicked.connect(self.clearDish)
        layout.addWidget(self.clearDishButton)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def updateColorButton(self):
        """Update the color button to show the current color"""
        r, g, b = self.currentColor
        qcolor = QColor(int(r * 255), int(g * 255), int(b * 255))
        self.colorButton.setStyleSheet(
            f"background-color: rgb({qcolor.red()}, {qcolor.green()}, {qcolor.blue()})")
    
    def selectColor(self):
        """Open color dialog to select a new blob color"""
        r, g, b = self.currentColor
        initial_color = QColor(int(r * 255), int(g * 255), int(b * 255))
        color = QColorDialog.getColor(initial_color, self)
        
        if color.isValid():
            self.currentColor = vec3.fromValues(
                color.red() / 255.0,
                color.green() / 255.0,
                color.blue() / 255.0
            )
            self.updateColorButton()
    
    def updateRadius(self, value):
        """Update the blob radius based on slider value"""
        self.currentRadius = value / 100.0
        self.radiusLabel.setText(f"Radius: {self.currentRadius:.2f}")
    
    def addBlob(self):
        """Add a new blob to the active mixing dish"""
        if not self.paletteHistory.activeDish:
            return
        
        # Create a snapshot if needed
        dish = self.paletteHistory.checkAndCreateSnapshot()
        
        # Calculate a position for the new blob
        # Place it in a circle around the center, based on how many blobs are already there
        num_blobs = len(dish.blobs)
        angle = (num_blobs * 2.0 * np.pi / 5) % (2.0 * np.pi)  # Space them out
        
        # Position in a circle of radius 0.3
        x = 0.3 * np.cos(angle)
        y = 0.3 * np.sin(angle)
        
        # Create the new blob
        center = vec3.fromValues(x, y, 0.0)
        color = vec3.clone(self.currentColor)
        
        new_blob = Blob(center, color, self.currentRadius)
        new_blob.create()
        
        # Add to the dish
        dish.blobs.append(new_blob)
        
        # Emit signal
        self.blobAdded.emit(new_blob)
        self.blobModified.emit()
    
    def clearDish(self):
        """Remove all blobs from the active dish"""
        if not self.paletteHistory.activeDish:
            return
            
        # Create a new empty dish
        dish = self.paletteHistory.createNewDish()
        dish.blobs = []
        
        self.blobModified.emit() 