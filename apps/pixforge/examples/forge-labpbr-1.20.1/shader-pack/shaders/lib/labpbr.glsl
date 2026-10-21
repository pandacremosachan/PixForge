// PixForge-owned LabPBR 1.3 decoder. Data samplers are linear UNORM bytes.
struct LabData {
    vec3 normal;
    float ao;
    float height;
    float smoothness;
    float roughness;
    float f0;
    float metal;
    float porosity;
    float sss;
    float emission;
};
LabData labDecode(vec4 n, vec4 s) {
    LabData d;
    vec2 xy = n.rg * 2.0 - 1.0;
    // Invalid XY is rejected by authoring checks. Clamp only avoids NaNs in
    // an unvalidated game resource or the exhaustive numerical diagnostic.
    d.normal = vec3(xy, sqrt(max(0.0, 1.0 - dot(xy, xy))));
    d.ao = n.b;
    d.height = n.a;
    d.smoothness = s.r;
    d.roughness = (1.0 - s.r) * (1.0 - s.r);
    float g = floor(s.g * 255.0 + 0.5);
    float b = floor(s.b * 255.0 + 0.5);
    float a = floor(s.a * 255.0 + 0.5);
    d.metal = g >= 230.0 ? 1.0 : 0.0;
    d.f0 = g < 230.0 ? s.g : 0.0;
    d.porosity = b <= 64.0 ? b / 64.0 : 0.0;
    d.sss = b >= 65.0 ? (b - 65.0) / 190.0 : 0.0;
    d.emission = a < 255.0 ? a / 254.0 : 0.0;
    return d;
}
