#version 300 es
precision highp float;

uniform vec3 u_Eye, u_Ref, u_Up;
uniform vec2 u_Dimensions;
uniform float u_Time;

// Blob data
uniform int u_NumBlobs;
uniform vec3 u_BlobPositions[20]; // Max 20 blobs
uniform float u_BlobRadii[20];
uniform vec3 u_BlobColors[20];
uniform float u_Threshold;

in vec2 fs_Pos;
out vec4 out_Col;

float calculateField(vec2 pos) {
    float field = 0.0;
    
    for (int i = 0; i < 20; i++) {
        if (i >= u_NumBlobs) break;
        
        vec2 blobPos = u_BlobPositions[i].xy;
        float radius = u_BlobRadii[i];
        
        float dx = pos.x - blobPos.x;
        float dy = pos.y - blobPos.y;
        float distSq = dx * dx + dy * dy;
        float dist = sqrt(distSq);
        
        // metaball field function (similar to the one in the paper)
        float influenceRadius = radius * 3.0;
        
        if (dist <= influenceRadius) {
            float t = dist / influenceRadius;
            // quintic interpolation for smoother falloff
            field += (1.0 - t * t * t * (t * (t * 6.0 - 15.0) + 10.0)) * 1.2;
        }
    }
    
    return field;
}

vec3 calculateColor(vec2 pos, float field) {
    // color blending based on field strength and proximity
    vec3 color = vec3(0.0);
    float totalWeight = 0.0;
    
    for (int i = 0; i < 20; i++) {
        if (i >= u_NumBlobs) break;
        
        vec2 blobPos = u_BlobPositions[i].xy;
        float radius = u_BlobRadii[i];
        vec3 blobColor = u_BlobColors[i];
        
        float dx = pos.x - blobPos.x;
        float dy = pos.y - blobPos.y;
        float dist = sqrt(dx * dx + dy * dy);
        
        float influenceRadius = radius * 3.0;
        
        if (dist <= influenceRadius) {
            float t = dist / influenceRadius;
            float weight = (1.0 - t * t * t * (t * (t * 6.0 - 15.0) + 10.0)) * 1.2;
            color += weight * blobColor;
            totalWeight += weight;
        }
    }
    
    if (totalWeight > 0.0) {
        color /= totalWeight;
    }
    
    return color;
}

void main() {
    float field = calculateField(fs_Pos);
    
    // anti-aliased edge
    float edgeWidth = 0.01;
    float alpha = smoothstep(u_Threshold - edgeWidth, u_Threshold + edgeWidth, field);
    
    if (field < u_Threshold - edgeWidth) {
        discard; 
    }
    
    vec3 color = calculateColor(fs_Pos, field);
    
    out_Col = vec4(color, alpha);
} 