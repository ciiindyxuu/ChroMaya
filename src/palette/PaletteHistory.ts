import { vec2, vec3 } from 'gl-matrix';
import Blob from '../geometry/Blob';

// Represents a mixing dish in our palette
export class MixingDish {
  id: number;
  blobs: Blob[] = [];
  parent: MixingDish | null = null;
  children: MixingDish[] = [];
  usedForPainting: boolean = false;
  
  constructor(id: number, parent: MixingDish | null = null) {
    this.id = id;
    this.parent = parent;
    if (parent) {
      parent.children.push(this);
    }
  }
  
  // Deep clone the blobs from another dish
  cloneFrom(dish: MixingDish) {
    this.blobs = dish.blobs.map(blob => {
      const newBlob = new Blob(
        vec3.clone(blob.center as vec3),
        vec3.clone(blob.color),
        blob.radius
      );
      newBlob.create();
      return newBlob;
    });
  }
  
  // Check if this dish is sufficiently different from another
  isDifferentFrom(dish: MixingDish): boolean {
    if (this.blobs.length !== dish.blobs.length) return true;
    
    // Check if any blob has significantly changed
    for (let i = 0; i < this.blobs.length; i++) {
      const thisBlob = this.blobs[i];
      const otherBlob = dish.blobs[i];
      
      // Check position difference
      const posDiff = vec3.distance(
        thisBlob.center as vec3, 
        otherBlob.center as vec3
      );
      if (posDiff > 0.05) return true;
      
      // Check color difference
      const colorDiff = vec3.distance(thisBlob.color, otherBlob.color);
      if (colorDiff > 0.05) return true;
      
      // Check radius difference
      if (Math.abs(thisBlob.radius - otherBlob.radius) > 0.01) return true;
    }
    
    return false;
  }
  
  // Calculate the average color of this dish
  getAverageColor(): vec3 {
    if (this.blobs.length === 0) return vec3.fromValues(1, 1, 1);
    
    const avgColor = vec3.create();
    for (const blob of this.blobs) {
      vec3.add(avgColor, avgColor, blob.color);
    }
    vec3.scale(avgColor, avgColor, 1.0 / this.blobs.length);
    return avgColor;
  }
}

export default class PaletteHistory {
  dishes: MixingDish[] = [];
  activeDish: MixingDish | null = null;
  nextDishId: number = 0;
  
  // Map to track which dish was used to paint each pixel
  // Key is "x,y" string, value is dish ID
  pixelToDishMap: Map<string, number> = new Map();
  
  constructor() {
    this.createNewDish();
  }
  
  createNewDish(parent: MixingDish | null = null): MixingDish {
    const dish = new MixingDish(this.nextDishId++, parent);
    this.dishes.push(dish);
    this.activeDish = dish;
    
    // If this dish has a parent, clone the parent's blobs
    if (parent) {
      dish.cloneFrom(parent);
    }
    
    return dish;
  }
  
  // Set the active dish
  setActiveDish(dish: MixingDish) {
    this.activeDish = dish;
  }
  
  // Get dish by ID
  getDishById(id: number): MixingDish | null {
    return this.dishes.find(dish => dish.id === id) || null;
  }
  
  // Record that a pixel was painted with the active dish
  recordPaintedPixel(x: number, y: number) {
    if (!this.activeDish) return;
    
    const key = `${Math.round(x * 1000)},${Math.round(y * 1000)}`;
    this.pixelToDishMap.set(key, this.activeDish.id);
    this.activeDish.usedForPainting = true;
  }
  
  // Get the dish used to paint a specific pixel
  getDishForPixel(x: number, y: number): MixingDish | null {
    const key = `${Math.round(x * 1000)},${Math.round(y * 1000)}`;
    const dishId = this.pixelToDishMap.get(key);
    if (dishId === undefined) return null;
    return this.getDishById(dishId);
  }
  
  // Create a new dish if the active dish has changed significantly
  checkAndCreateSnapshot(): MixingDish {
    if (!this.activeDish) {
      return this.createNewDish();
    }
    
    // If the active dish has been used for painting and has changed,
    // create a new dish to preserve the history
    if (this.activeDish.usedForPainting) {
      const parent = this.activeDish;
      const newDish = this.createNewDish(parent);
      return newDish;
    }
    
    return this.activeDish;
  }
  
  // Propagate color changes from a dish to its descendants
  propagateColorChanges(dish: MixingDish, originalBlobs: Blob[]) {
    // For each child dish
    for (const childDish of dish.children) {
      let childChanged = false;
      
      // Update each blob in the child dish if it matches a blob in the parent
      for (let i = 0; i < childDish.blobs.length; i++) {
        const childBlob = childDish.blobs[i];
        
        // Find the corresponding original blob
        for (let j = 0; j < originalBlobs.length; j++) {
          const originalBlob = originalBlobs[j];
          const updatedBlob = dish.blobs[j];
          
          // If positions are very close, this might be the same blob
          const posDiff = vec3.distance(
            childBlob.center as vec3, 
            originalBlob.center as vec3
          );
          
          // If colors are very close, this blob hasn't been modified
          const colorDiff = vec3.distance(
            childBlob.color, 
            originalBlob.color
          );
          
          // If this blob in the child matches an original blob that was updated
          if (posDiff < 0.05 && colorDiff < 0.05) {
            // Update the child blob's color to match the updated parent blob
            vec3.copy(childBlob.color, updatedBlob.color);
            childBlob.create();
            childChanged = true;
            break;
          }
        }
      }
      
      // Recursively propagate changes to this child's descendants
      if (childChanged) {
        this.propagateColorChanges(childDish, originalBlobs);
      }
    }
  }
} 