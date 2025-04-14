import numpy as np
from geometry import Blob

class MixingDish:
    def __init__(self, id, parent=None):
        self.id = id
        self.parent = parent
        self.children = []
        self.blobs = []
        self.used_for_painting = False
        
    def get_average_color(self):
        """Calculate the average color of all blobs in the dish."""
        if not self.blobs:
            return np.array([0.0, 0.0, 0.0])
            
        total_color = np.zeros(3)
        total_weight = 0.0
        
        for blob in self.blobs:
            total_color += blob.color
            total_weight += 1.0
            
        if total_weight > 0:
            return total_color / total_weight
        return np.array([0.0, 0.0, 0.0])
        
    def copy(self):
        """Create a deep copy of this dish."""
        new_dish = MixingDish(self.id, self.parent)
        new_dish.blobs = [Blob(
            np.array(blob.center),
            np.array(blob.color),
            blob.radius
        ) for blob in self.blobs]
        new_dish.used_for_painting = self.used_for_painting
        return new_dish

class PaletteHistory:
    def __init__(self):
        self.dishes = []
        self.active_dish = None
        self.next_id = 0
        
    def create_new_dish(self):
        """Create a new mixing dish."""
        new_dish = MixingDish(self.next_id)
        self.next_id += 1
        
        if self.active_dish:
            new_dish.parent = self.active_dish
            self.active_dish.children.append(new_dish)
            
        self.dishes.append(new_dish)
        self.active_dish = new_dish
        return new_dish
        
    def get_dish_for_pixel(self, x, y):
        """Find the dish that contains the given pixel."""
        for dish in reversed(self.dishes):  # Check from newest to oldest
            for blob in dish.blobs:
                if blob.get_influence(x, y) > 0:
                    return dish
        return None
        
    def propagate_color_changes(self, dish, original_blobs):
        """Propagate color changes from a dish to its descendants."""
        if not dish or not dish.children:
            return
            
        # Calculate color changes
        color_changes = []
        for i, (old_blob, new_blob) in enumerate(zip(original_blobs, dish.blobs)):
            if not np.array_equal(old_blob.color, new_blob.color):
                color_changes.append((i, new_blob.color))
                
        # Apply changes to descendants
        for child in dish.children:
            for blob_idx, new_color in color_changes:
                if blob_idx < len(child.blobs):
                    child.blobs[blob_idx].color = np.array(new_color)
            self.propagate_color_changes(child, original_blobs) 