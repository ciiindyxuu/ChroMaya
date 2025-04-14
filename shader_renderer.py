import numpy as np
from OpenGL.GL import *
from OpenGL.GL.shaders import compileShader, compileProgram
from shaders import VERTEX_SHADER, FRAGMENT_SHADER

class ShaderMetaballRenderer:
    def __init__(self):
        self.shader_program = None
        self.vbo = None
        self.initialized = False
        self.threshold = 0.5
        
    def initialize_shaders(self, width, height):
        if self.initialized:
            return
            
        # Compile shaders
        vertex_shader = compileShader(VERTEX_SHADER, GL_VERTEX_SHADER)
        fragment_shader = compileShader(FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
        self.shader_program = compileProgram(vertex_shader, fragment_shader)
        
        # Create vertex data for a full-screen quad
        vertices = np.array([
            -1.0, -1.0, 0.0, 1.0,  # Bottom-left
             1.0, -1.0, 0.0, 1.0,  # Bottom-right
            -1.0,  1.0, 0.0, 1.0,  # Top-left
             1.0,  1.0, 0.0, 1.0   # Top-right
        ], dtype=np.float32)
        
        # Create and bind VBO
        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        
        # Unbind buffer
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        
        self.initialized = True
        
    def render(self, blobs, width, height):
        if not self.initialized:
            self.initialize_shaders(width, height)
            
        # Clear the screen
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        # Use shader program
        glUseProgram(self.shader_program)
        
        # Set viewport
        glViewport(0, 0, width, height)
        
        # Prepare blob data (limit to 20 blobs as in WebGL version)
        num_blobs = min(len(blobs), 20)
        positions = np.zeros((20, 3), dtype=np.float32)
        radii = np.zeros(20, dtype=np.float32)
        colors = np.zeros((20, 3), dtype=np.float32)
        
        for i in range(num_blobs):
            positions[i] = blobs[i].position
            radii[i] = blobs[i].radius
            colors[i] = blobs[i].color
            
        # Set uniforms
        glUniform1i(glGetUniformLocation(self.shader_program, "u_NumBlobs"), num_blobs)
        glUniform3fv(glGetUniformLocation(self.shader_program, "u_BlobPositions"), 20, positions)
        glUniform1fv(glGetUniformLocation(self.shader_program, "u_BlobRadii"), 20, radii)
        glUniform3fv(glGetUniformLocation(self.shader_program, "u_BlobColors"), 20, colors)
        glUniform1f(glGetUniformLocation(self.shader_program, "u_Threshold"), self.threshold)
        
        # Set up vertex attributes
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        position_loc = glGetAttribLocation(self.shader_program, "position")
        glEnableVertexAttribArray(position_loc)
        glVertexAttribPointer(position_loc, 4, GL_FLOAT, GL_FALSE, 0, None)
        
        # Draw full-screen quad
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        
        # Clean up vertex attributes
        glDisableVertexAttribArray(position_loc)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glUseProgram(0)
        
    def cleanup(self):
        if self.initialized:
            if self.vbo:
                glDeleteBuffers(1, [self.vbo])
            if self.shader_program:
                glDeleteProgram(self.shader_program)
            self.initialized = False 