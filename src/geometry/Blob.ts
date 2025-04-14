import {vec3, vec4} from 'gl-matrix';
import Circle from './Circle';
import {gl} from '../globals';

class Blob extends Circle {
  radius: number = 0.1;
  static nextId: number = 0;
  id: number;
  
  constructor(center: vec3, color: vec3, radius: number = 0.1) {
    super(vec3.fromValues(center[0], center[1], center[2]), color);
    this.center = vec4.fromValues(center[0], center[1], center[2], 1.0);
    this.color = color;
    this.radius = radius;
    this.id = Blob.nextId++;
  }
  

  getInfluence(x: number, y: number): number {
    const dx = x - this.center[0];
    const dy = y - this.center[1];
    const distSq = dx * dx + dy * dy;
    const dist = Math.sqrt(distSq);
    
    const influenceRadius = this.radius * 3.0;
    
    if (dist <= influenceRadius) {
      const t = dist / influenceRadius;
      return (1.0 - t * t * t * (t * (t * 6.0 - 15.0) + 10.0)) * 1.2;
    }
    
    return 0.0;
  }
}

export default Blob; 