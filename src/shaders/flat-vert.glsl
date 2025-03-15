#version 300 es
precision highp float;

uniform mat4 u_Model;
uniform mat4 u_ModelInvTr;
uniform mat4 u_ViewProj;

in vec4 vs_Pos;
in vec4 vs_Col;

out vec2 fs_Pos;
out vec4 fs_Col;

void main() {
    fs_Pos = vs_Pos.xy;
    fs_Col = vs_Col;
    gl_Position = u_ViewProj * u_Model * vs_Pos;
}
