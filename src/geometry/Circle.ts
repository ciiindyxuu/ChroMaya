import {vec3, vec4} from 'gl-matrix';
import Drawable from '../rendering/gl/Drawable';
import {gl} from '../globals';

class Circle extends Drawable {
  indices: Uint32Array;
  positions: Float32Array;
  center: vec4;
  color: vec3;
  segments: number = 32; 

  constructor(center: vec3, color: vec3) {
    super();
    this.center = vec4.fromValues(center[0], center[1], center[2], 1);
    this.color = color;
  }

  create() {
    const positions: number[] = [];
    const indices: number[] = [];
    
    positions.push(this.center[0], this.center[1], this.center[2], 1);

    for (let i = 0; i <= this.segments; i++) {
      const angle = (i / this.segments) * Math.PI * 2;
      const x = this.center[0] + 0.1 * Math.cos(angle); 
      const y = this.center[1] + 0.1 * Math.sin(angle);
      positions.push(x, y, this.center[2], 1);
      
      if (i < this.segments) {
        indices.push(0, i + 1, i + 2);
      }
    }

    this.positions = new Float32Array(positions);
    this.indices = new Uint32Array(indices);

    this.generateIdx();
    this.generatePos();

    this.count = this.indices.length;
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.bufIdx);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, this.indices, gl.STATIC_DRAW);

    gl.bindBuffer(gl.ARRAY_BUFFER, this.bufPos);
    gl.bufferData(gl.ARRAY_BUFFER, this.positions, gl.STATIC_DRAW);
  }
}

export default Circle;