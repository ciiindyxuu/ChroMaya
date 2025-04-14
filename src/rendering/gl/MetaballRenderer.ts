import {vec3} from 'gl-matrix';
import {gl} from '../../globals';
import Blob from '../../geometry/Blob';
import ShaderProgram from './ShaderProgram';
import Camera from '../../Camera';
import Square from '../../geometry/Square';

class MetaballRenderer {
  private square: Square;
  private shader: ShaderProgram;
  private threshold: number = 0.5;
  
  constructor(shader: ShaderProgram) {
    this.shader = shader;
    this.square = new Square(vec3.fromValues(0, 0, 0));
    this.square.create();
  }
  
  render(camera: Camera, blobs: Blob[], time: number) {
    if (blobs.length === 0) return;
    
    this.shader.use();
    
    // Set uniforms
    this.shader.setEyeRefUp(camera.controls.eye, camera.controls.center, camera.controls.up);
    this.shader.setTime(time);
    
    // Set blob data
    gl.uniform1i(gl.getUniformLocation(this.shader.prog, "u_NumBlobs"), blobs.length);
    gl.uniform1f(gl.getUniformLocation(this.shader.prog, "u_Threshold"), this.threshold);
    
    // Set blob positions, radii, and colors
    for (let i = 0; i < blobs.length; i++) {
      const blob = blobs[i];
      gl.uniform3f(
        gl.getUniformLocation(this.shader.prog, `u_BlobPositions[${i}]`),
        blob.center[0], blob.center[1], blob.center[2]
      );
      gl.uniform1f(
        gl.getUniformLocation(this.shader.prog, `u_BlobRadii[${i}]`),
        blob.radius
      );
      gl.uniform3f(
        gl.getUniformLocation(this.shader.prog, `u_BlobColors[${i}]`),
        blob.color[0], blob.color[1], blob.color[2]
      );
    }
    
    // Draw a full-screen quad
    this.shader.draw(this.square);
  }
  
  setThreshold(threshold: number) {
    this.threshold = threshold;
  }
}

export default MetaballRenderer;