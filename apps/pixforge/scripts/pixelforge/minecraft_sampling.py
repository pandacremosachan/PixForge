"""Forge 1.20.1 reference sampling and controlled light/tint calculations.

These functions consume authored pixels and explicit preview-world samples.
They never change a source texture, a document, or the game light engine.
"""
import math
import struct

from PIL import Image


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


POW22 = tuple(f32((f32(i / 255.0)) ** 2.2) for i in range(256))
RENDER_TYPES = ('solid', 'cutout', 'cutout_mipped', 'cutout_mipped_all', 'translucent', 'tripwire')
ITEM_CONTEXTS = ('gui', 'ground', 'fixed', 'head', 'thirdperson_righthand', 'thirdperson_lefthand',
                 'firstperson_righthand', 'firstperson_lefthand')


def layer_rules(name, context='block'):
    name = name.removeprefix('minecraft:')
    if name not in RENDER_TYPES:
        raise ValueError('尚未适配的渲染层: ' + name)
    mipped = name != 'cutout' if context == 'block' else name == 'cutout_mipped_all'
    # Entity cutout uses the entity shader's 0.1 threshold, including the
    # item representation of cutout_mipped. Terrain cutout_mipped uses 0.5.
    cutoff = .5 if context == 'block' and name in ('cutout_mipped', 'cutout_mipped_all') else (
        .1 if name in ('cutout', 'cutout_mipped', 'cutout_mipped_all', 'tripwire') or (context != 'block' and name=='translucent') else 0.)
    return {'name': name, 'mipmapped': mipped, 'alpha_cutoff': cutoff,
            'alpha_test_texture_only': context != 'block',
            'blend': name in ('translucent', 'tripwire'), 'depth_write': True,
            'sampling': 'nearest_mipmap_linear' if mipped else 'nearest'}


def _blend4(values, transparent):
    accum = 0.
    for value, present in values:
        if not transparent or present:
            accum = f32(accum + POW22[value])
    mean = f32(accum / 4.)
    decoded = mean ** (1 / 2.2)
    return max(0, min(255, int((decoded if transparent else f32(decoded)) * 255.)))


def mipmaps(image, levels=4):
    """Gamma-2.2 reduction, with the target's transparent-chain alpha cutoff.

    The transparency branch is chosen once from the original image. Hidden RGB
    in fully transparent input contributes zero, rather than polluting an edge.
    """
    image = image.convert('RGBA')
    limit = min(levels, min(image.size).bit_length() - 1)
    transparent = image.getchannel('A').getextrema()[0] == 0
    out = [image]
    for _ in range(limit):
        source = out[-1]
        w, h = source.size
        pixels = source.load()
        reduced = Image.new('RGBA', (max(1, w // 2), max(1, h // 2)))
        target = reduced.load()
        for y in range(reduced.height):
            for x in range(reduced.width):
                block = [pixels[2*x+dx, 2*y+dy] for dy in (0, 1) for dx in (0, 1)]
                rgba = [_blend4([(p[c], p[3] != 0) for p in block], transparent) for c in range(4)]
                if transparent and rgba[3] < 96:
                    rgba[3] = 0
                target[x, y] = tuple(rgba)
        out.append(reduced)
    return out


def lightmap(block, sky, *, sky_darken=1., gamma=0., ambient=0., flicker=0.,
             night_vision=0., force_bright=False):
    """Deterministic normal-world 1.20.1 lightmap; status effects are explicit."""
    def brightness(level):
        value = level / 15.
        return (value / (4 - 3 * value)) * (1 - ambient) + ambient
    sun = brightness(sky) * (sky_darken * .95 + .05)
    torch = brightness(block) * (1.5 + flicker)
    result = [torch, torch * ((torch * .6 + .4) * .6 + .4), torch * (torch * torch * .6 + .4)]
    if force_bright:
        result = [min(1., max(0., x * .75 + target * .25)) for x, target in zip(result, (.99, 1.12, 1.))]
    else:
        sun_color = (sky_darken * .65 + .35, sky_darken * .65 + .35, 1.)
        result = [(x + sun * color) * .96 + .03 for x, color in zip(result, sun_color)]
    if night_vision and 0 < max(result) < 1:
        peak = max(result)
        result = [x * (1 - night_vision) + x / peak * night_vision for x in result]
    result = [min(1., max(0., x)) for x in result]
    result = [x * (1 - gamma) + (1 - (1 - x) ** 4) * gamma for x in result]
    return tuple(int(min(1., max(0., x * .96 + .03)) * 255) for x in result)


def direction_shade(normal, *, shade=True, constant_ambient=False):
    if not shade:
        return .9 if constant_ambient else 1.
    x, y, z = normal
    return min(1., x*x*.6 + y*y*(.9 if constant_ambient else (3+y)/4) + z*z*.8)


def forge_face_data(value=None):
    if value is None:
        value = {}
    allowed = {'color', 'block_light', 'sky_light', 'ambient_occlusion', 'calculate_normals'}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError('forge_data 仅支持 color/block_light/sky_light/ambient_occlusion/calculate_normals')
    color = value.get('color', 0xffffffff)
    if isinstance(color, str):
        if not color or len(color) > 8 or any(c not in '0123456789abcdefABCDEF' for c in color):
            raise ValueError('Forge 1.20.1 的 forge_data.color 使用不带 0x 的 ARGB 十六进制字符串')
        color = int(color, 16)
    if type(color) is not int or not -(1 << 31) <= color < (1 << 32):
        raise ValueError('forge_data.color 须为 32 位 ARGB 整数或十六进制字符串')
    result = {'color': [(color >> n) & 255 for n in (16, 8, 0, 24)]}
    for name in ('block_light', 'sky_light'):
        n = value.get(name, 0)
        if type(n) is not int or not 0 <= n <= 15:
            raise ValueError(name + ' 须为 0..15 的整数')
        result[name] = n
    for name, default in (('ambient_occlusion', True), ('calculate_normals', False)):
        n = value.get(name, default)
        if type(n) is not bool:
            raise ValueError(name + ' 须为布尔值')
        result[name] = n
    return result


def rgb(value):
    if not isinstance(value, str) or len(value) not in (7, 9) or not value.startswith('#'):
        raise ValueError('颜色使用 #RRGGBB 或 #RRGGBBAA')
    try:
        result = [int(value[n:n+2], 16) for n in (1, 3, 5)]
        result.append(int(value[7:9], 16) if len(value) == 9 else 255)
        return result
    except ValueError:
        raise ValueError('颜色包含无效的十六进制数字') from None


def colormap_sample(image, temperature, downfall):
    """Grass/FoliageColor's clamped climate lookup, using actual source pixels."""
    temperature = max(0., min(1., temperature))
    downfall = max(0., min(1., downfall)) * temperature
    return image.convert('RGBA').getpixel((int((1-temperature)*255), int((1-downfall)*255)))


def ambient_occlusion(position, normal, origin, samples):
    """Trilinear shade-brightness field at the normal-adjusted quad vertex.

    Samples are explicit full-voxel preview-world data. This does not infer a
    consuming mod's collision shapes or registered light-occlusion callbacks.
    """
    at = [min(1., max(-1., p / 16 - .5 + n*.5)) for p, n in zip(position, normal)]
    lower = [math.floor(v) for v in at]
    fraction = [v-lo for v, lo in zip(at, lower)]
    result = 0.
    for x in (0, 1):
        for y in (0, 1):
            for z in (0, 1):
                corner = (x, y, z)
                key = tuple(origin[i] + lower[i] + corner[i] for i in range(3))
                weight = math.prod(fraction[i] if corner[i] else 1-fraction[i] for i in range(3))
                result += samples.get(key, {}).get('shade_brightness', 1.) * weight
    return min(1., max(0., result))
