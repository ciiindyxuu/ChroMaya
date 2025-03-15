import {vec2, vec3} from 'gl-matrix';
import * as DAT from 'dat.gui';
import Square from './geometry/Square';
import OpenGLRenderer from './rendering/gl/OpenGLRenderer';
import Camera from './Camera';
import {setGL} from './globals';
import ShaderProgram, {Shader} from './rendering/gl/ShaderProgram';
import Circle from './geometry/Circle';
import Blob from './geometry/Blob';
import MetaballRenderer from './rendering/gl/MetaballRenderer';

const controls = {
  tesselations: 5,
  'Load Scene': loadScene, 
  color: "#ff0000", 
  blobRadius: 0.1,
  threshold: 0.5
};

let square: Square;
let blobs: Blob[] = [];
let time: number = 0;
let isDragging = false;
let selectedBlob: Blob | null = null;

function loadScene() {
  square = new Square(vec3.fromValues(0, 0, 0));
  square.create();
}

function getClipSpaceMousePosition(event: MouseEvent, canvas: HTMLCanvasElement) {
  const rect = canvas.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;

  return {
    x: (x / canvas.width) * 2 - 1,
    y: -((y / canvas.height) * 2 - 1) 
  };
}


function hexToRgb(hex: string): {r: number, g: number, b: number} {

  hex = hex.replace(/^#/, '');
  

  const bigint = parseInt(hex, 16);
  const r = ((bigint >> 16) & 255) / 255;
  const g = ((bigint >> 8) & 255) / 255;
  const b = (bigint & 255) / 255;
  
  return { r, g, b };
}

function main() {
  window.addEventListener('keypress', function (e) {
    switch(e.key) {

    }
  }, false);

  window.addEventListener('keyup', function (e) {
    switch(e.key) {

    }
  }, false);

  const gui = new DAT.GUI();

  const colorController = gui.addColor(controls, 'color').name('Blob Color');
  
  // Add blob controls
  const blobFolder = gui.addFolder('Blob Settings');
  blobFolder.add(controls, 'blobRadius', 0.05, 0.2).name('Blob Radius');
  blobFolder.add(controls, 'threshold', 0.1, 1.0).name('Metaball Threshold');
  blobFolder.open();

  const canvas = <HTMLCanvasElement> document.getElementById('canvas');
  const gl = <WebGL2RenderingContext> canvas.getContext('webgl2');
  if (!gl) {
    alert('WebGL 2 not supported!');
  }
  setGL(gl);

  const camera = new Camera(vec3.fromValues(0, 0, -10), vec3.fromValues(0, 0, 0));

  const renderer = new OpenGLRenderer(canvas);
  renderer.setClearColor(1.0, 1.0, 1.0, 1); 
  gl.enable(gl.DEPTH_TEST);
  gl.enable(gl.BLEND);
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

  const flat = new ShaderProgram([
    new Shader(gl.VERTEX_SHADER, require('./shaders/flat-vert.glsl')),
    new Shader(gl.FRAGMENT_SHADER, require('./shaders/flat-frag.glsl')),
  ]);
  
  const metaballShader = new ShaderProgram([
    new Shader(gl.VERTEX_SHADER, require('./shaders/metaball-vert.glsl')),
    new Shader(gl.FRAGMENT_SHADER, require('./shaders/metaball-frag.glsl')),
  ]);
  
  const metaballRenderer = new MetaballRenderer(metaballShader);

  canvas.addEventListener('mousedown', (event) => {
    const pos = getClipSpaceMousePosition(event, canvas);
    for (let i = blobs.length - 1; i >= 0; i--) {
      const blob = blobs[i];
      const dx = pos.x - blob.center[0];
      const dy = pos.y - blob.center[1];
      const distance = Math.sqrt(dx * dx + dy * dy);
      
      if (distance < blob.radius) { 
        isDragging = true;
        selectedBlob = blob;
        return;
      }
    }

    const blob = new Blob(
      vec3.fromValues(pos.x, pos.y, 0),
      (() => {
        const rgb = hexToRgb(controls.color);
        return vec3.fromValues(rgb.r, rgb.g, rgb.b);
      })(),
      controls.blobRadius
    );
    blob.create();
    blobs.push(blob);
  });

  canvas.addEventListener('mousemove', (event) => {
    if (isDragging && selectedBlob) {
      const pos = getClipSpaceMousePosition(event, canvas);
      selectedBlob.center[0] = pos.x;
      selectedBlob.center[1] = pos.y;
      selectedBlob.create(); 
    }
  });

  canvas.addEventListener('mouseup', () => {
    isDragging = false;
    selectedBlob = null;
  });

  canvas.addEventListener('contextmenu', (event) => {
    event.preventDefault(); 
    
    const pos = getClipSpaceMousePosition(event, canvas);

    for (let i = blobs.length - 1; i >= 0; i--) {
      const blob = blobs[i];
      const dx = pos.x - blob.center[0];
      const dy = pos.y - blob.center[1];
      const distance = Math.sqrt(dx * dx + dy * dy);
      
      if (distance < blob.radius) { 
        blobs.splice(i, 1); 
        break;
      }
    }
  });

  function processKeyPresses() {
    metaballRenderer.setThreshold(controls.threshold);
    
    for (const blob of blobs) {
      if (blob.radius !== controls.blobRadius && !isDragging) {
        blob.radius = controls.blobRadius;
        blob.create();
      }
    }
  }

  function tick() {
    camera.update();
    gl.viewport(0, 0, window.innerWidth, window.innerHeight);
    renderer.clear();
    processKeyPresses();
    
    if (blobs.length > 0) {
    
      metaballRenderer.render(camera, blobs, time);
    }
    
    time++;
    requestAnimationFrame(tick);
  }

  window.addEventListener('resize', function() {
    renderer.setSize(window.innerWidth, window.innerHeight);
    camera.setAspectRatio(window.innerWidth / window.innerHeight);
    camera.updateProjectionMatrix();
    metaballShader.setDimensions(window.innerWidth, window.innerHeight);
  }, false);

  renderer.setSize(window.innerWidth, window.innerHeight);
  camera.setAspectRatio(window.innerWidth / window.innerHeight);
  camera.updateProjectionMatrix();
  metaballShader.setDimensions(window.innerWidth, window.innerHeight);
  tick();
}

main();
