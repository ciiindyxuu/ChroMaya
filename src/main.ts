import {vec2, vec3} from 'gl-matrix';
import * as DAT from 'dat.gui';
import Square from './geometry/Square';
import OpenGLRenderer from './rendering/gl/OpenGLRenderer';
import Camera from './Camera';
import {setGL} from './globals';
import ShaderProgram, {Shader} from './rendering/gl/ShaderProgram';
import Circle from './geometry/Circle';

const controls = {
  tesselations: 5,
  'Load Scene': loadScene, 
  circleColor: {
    r: 1.0,
    g: 0.0,
    b: 0.0
  }
};

let square: Square;
let circles: Circle[] = [];
let time: number = 0;
let isDragging = false;
let selectedCircle: Circle | null = null;

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
  // Add color controls
  const colorFolder = gui.addFolder('Circle Color');
  colorFolder.add(controls.circleColor, 'r', 0, 1).name('Red');
  colorFolder.add(controls.circleColor, 'g', 0, 1).name('Green');
  colorFolder.add(controls.circleColor, 'b', 0, 1).name('Blue');
  colorFolder.open(); 

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

  const flat = new ShaderProgram([
    new Shader(gl.VERTEX_SHADER, require('./shaders/flat-vert.glsl')),
    new Shader(gl.FRAGMENT_SHADER, require('./shaders/flat-frag.glsl')),
  ]);


  canvas.addEventListener('mousedown', (event) => {
    const pos = getClipSpaceMousePosition(event, canvas);
    for (let i = circles.length - 1; i >= 0; i--) {
      const circle = circles[i];
      const dx = pos.x - circle.center[0];
      const dy = pos.y - circle.center[1];
      const distance = Math.sqrt(dx * dx + dy * dy);
      
      if (distance < 0.1) { 
        isDragging = true;
        selectedCircle = circle;
        return;
      }
    }

    const circle = new Circle(
      vec3.fromValues(pos.x, pos.y, 0),
      vec3.fromValues(controls.circleColor.r, controls.circleColor.g, controls.circleColor.b)
    );
    circle.create();
    circles.push(circle);
  });

  canvas.addEventListener('mousemove', (event) => {
    if (isDragging && selectedCircle) {
      const pos = getClipSpaceMousePosition(event, canvas);
      selectedCircle.center[0] = pos.x;
      selectedCircle.center[1] = pos.y;
      selectedCircle.create(); 
    }
  });

  canvas.addEventListener('mouseup', () => {
    isDragging = false;
    selectedCircle = null;
  });

  canvas.addEventListener('contextmenu', (event) => {
    event.preventDefault(); 
    
    const pos = getClipSpaceMousePosition(event, canvas);

    for (let i = circles.length - 1; i >= 0; i--) {
        const circle = circles[i];
        const dx = pos.x - circle.center[0];
        const dy = pos.y - circle.center[1];
        const distance = Math.sqrt(dx * dx + dy * dy);
        
        if (distance < 0.1) { 
            circles.splice(i, 1); 
            break;
        }
    }
  });

  function processKeyPresses() {
  }

  function tick() {
    camera.update();
    gl.viewport(0, 0, window.innerWidth, window.innerHeight);
    renderer.clear();
    processKeyPresses();
    
    if (circles.length > 0) {
        for (const circle of circles) {
            flat.setCircleColor(circle.color[0], circle.color[1], circle.color[2]);
            renderer.render(camera, flat, [circle], time);
        }
    }
    
    time++;
    requestAnimationFrame(tick);
  }

  window.addEventListener('resize', function() {
    renderer.setSize(window.innerWidth, window.innerHeight);
    camera.setAspectRatio(window.innerWidth / window.innerHeight);
    camera.updateProjectionMatrix();
    flat.setDimensions(window.innerWidth, window.innerHeight);
  }, false);

  renderer.setSize(window.innerWidth, window.innerHeight);
  camera.setAspectRatio(window.innerWidth / window.innerHeight);
  camera.updateProjectionMatrix();
  flat.setDimensions(window.innerWidth, window.innerHeight);
  tick();
}

main();
