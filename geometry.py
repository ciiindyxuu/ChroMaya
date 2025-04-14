import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *

class Blob:
    def __init__(self, position, color, radius):
        self.position = position
        self.color = color
        self.radius = radius
        
    def get_influence(self, x, y):
        """Calculate the influence of this blob at a given point."""
        dx = x - self.position[0]
        dy = y - self.position[1]
        dist = np.sqrt(dx * dx + dy * dy)
        
        # Use same influence radius as WebGL version
        influence_radius = self.radius * 3.0
        
        if dist > influence_radius:
            return 0.0
            
        # Use same quintic interpolation as WebGL version
        t = dist / influence_radius
        return (1.0 - t * t * t * (t * (t * 6.0 - 15.0) + 10.0)) * 1.2
        
    def render(self):
        """Render the blob using OpenGL."""
        glPushMatrix()
        glTranslatef(self.position[0], self.position[1], self.position[2])
        glColor3fv(self.color)
        
        # Draw a circle to represent the blob
        segments = 32
        glBegin(GL_POLYGON)
        for i in range(segments):
            angle = 2.0 * np.pi * i / segments
            x = self.radius * np.cos(angle)
            y = self.radius * np.sin(angle)
            glVertex2f(x, y)
        glEnd()
        
        glPopMatrix() 