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
import PaintRenderer from './rendering/gl/PaintRenderer';

const controls = {
  tesselations: 5,
  'Load Scene': loadScene, 
  color: "#ff0000", 
  blobRadius: 0.1,
  threshold: 0.5,
  paintingMode: false,
  brushSize: 0.05,
  clearPainting: () => {
    paintStrokes = [];
  }
};

let square: Square;
let blobs: Blob[] = [];
let time: number = 0;
let isDragging = false;
let selectedBlob: Blob | null = null;
let activeColorPickerBlob: Blob | null = null;
let isPaintingMode = false;
let currentBrushColor = vec3.fromValues(1, 0, 0); // Default red
let brushSize = 0.05;
let paintStrokes: {position: vec2, color: vec3, size: number}[] = [];

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

function rgbToHex(r: number, g: number, b: number): string {
  r = Math.round(r * 255);
  g = Math.round(g * 255);
  b = Math.round(b * 255);
  return '#' + 
    (r < 16 ? '0' : '') + r.toString(16) + 
    (g < 16 ? '0' : '') + g.toString(16) + 
    (b < 16 ? '0' : '') + b.toString(16);
}

function updateColorPalette() {
  const container = document.getElementById('color-palette-container');
  container.innerHTML = '';
  
  // Add current brush color
  const currentColorSwatch = document.createElement('div');
  currentColorSwatch.style.width = '30px';
  currentColorSwatch.style.height = '30px';
  currentColorSwatch.style.backgroundColor = rgbToHex(
    currentBrushColor[0], 
    currentBrushColor[1], 
    currentBrushColor[2]
  );
  currentColorSwatch.style.border = '2px solid black';
  currentColorSwatch.style.margin = '2px';
  currentColorSwatch.title = 'Current Brush Color';
  container.appendChild(currentColorSwatch);
  
  // Add colors from blobs
  const uniqueColors = new Map<string, vec3>();
  
  for (const blob of blobs) {
    const hexColor = rgbToHex(blob.color[0], blob.color[1], blob.color[2]);
    uniqueColors.set(hexColor, blob.color);
  }
  
  uniqueColors.forEach((color, hexColor) => {
    const swatch = document.createElement('div');
    swatch.style.width = '20px';
    swatch.style.height = '20px';
    swatch.style.backgroundColor = hexColor;
    swatch.style.margin = '2px';
    swatch.style.cursor = 'pointer';
    swatch.title = 'Click to use this color';
    swatch.addEventListener('click', () => {
      currentBrushColor = vec3.clone(color);
      updateColorPalette(); // Refresh to show new current color
    });
    container.appendChild(swatch);
  });
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

  const paintingFolder = gui.addFolder('Painting');
  paintingFolder.add(controls, 'paintingMode').name('Painting Mode').onChange((value) => {
    isPaintingMode = value;
    document.getElementById('canvas').style.cursor = value ? 'crosshair' : 'default';
  });
  paintingFolder.add(controls, 'brushSize', 0.01, 0.1).name('Brush Size').onChange((value) => {
    brushSize = value;
  });
  paintingFolder.add(controls, 'clearPainting').name('Clear Painting');
  paintingFolder.open();

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

  const paintShader = new ShaderProgram([
    new Shader(gl.VERTEX_SHADER, require('./shaders/paint-vert.glsl')),
    new Shader(gl.FRAGMENT_SHADER, require('./shaders/paint-frag.glsl')),
  ]);
  
  const paintRenderer = new PaintRenderer(paintShader);

  canvas.addEventListener('mousedown', (event) => {
    const pos = getClipSpaceMousePosition(event, canvas);
    
    if (isPaintingMode) {
      if (event.altKey) {
        // Sample color from metaballs at this position
        const pos = getClipSpaceMousePosition(event, canvas);
        
        // Calculate the field value at this position
        let field = 0.0;
        for (const blob of blobs) {
          field += blob.getInfluence(pos.x, pos.y);
        }
        
        // Only sample if we're inside the metaball field
        if (field >= controls.threshold) {
          // Calculate the blended color at this position (similar to shader logic)
          let totalColor = vec3.create();
          let totalWeight = 0.0;
          
          for (const blob of blobs) {
            const influence = blob.getInfluence(pos.x, pos.y);
            if (influence > 0) {
              vec3.scaleAndAdd(totalColor, totalColor, blob.color, influence);
              totalWeight += influence;
            }
          }
          
          if (totalWeight > 0) {
            // Normalize the color
            vec3.scale(totalColor, totalColor, 1.0 / totalWeight);
            currentBrushColor = totalColor;
            updateColorPalette();
          }
        }
        return;
      } else {
        // Add a paint stroke
        paintStrokes.push({
          position: vec2.fromValues(pos.x, pos.y),
          color: vec3.clone(currentBrushColor),
          size: brushSize
        });
      }
      return; // Important: return here to prevent blob creation
    }
    
    // Only execute this code if NOT in painting mode
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
    if (isPaintingMode && event.buttons === 1) {
      const pos = getClipSpaceMousePosition(event, canvas);
      paintStrokes.push({
        position: vec2.fromValues(pos.x, pos.y),
        color: vec3.clone(currentBrushColor),
        size: brushSize
      });
      return;
    }
    
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

  canvas.addEventListener('dblclick', (event) => {
    const pos = getClipSpaceMousePosition(event, canvas);
    
    for (let i = blobs.length - 1; i >= 0; i--) {
      const blob = blobs[i];
      const dx = pos.x - blob.center[0];
      const dy = pos.y - blob.center[1];
      const distance = Math.sqrt(dx * dx + dy * dy);
      
      if (distance < blob.radius) { 
        // Show color picker near the blob
        const colorPickerContainer = document.getElementById('color-picker-container');
        const colorPicker = document.getElementById('blob-color-picker') as HTMLInputElement;
        
        // Convert blob's current color to hex for the color picker
        const r = Math.round(blob.color[0] * 255);
        const g = Math.round(blob.color[1] * 255);
        const b = Math.round(blob.color[2] * 255);
        const hexColor = '#' + 
          (r < 16 ? '0' : '') + r.toString(16) + 
          (g < 16 ? '0' : '') + g.toString(16) + 
          (b < 16 ? '0' : '') + b.toString(16);
        
        colorPicker.value = hexColor;
        
        // Position the color picker near the blob in screen space
        const rect = canvas.getBoundingClientRect();
        const screenX = ((blob.center[0] + 1) / 2) * canvas.width + rect.left;
        const screenY = ((1 - (blob.center[1] + 1) / 2)) * canvas.height + rect.top;
        
        colorPickerContainer.style.left = `${screenX + 20}px`;
        colorPickerContainer.style.top = `${screenY}px`;
        colorPickerContainer.style.display = 'block';
        
        // Store reference to the blob being edited
        activeColorPickerBlob = blob;
        
        // Prevent default behavior to avoid canvas interactions
        event.preventDefault();
        return;
      }
    }
  });

  // Add this after creating the color picker in the main function
  const colorPicker = document.getElementById('blob-color-picker') as HTMLInputElement;
  const colorPickerContainer = document.getElementById('color-picker-container');

  // Update blob color when the color picker changes
  colorPicker.addEventListener('input', () => {
    if (activeColorPickerBlob) {
      const rgb = hexToRgb(colorPicker.value);
      activeColorPickerBlob.color = vec3.fromValues(rgb.r, rgb.g, rgb.b);
      activeColorPickerBlob.create();
    }
  });

  // Hide the color picker when clicking outside
  document.addEventListener('click', (event) => {
    if (event.target !== colorPicker && activeColorPickerBlob) {
      colorPickerContainer.style.display = 'none';
      activeColorPickerBlob = null;
    }
  });

  // Also hide the color picker when the color is selected
  colorPicker.addEventListener('change', () => {
    colorPickerContainer.style.display = 'none';
    activeColorPickerBlob = null;
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
    
    // Update color palette if blobs have changed
    updateColorPalette();
    
    // Render paint strokes first (behind metaballs)
    if (paintStrokes.length > 0) {
      paintRenderer.render(camera, paintStrokes);
    }
    
    // Render metaballs
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
    paintShader.setDimensions(window.innerWidth, window.innerHeight);
  }, false);

  renderer.setSize(window.innerWidth, window.innerHeight);
  camera.setAspectRatio(window.innerWidth / window.innerHeight);
  camera.updateProjectionMatrix();
  metaballShader.setDimensions(window.innerWidth, window.innerHeight);
  paintShader.setDimensions(window.innerWidth, window.innerHeight);

  // Add a color palette div to the DOM
  const colorPaletteContainer = document.createElement('div');
  colorPaletteContainer.id = 'color-palette-container';
  colorPaletteContainer.style.position = 'absolute';
  colorPaletteContainer.style.bottom = '10px';
  colorPaletteContainer.style.left = '10px';
  colorPaletteContainer.style.display = 'flex';
  colorPaletteContainer.style.flexWrap = 'wrap';
  colorPaletteContainer.style.maxWidth = '300px';
  colorPaletteContainer.style.background = 'rgba(255, 255, 255, 0.7)';
  colorPaletteContainer.style.padding = '5px';
  colorPaletteContainer.style.borderRadius = '5px';
  document.body.appendChild(colorPaletteContainer);

  // Add this after creating the color palette container
  const instructionsElement = document.createElement('div');
  instructionsElement.style.position = 'absolute';
  instructionsElement.style.top = '10px';
  instructionsElement.style.left = '10px';
  instructionsElement.style.background = 'rgba(255, 255, 255, 0.7)';
  instructionsElement.style.padding = '10px';
  instructionsElement.style.borderRadius = '5px';
  instructionsElement.style.maxWidth = '300px';
  instructionsElement.innerHTML = `
    <h3>Instructions:</h3>
    <ul>
      <li>Click to create blobs</li>
      <li>Drag to move blobs</li>
      <li>Right-click to delete blobs</li>
      <li>Double-click to change blob color</li>
      <li>Toggle Painting Mode to paint with blob colors</li>
      <li>Alt+Click in painting mode to sample colors</li>
    </ul>
  `;
  document.body.appendChild(instructionsElement);

  tick();
}

main();
