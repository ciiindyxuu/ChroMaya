#version 300 es
precision highp float;

uniform vec3 u_Eye, u_Ref, u_Up;
uniform vec2 u_Dimensions;
uniform float u_Time;
uniform vec3 u_CircleColor;

in vec2 fs_Pos;
out vec4 out_Col;

void main() {
    out_Col = vec4(u_CircleColor, 1.0);
}
