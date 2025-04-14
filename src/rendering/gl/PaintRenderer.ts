import {vec2, vec3} from 'gl-matrix';
import {gl} from '../../globals';
import ShaderProgram from './ShaderProgram';
import Camera from '../../Camera';
import Square from '../../geometry/Square';

// Import the PaintStroke interface
interface PaintStroke {
  position: vec2;
  color: vec3;
  size: number;
  sourceType: 'blob' | 'dish' | 'manual';
  sourceId?: number;
}

class PaintRenderer {
  private square: Square;
  private shader: ShaderProgram;
  
  constructor(shader: ShaderProgram) {
    this.shader = shader;
    this.square = new Square(vec3.fromValues(0, 0, 0));
    this.square.create();
  }
  
  render(camera: Camera, paintStrokes: PaintStroke[]) {
    if (paintStrokes.length === 0) return;
    
    this.shader.use();
    
    this.shader.setEyeRefUp(camera.controls.eye, camera.controls.center, camera.controls.up);
  
    for (const stroke of paintStrokes) {
      gl.uniform2f(
        gl.getUniformLocation(this.shader.prog, "u_PaintPosition"),
        stroke.position[0], stroke.position[1]
      );
      gl.uniform3f(
        gl.getUniformLocation(this.shader.prog, "u_PaintColor"),
        stroke.color[0], stroke.color[1], stroke.color[2]
      );
      gl.uniform1f(
        gl.getUniformLocation(this.shader.prog, "u_PaintSize"),
        stroke.size
      );
      
      this.shader.draw(this.square);
    }
  }
}

export default PaintRenderer;