#version 300 es
precision highp float;

uniform vec3 u_Eye, u_Ref, u_Up;
uniform vec2 u_Dimensions;
uniform vec3 u_BrushColor;
uniform float u_BrushSize;
uniform vec2 u_BrushPosition;
uniform vec2 u_PrevPosition;
uniform float u_StrokeLength;

in vec2 fs_Pos;
out vec4 out_Col;

// Distance to line segment
float distToSegment(vec2 p, vec2 a, vec2 b) {
    vec2 pa = p - a;
    vec2 ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h);
}

void main() {
    // Calculate distance to line segment
    float dist = distToSegment(fs_Pos, u_PrevPosition, u_BrushPosition);
    
    // Simple circle test for debugging
    // float dist = distance(fs_Pos, u_BrushPosition);
    
    // Discard pixels outside brush radius
    if (dist > u_BrushSize) {
        discard;
    }
    
    // Simple smooth falloff for brush edge
    float alpha = 1.0 - smoothstep(u_BrushSize * 0.7, u_BrushSize, dist);
    
    out_Col = vec4(u_BrushColor, alpha);
} 