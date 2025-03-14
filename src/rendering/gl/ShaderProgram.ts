import {vec2, vec3, vec4, mat4} from 'gl-matrix';
import Drawable from './Drawable';
import {gl} from '../../globals';

var activeProgram: WebGLProgram = null;

export class Shader {
  shader: WebGLShader;

  constructor(type: number, source: string) {
    this.shader = gl.createShader(type);
    gl.shaderSource(this.shader, source);
    gl.compileShader(this.shader);

    if (!gl.getShaderParameter(this.shader, gl.COMPILE_STATUS)) {
      throw gl.getShaderInfoLog(this.shader);
    }
  }
};

class ShaderProgram {
  prog: WebGLProgram;

  attrPos: number;
  attrNor: number;

  unifRef: WebGLUniformLocation;
  unifEye: WebGLUniformLocation;
  unifUp: WebGLUniformLocation;
  unifDimensions: WebGLUniformLocation;
  unifTime: WebGLUniformLocation;
  unifCircleColor: WebGLUniformLocation;

  constructor(shaders: Array<Shader>) {
    this.prog = gl.createProgram();

    for (let shader of shaders) {
      gl.attachShader(this.prog, shader.shader);
    }
    gl.linkProgram(this.prog);
    if (!gl.getProgramParameter(this.prog, gl.LINK_STATUS)) {
      throw gl.getProgramInfoLog(this.prog);
    }

    this.attrPos = gl.getAttribLocation(this.prog, "vs_Pos");
    this.unifEye   = gl.getUniformLocation(this.prog, "u_Eye");
    this.unifRef   = gl.getUniformLocation(this.prog, "u_Ref");
    this.unifUp   = gl.getUniformLocation(this.prog, "u_Up");
    this.unifDimensions   = gl.getUniformLocation(this.prog, "u_Dimensions");
    this.unifTime   = gl.getUniformLocation(this.prog, "u_Time");
    this.unifCircleColor = gl.getUniformLocation(this.prog, "u_CircleColor");
  }

  use() {
    if (activeProgram !== this.prog) {
      gl.useProgram(this.prog);
      activeProgram = this.prog;
    }
  }

  setEyeRefUp(eye: vec3, ref: vec3, up: vec3) {
    this.use();
    if(this.unifEye !== -1) {
      gl.uniform3f(this.unifEye, eye[0], eye[1], eye[2]);
    }
    if(this.unifRef !== -1) {
      gl.uniform3f(this.unifRef, ref[0], ref[1], ref[2]);
    }
    if(this.unifUp !== -1) {
      gl.uniform3f(this.unifUp, up[0], up[1], up[2]);
    }
  }

  setDimensions(width: number, height: number) {
    this.use();
    if(this.unifDimensions !== -1) {
      gl.uniform2f(this.unifDimensions, width, height);
    }
  }

  setTime(t: number) {
    this.use();
    if(this.unifTime !== -1) {
      gl.uniform1f(this.unifTime, t);
    }
  }

  setCircleColor(r: number, g: number, b: number) {
    this.use();
    if(this.unifCircleColor !== -1) {
      gl.uniform3f(this.unifCircleColor, r, g, b);
    }
  }

  draw(d: Drawable) {
    this.use();

    if (this.attrPos != -1 && d.bindPos()) {
      gl.enableVertexAttribArray(this.attrPos);
      gl.vertexAttribPointer(this.attrPos, 4, gl.FLOAT, false, 0, 0);
    }

    d.bindIdx();
    gl.drawElements(d.drawMode(), d.elemCount(), gl.UNSIGNED_INT, 0);

    if (this.attrPos != -1) gl.disableVertexAttribArray(this.attrPos);
  }

  setNumBlobs(num: number) {
    this.use();
    const loc = gl.getUniformLocation(this.prog, "u_NumBlobs");
    if (loc !== null) {
      gl.uniform1i(loc, num);
    }
  }

  setThreshold(threshold: number) {
    this.use();
    const loc = gl.getUniformLocation(this.prog, "u_Threshold");
    if (loc !== null) {
      gl.uniform1f(loc, threshold);
    }
  }

  setBlobPosition(index: number, position: vec3) {
    this.use();
    const loc = gl.getUniformLocation(this.prog, `u_BlobPositions[${index}]`);
    if (loc !== null) {
      gl.uniform3f(loc, position[0], position[1], position[2]);
    }
  }

  setBlobRadius(index: number, radius: number) {
    this.use();
    const loc = gl.getUniformLocation(this.prog, `u_BlobRadii[${index}]`);
    if (loc !== null) {
      gl.uniform1f(loc, radius);
    }
  }

  setBlobColor(index: number, color: vec3) {
    this.use();
    const loc = gl.getUniformLocation(this.prog, `u_BlobColors[${index}]`);
    if (loc !== null) {
      gl.uniform3f(loc, color[0], color[1], color[2]);
    }
  }
}

export default ShaderProgram;
