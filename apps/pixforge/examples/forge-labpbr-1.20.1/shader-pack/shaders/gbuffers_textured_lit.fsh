#version 120
/* DRAWBUFFERS:0 */
#include "/lib/labpbr.glsl"
uniform sampler2D gtexture;
uniform sampler2D lightmap;
uniform sampler2D normals;
uniform sampler2D specular;
uniform vec3 sunPosition;
varying vec2 texcoord;
varying vec2 lightcoord;
varying vec4 vertexColor;
varying vec3 viewPosition;
varying vec3 viewNormal;
vec3 linearColor(vec3 value) {
    return mix(value / 12.92, pow((value + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), value));
}
vec3 displayColor(vec3 value) {
    return mix(value * 12.92, 1.055 * pow(max(value, vec3(0.0)), vec3(1.0/2.4)) - 0.055, step(vec3(0.0031308), value));
}
void main() {
    vec4 albedo = texture2D(gtexture, texcoord) * vertexColor;
    if (albedo.a < 0.1) discard;
    vec4 normalData = vec4(128.0/255.0, 128.0/255.0, 1.0, 1.0);
    vec4 specularData = vec4(0.0, 10.0/255.0, 0.0, 1.0);
#ifdef MC_NORMAL_MAP
    normalData = texture2D(normals, texcoord);
#endif
#ifdef MC_SPECULAR_MAP
    specularData = texture2D(specular, texcoord);
#endif
    LabData data = labDecode(normalData, specularData);
    vec3 base = linearColor(albedo.rgb);
    vec3 n = normalize(viewNormal);
    vec3 dpdx = dFdx(viewPosition), dpdy = dFdy(viewPosition);
    vec2 duvdx = dFdx(texcoord), duvdy = dFdy(texcoord);
    float det = duvdx.x * duvdy.y - duvdx.y * duvdy.x;
    if (abs(det) > 0.00000001) {
        vec3 tangent = (dpdx * duvdy.y - dpdy * duvdx.y) / det;
        vec3 bitangent = (-dpdx * duvdy.x + dpdy * duvdx.x) / det;
        tangent = normalize(tangent - n * dot(tangent,n));
        bitangent = normalize(bitangent - n * dot(bitangent,n));
        // Basis follows +U/+V. DirectX green points toward image-down +V.
        n = normalize(tangent * data.normal.x + bitangent * data.normal.y + n * data.normal.z);
    }
    vec3 l = length(sunPosition)>0.00001 ? normalize(sunPosition) : normalize(vec3(0.3,0.8,0.4));
    vec3 v = normalize(-viewPosition), h = normalize(l+v);
    float nl=max(dot(n,l),0.0), nv=max(dot(n,v),0.001), nh=max(dot(n,h),0.0), vh=max(dot(v,h),0.0);
    // A diagnostic GGX surface, without POM, SSR, porosity, SSS or named metals.
    // All metals use the standard albedo-F0 fallback in this small probe pack.
    vec3 f0=mix(vec3(data.f0),base,data.metal);
    vec3 fresnel=f0+(1.0-f0)*pow(1.0-vh,5.0);
    float alpha=max(data.roughness*data.roughness,0.002), aa=alpha*alpha;
    float denominator=nh*nh*(aa-1.0)+1.0;
    float distribution=aa/(3.14159265*denominator*denominator);
    float k=(data.roughness+1.0)*(data.roughness+1.0)/8.0;
    float geometry=nv/(nv*(1.0-k)+k)*nl/(nl*(1.0-k)+k);
    vec3 spec=distribution*geometry*fresnel/max(4.0*nv*nl,0.001);
    vec3 diffuse=(1.0-fresnel)*(1.0-data.metal)*base/3.14159265;
    vec3 light=linearColor(texture2D(lightmap,lightcoord).rgb);
    vec3 color=(diffuse+spec)*nl*2.0+base*light*data.ao*0.35+base*data.emission*2.0;
    color=color/(1.0+color);
    // Only ALBEDO alpha controls opacity. Data texture alpha never does.
    gl_FragData[0]=vec4(displayColor(color),albedo.a);
}
