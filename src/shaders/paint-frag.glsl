#version 300 es
precision highp float;

uniform vec3 u_Eye, u_Ref, u_Up;
uniform vec2 u_Dimensions;
uniform float u_Time;
uniform vec3 u_PaintColor;
uniform float u_PaintSize;
uniform vec2 u_PaintPosition;

in vec2 fs_Pos;
out vec4 out_Col;

void main() {
    float dist = distance(fs_Pos, u_PaintPosition);
    
    if (dist > u_PaintSize) {
        discard;
    }
    
    // Smooth circle edge
    float alpha = smoothstep(u_PaintSize, u_PaintSize - 0.01, dist);
    out_Col = vec4(u_PaintColor, alpha);
}