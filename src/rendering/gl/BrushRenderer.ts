import {vec2, vec3} from 'gl-matrix';
import {gl} from '../../globals';
import ShaderProgram from './ShaderProgram';
import Camera from '../../Camera';
import Square from '../../geometry/Square';

class BrushRenderer {
  private square: Square;
  private shader: ShaderProgram;
  
  constructor(shader: ShaderProgram) {
    this.shader = shader;
    this.square = new Square(vec3.fromValues(0, 0, 0));
    this.square.create();
  }
  
  render(camera: Camera, strokes: {points: {position: vec2, color: vec3, size: number}[], color: vec3}[]) {
    if (strokes.length === 0) return;
    
    // Save current GL state
    const oldBlendSrc = gl.getParameter(gl.BLEND_SRC_ALPHA);
    const oldBlendDst = gl.getParameter(gl.BLEND_DST_ALPHA);
    
    // Set up blending for brush strokes
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    
    this.shader.use();
    
    // Set camera uniforms
    this.shader.setEyeRefUp(camera.controls.eye, camera.controls.center, camera.controls.up);
    
    // Draw each stroke
    for (const stroke of strokes) {
      const points = stroke.points;
      if (points.length < 2) continue;
      
      // Set color uniform
      gl.uniform3f(
        gl.getUniformLocation(this.shader.prog, "u_BrushColor"),
        stroke.color[0], stroke.color[1], stroke.color[2]
      );
      
      // Draw line segments
      for (let i = 0; i < points.length - 1; i++) {
        const p1 = points[i];
        const p2 = points[i + 1];
        
        // Calculate distance between points
        const dx = p2.position[0] - p1.position[0];
        const dy = p2.position[1] - p1.position[1];
        const distance = Math.sqrt(dx * dx + dy * dy);
        
        // Skip if points are too close
        if (distance < 0.001) continue;
        
        gl.uniform2f(
          gl.getUniformLocation(this.shader.prog, "u_PrevPosition"),
          p1.position[0], p1.position[1]
        );
        
        gl.uniform2f(
          gl.getUniformLocation(this.shader.prog, "u_BrushPosition"),
          p2.position[0], p2.position[1]
        );
        
        gl.uniform1f(
          gl.getUniformLocation(this.shader.prog, "u_BrushSize"),
          (p1.size + p2.size) / 2.0
        );
        
        gl.uniform1f(
          gl.getUniformLocation(this.shader.prog, "u_StrokeLength"),
          distance
        );
        
        this.shader.draw(this.square);
      }
    }
  
    gl.blendFunc(oldBlendSrc, oldBlendDst);
  }
}

export default BrushRenderer; 