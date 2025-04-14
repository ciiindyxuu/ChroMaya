import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *

class MetaballRenderer:
    def __init__(self):
        self.threshold = 0.5  # Adjusted to match shader
        self.resolution = 400  # Increased for better quality
        
    def quintic_interpolation(self, t):
        """Quintic interpolation function matching the shader."""
        return 1.0 - t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
        
    def render(self, blobs):
        """Render metaballs using the same approach as the WebGL shader."""
        # Create a grid of points
        x = np.linspace(-1, 1, self.resolution)
        y = np.linspace(-1, 1, self.resolution)
        X, Y = np.meshgrid(x, y)
        
        # Calculate field values using vectorized operations
        field = np.zeros((self.resolution, self.resolution))
        for blob in blobs:
            # Calculate distances for all points at once
            dx = X - blob.center[0]
            dy = Y - blob.center[1]
            distances = np.sqrt(dx * dx + dy * dy)
            
            # Use same influence radius as shader
            influence_radius = blob.radius * 3.0
            r = distances / influence_radius
            mask = r < 1.0
            
            # Use quintic interpolation matching the shader
            field[mask] += self.quintic_interpolation(r[mask]) * 1.2
        
        # Enable anti-aliasing and blending
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        # Render the metaballs using triangle strips
        glBegin(GL_TRIANGLE_STRIP)
        for i in range(self.resolution - 1):
            for j in range(self.resolution - 1):
                # Get field values at corners
                f00 = field[i, j]
                f10 = field[i + 1, j]
                f01 = field[i, j + 1]
                f11 = field[i + 1, j + 1]
                
                # Check if any corner is near or above threshold
                edge_width = 0.01
                if max(f00, f10, f01, f11) > self.threshold - edge_width:
                    # Calculate blended colors with smooth interpolation
                    colors = np.zeros((4, 3))  # Colors for each corner
                    alphas = np.zeros(4)  # Alpha values for smooth edges
                    corners = [(i, j), (i+1, j), (i, j+1), (i+1, j+1)]
                    field_values = [f00, f10, f01, f11]
                    
                    for idx, (ci, cj) in enumerate(corners):
                        total_color = np.zeros(3)
                        total_weight = 0.0
                        
                        # Calculate alpha for smooth edges
                        f = field_values[idx]
                        alphas[idx] = np.clip((f - (self.threshold - edge_width)) / (2 * edge_width), 0, 1)
                        
                        for blob in blobs:
                            dx = X[ci, cj] - blob.center[0]
                            dy = Y[ci, cj] - blob.center[1]
                            dist = np.sqrt(dx * dx + dy * dy)
                            influence_radius = blob.radius * 3.0
                            r = dist / influence_radius
                            
                            if r < 1.0:
                                # Use same quintic interpolation for color blending
                                influence = self.quintic_interpolation(r) * 1.2
                                total_color += blob.color * influence
                                total_weight += influence
                        
                        if total_weight > 0:
                            colors[idx] = total_color / total_weight
                    
                    # Draw two triangles with interpolated colors and alpha
                    vertices = [(X[i, j], Y[i, j]), (X[i+1, j], Y[i+1, j]),
                              (X[i, j+1], Y[i, j+1]), (X[i+1, j+1], Y[i+1, j+1])]
                    
                    for idx, (vx, vy) in enumerate(vertices):
                        glColor4f(colors[idx][0], colors[idx][1], colors[idx][2], alphas[idx])
                        glVertex2f(vx, vy)
        
        glEnd()
        glDisable(GL_BLEND)

class PaintRenderer:
    def __init__(self):
        pass
        
    def render(self, strokes):
        """Render paint strokes."""
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        for stroke in strokes:
            glColor4f(*stroke['color'], 0.5)  # Semi-transparent
            glPointSize(stroke['size'] * 100)  # Scale size to pixels
            
            glBegin(GL_POINTS)
            glVertex2f(stroke['position'][0], stroke['position'][1])
            glEnd()
            
        glDisable(GL_BLEND) 