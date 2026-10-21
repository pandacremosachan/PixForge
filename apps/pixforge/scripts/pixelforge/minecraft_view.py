"""Read-only Forge 1.20.1 resource/state scenes for desktop and public clients.

The application resolves sources and emits a self-contained render bundle.
Clients do not import this module or read game resources behind the application.
"""
import base64
from copy import deepcopy
import io
import itertools
import math

from PIL import Image

from .document import StudioError
from .minecraft_target import normalize, resource_id, location
from .minecraft_resources import Audit, digest, encode, parse_json
from .minecraft_sampling import (ITEM_CONTEXTS, RENDER_TYPES, layer_rules, forge_face_data, rgb,
                                 colormap_sample, lightmap, direction_shade, ambient_occlusion)
from .minecraft_geometry import (NORMALS, add, sub, mul, dot, cross, unit, apply, facing,
                                 block_rotation, baked_face, display_transform, display_normal)

CAPABILITY = 'minecraft-preview/v1'
MAX_FACES = 16384
MAX_TEXTURE_PIXELS = 8_388_608
MAX_CASES = 256


def capabilities():
    return {'schema': 'pixforge.minecraft-preview-capabilities/v1', 'capability': CAPABILITY,
            'profiles': ['forge-1.20.1'], 'contexts': ['block', *ITEM_CONTEXTS],
            'render_types': list(RENDER_TYPES), 'mipmap_levels': [0, 1, 2, 3, 4],
            'features': ['source-resolved multi-texture models', 'variants and multipart',
                         'weighted alternatives', 'block rotations and uvlock', 'inherited item display transforms',
                         'generated item layers and alpha edges', 'per-face texel density',
                         'gamma mipmaps and render-layer alpha tests', 'distance sampling and translucent order',
                         'separate block/item tints and source colormaps', 'explicit lightmap and voxel AO samples',
                         'Forge face color/light/AO data', 'read-only batch comparison'],
            'world_scope': 'Controlled preview scene and explicit voxel samples; not a live Minecraft world.',
            'shader_scope': 'Forge 1.20.1 standard render layers; third-party GLSL, PBR and Fabulous postprocessing are not executed.',
            'in_game_validated': False}


def finite(value, low, high, label, integer=False):
    if type(value) not in ((int,) if integer else (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise StudioError(f'{label} 须为 {low}..{high} 的' + ('整数' if integer else '有限数值'))
    return value


def _mapping(value, label):
    if not isinstance(value, dict):
        raise StudioError(label + ' 须为对象')
    return value


def options(value=None):
    value = deepcopy({} if value is None else value)
    allowed = {'subject', 'state', 'context', 'item_model', 'item_properties', 'property_domains', 'seed', 'weighted_choices',
               'arrangement', 'instances', 'render_type', 'mipmap_levels', 'mip_level', 'time_ms', 'environment',
               'block_tints', 'item_tints', 'biome_tint', 'occluders', 'emission_sources', 'self_light', 'ao',
               'camera', 'size', 'background', 'sort_translucent', 'catalog_only', 'use_document'}
    if not isinstance(value, dict) or set(value)-allowed:
        raise StudioError('预览包含未知选项: ' + ', '.join(sorted(set(value)-allowed)) if isinstance(value, dict) else '预览选项须为对象')
    value.setdefault('subject', {'kind': 'document', 'id': 'current'})
    subject = _mapping(value['subject'], 'subject')
    if set(subject)-{'kind', 'id'} or subject.get('kind') not in ('document', 'model', 'blockstate', 'texture'):
        raise StudioError('subject.kind 为 document/model/blockstate/texture')
    subject['id'] = 'current' if subject['kind'] == 'document' else resource_id(subject.get('id'))
    value.setdefault('context', 'block')
    if value['context'] not in ('block', *ITEM_CONTEXTS):
        raise StudioError('无效的 Minecraft 显示场景')
    if value.setdefault('item_model', None) is not None:
        value['item_model'] = resource_id(value['item_model'])
    for name, default in [('state', {}), ('item_properties', {}), ('property_domains', {}), ('weighted_choices', {}),
                          ('block_tints', {}), ('item_tints', {}), ('environment', {}), ('camera', {})]:
        value.setdefault(name, default)
        _mapping(value[name], name)
    for key, n in value['item_properties'].items():
        resource_id(key);finite(n, -1e9, 1e9, 'item_properties/'+key)
    value['state'] = {str(k): str(v).lower() if type(v) is bool else str(v) for k, v in value['state'].items()}
    if len(value['state']) > 32 or any(not k or len(k) > 80 or len(v) > 80 for k, v in value['state'].items()):
        raise StudioError('state 使用最多 32 个有效属性')
    for key, domain in value['property_domains'].items():
        if not isinstance(domain, list) or not domain or len(domain) > 64 or any(type(n) not in (str, bool, int) for n in domain):
            raise StudioError('property_domains 的每个属性须为非空值列表')
        value['property_domains'][key] = [str(n).lower() if type(n) is bool else str(n) for n in domain]
    finite(value.setdefault('seed', 0), -(1 << 31), (1 << 31)-1, 'seed', True)
    for key, n in value['weighted_choices'].items():
        finite(n, 0, 255, 'weighted_choices/'+key, True)
    for name, default in [('ao', True), ('sort_translucent', True), ('catalog_only', False), ('use_document', True)]:
        if type(value.setdefault(name, default)) is not bool:
            raise StudioError(name + ' 须为布尔值')
    finite(value.setdefault('mipmap_levels', 4), 0, 4, 'mipmap_levels', True)
    finite(value.setdefault('mip_level', -1), -1, 4, 'mip_level', True)
    finite(value.setdefault('time_ms', 0), 0, 120000, 'time_ms')
    finite(value.setdefault('self_light', 0), 0, 15, 'self_light', True)
    finite(value.setdefault('size', 512), 96, 1024, 'size', True)
    value.setdefault('background', '#373b44')
    rgb(value['background'])
    value.setdefault('render_type', 'auto')
    if value['render_type'] not in ('auto', *RENDER_TYPES):
        raise StudioError('render_type 为 auto 或 Minecraft 渲染层')
    value.setdefault('arrangement', 'single')
    if value['arrangement'] not in ('single', 'grid', 'glass_layers', 'corner'):
        raise StudioError('arrangement 为 single/grid/glass_layers/corner')
    env = value['environment']
    allowed_env = {'sky_light', 'block_light', 'sky_darken', 'gamma', 'ambient', 'flicker', 'night_vision', 'force_bright'}
    if set(env)-allowed_env:
        raise StudioError('environment 包含未知光照参数')
    for key, default, lo, hi, integer in [('sky_light', 15, 0, 15, True), ('block_light', 0, 0, 15, True),
        ('sky_darken', 1., 0., 1., False), ('gamma', 0., 0., 1., False), ('ambient', 0., 0., 1., False),
        ('flicker', 0., -1., 1., False), ('night_vision', 0., 0., 1., False)]:
        finite(env.setdefault(key, default), lo, hi, 'environment/'+key, integer)
    if type(env.setdefault('force_bright', False)) is not bool:
        raise StudioError('force_bright 须为布尔值')
    camera = value['camera']
    if set(camera)-{'yaw', 'pitch', 'distance', 'projection', 'fov', 'zoom'}:
        raise StudioError('camera 包含未知参数')
    for key, default, lo, hi in [('yaw', 30. if value['context']=='block' else 0., -360., 360.), ('pitch', 25. if value['context']=='block' else 0., -89., 89.),
                               ('distance', 64., 1., 4096.), ('fov', 40., 10., 100.), ('zoom', 1., .05, 16.)]:
        finite(camera.setdefault(key, default), lo, hi, 'camera/'+key)
    if camera.setdefault('projection', 'perspective' if value['context'] == 'block' else 'orthographic') not in ('perspective', 'orthographic'):
        raise StudioError('projection 为 perspective/orthographic')
    for table_name in ('block_tints', 'item_tints'):
        table = value[table_name]
        if len(table) > 64:
            raise StudioError(table_name + ' 最多 64 项')
        for key, color in table.items():
            if not str(key).isdigit() or int(key) > 255:
                raise StudioError('tint index 为 0..255')
            rgb(color)
    value.setdefault('biome_tint', None)
    if value['biome_tint'] is not None:
        biome = _mapping(value['biome_tint'], 'biome_tint')
        if set(biome)-{'mode', 'temperature', 'downfall', 'water_color', 'index', 'item', 'colormap'} or biome.get('mode') not in ('grass', 'foliage', 'water'):
            raise StudioError('biome_tint 使用草色图、叶色图或显式水色')
        finite(biome.setdefault('temperature', .8), 0, 1, 'temperature')
        finite(biome.setdefault('downfall', .4), 0, 1, 'downfall')
        finite(biome.setdefault('index', 0), 0, 255, 'biome tint index', True)
        if type(biome.setdefault('item', False)) is not bool:
            raise StudioError('biome_tint.item 须为布尔值')
        rgb(biome.setdefault('water_color', '#3f76e4'))
        if biome.get('colormap') is not None:biome['colormap']=resource_id(biome['colormap'])
    for name, limit in [('occluders', 256), ('emission_sources', 64), ('instances', 64)]:
        items = value.setdefault(name, [])
        if not isinstance(items, list) or len(items) > limit:
            raise StudioError(f'{name} 使用最多 {limit} 项')
        for item in items:
            _mapping(item, name)
            p = item.get('pos')
            if not isinstance(p, list) or len(p) != 3:
                raise StudioError(name + '.pos 须为三维方块坐标')
            for n in p:
                finite(n, -64, 64, name+'.pos', True)
            if name == 'emission_sources':
                if set(item)-{'pos', 'level'}:
                    raise StudioError('emission_sources 使用 pos/level')
                finite(item.setdefault('level', 15), 0, 15, 'light level', True)
            elif name == 'occluders':
                if set(item)-{'pos', 'shade_brightness', 'sky_light', 'block_light', 'light_block'}:
                    raise StudioError('occluders 使用位置、遮蔽亮度及光照样本')
                finite(item.setdefault('shade_brightness', .2), 0, 1, 'shade_brightness')
                for key, default in [('sky_light', 0), ('block_light', 0), ('light_block', 15)]:
                    finite(item.setdefault(key, default), 0, 15, key, True)
            else:
                if set(item)-{'pos', 'state', 'subject', 'x', 'y'}:
                    raise StudioError('instances 使用 pos/state/subject/x/y')
                if 'subject' in item:
                    candidate = _mapping(item['subject'], 'instances.subject')
                    if set(candidate)-{'kind','id'} or candidate.get('kind') not in ('document','model','blockstate','texture'):
                        raise StudioError('instances.subject 使用有效的 kind/id')
                    candidate['id'] = 'current' if candidate['kind']=='document' else resource_id(candidate.get('id'))
                if 'state' in item:
                    state = _mapping(item['state'], 'instances.state')
                    if len(state)>32 or any(type(k) is not str or not k or type(v) not in (str,bool,int) for k,v in state.items()):
                        raise StudioError('instances.state 须为有效属性对象')
                    item['state'] = {k:str(v).lower() if type(v) is bool else str(v) for k,v in state.items()}
                for key in ('x', 'y'):
                    if item.get(key, 0) not in (0, 90, 180, 270):
                        raise StudioError('实例旋转须为 90 度的整数倍')
    return value


class JavaRandom:
    def __init__(self, seed):
        self.seed = (seed ^ 0x5deece66d) & ((1 << 48)-1)

    def next(self, bits):
        self.seed = (self.seed * 0x5deece66d + 11) & ((1 << 48)-1)
        return self.seed >> (48-bits)

    def weighted_number(self, total):
        self.next(32)
        number = self.next(32)
        number = number - (1 << 32) if number & (1 << 31) else number
        return abs(number) % total if number != -(1 << 31) else -1


def condition(value, state):
    if not value:
        return True
    if 'OR' in value:
        return any(condition(row, state) for row in value['OR'])
    if 'AND' in value:
        return all(condition(row, state) for row in value['AND'])
    for key, wanted in value.items():
        wanted = str(wanted)
        negate = wanted.startswith('!')
        choices = wanted[1:] if negate else wanted
        if key not in state or ((state[key] in choices.split('|')) == negate):
            return False
    return True


def property_values(definition):
    values = {}
    def add_value(key, word):
        words = str(word).removeprefix('!').split('|')
        if set(words) <= {'true', 'false'}:
            words = ['false', 'true']
        values.setdefault(key, set()).update(words)
    for key in definition.get('variants', {}):
        for pair in key.split(',') if key else []:
            name, word = pair.split('=', 1)
            add_value(name, word)
    def visit(value):
        for key, word in value.items():
            if key in ('OR', 'AND'):
                for child in word:
                    visit(child)
            else:
                add_value(key, word)
    for row in definition.get('multipart', []):
        visit(row.get('when', {}))
    return {key: sorted(domain) for key, domain in sorted(values.items())}


def matching_groups(definition, state):
    out = []
    for key, row in definition.get('variants', {}).items():
        required = dict(pair.split('=', 1) for pair in key.split(',')) if key else {}
        if all(state.get(name) == word for name, word in required.items()):
            out.append(('variant:'+key, row if isinstance(row, list) else [row]))
    for index, row in enumerate(definition.get('multipart', [])):
        if condition(row.get('when', {}), state):
            model = row['apply']
            out.append(('multipart:'+str(index), model if isinstance(model, list) else [model]))
    return out


def state_cases(definition, domains=None):
    values = property_values(definition)
    values.update(domains or {})
    if math.prod(len(items) for items in values.values()) > MAX_CASES:
        raise StudioError('状态组合超过 256 项；请通过 property_domains 选择实际注册值或缩小范围')
    cases = []
    for words in itertools.product(*values.values()):
        state = dict(zip(values, words))
        groups = matching_groups(definition, state)
        if not groups:
            continue
        for indices in itertools.product(*(range(len(rows)) for _, rows in groups)):
            cases.append({'state': state, 'weighted_choices': {key: index for (key, _), index in zip(groups, indices)},
                          'models': [rows[index]['model'] for (_, rows), index in zip(groups, indices)]})
            if len(cases) > MAX_CASES:
                raise StudioError('含加权候选的状态组合超过 256 项；请缩小预览入口')
    return values, cases


def frame_at(image, metadata, time_ms):
    animation = metadata.get('animation')
    if animation is None:
        return image, {'frame': 0, 'tick': 0, 'interpolate': False}
    iw, ih = image.size
    fw, fh = animation.get('width'), animation.get('height')
    if fw is None and fh is None:
        fw = fh = min(iw, ih)
    else:
        fw, fh = fw or iw, fh or ih
    sequence = animation.get('frames') or list(range((iw//fw)*(ih//fh)))
    steps = [(row.get('index'), row.get('time', animation.get('frametime', 1))) if isinstance(row, dict)
             else (row, animation.get('frametime', 1)) for row in sequence]
    tick = int(time_ms // 50) % sum(n for _, n in steps)
    at = tick
    for step, (index, duration) in enumerate(steps):
        if at < duration:
            break
        at -= duration
    def crop(n):
        x, y = n % (iw//fw) * fw, n // (iw//fw) * fh
        return image.crop((x, y, x+fw, y+fh))
    result = crop(index)
    if animation.get('interpolate', False) and at and steps[(step+1) % len(steps)][0] != index:
        other = crop(steps[(step+1) % len(steps)][0])
        # Target interpolation keeps the current frame's alpha channel.
        delta = 1-at/duration
        data = [tuple(int(delta*a[c]+(1-delta)*b[c]) for c in range(3))+(a[3],)
                for a, b in zip(result.getdata(), other.getdata())]
        result.putdata(data)
    return result, {'frame': index, 'tick': tick, 'interpolate': animation.get('interpolate', False)}


class SceneBuilder:
    def __init__(self, document, settings=None, view=None):
        self.document, self.view = document, options(view)
        self.config = normalize(settings if settings is not None else document.minecraft_project, document.workspace)
        if self.config is None:
            self.config = normalize({'profile': 'forge-1.20.1', 'namespace': 'pixforge_preview', 'binding': None}, document.workspace)
        overlay, overlay_issues = {}, []
        if self.config['binding'] is not None and self.view['use_document'] and self.view['subject']['kind'] != 'document':
            from .minecraft_export import _binding
            overlay, _, overlay_issues = _binding(document, self.config)
        self.audit = Audit(self.config, overlay=overlay, content_digest=document.art_digest())
        for code, message, severity in overlay_issues:
            self.audit.issue(code, message, severity=severity)
        self.textures, self.faces, self.density, self.particles = {}, [], [], []
        self.sprite_frames = {}
        self.selected, self.catalog = [], {}
        self.samples = {tuple(row['pos']): row for row in self.view['occluders']}
        self.texture_pixels = 0

    def issue(self, code, message, resource=None, severity='warning'):
        self.audit.issue(code, message, resource, severity=severity)

    def _store_texture(self, identifier, image, **extra):
        if identifier in self.textures:
            return identifier
        self.texture_pixels += image.width * image.height
        if self.texture_pixels > MAX_TEXTURE_PIXELS or len(self.textures) >= 256:
            raise StudioError('预览超过 8M 纹理像素或 256 张纹理；请缩小所选场景')
        self.textures[identifier] = {'id': identifier, 'width': image.width, 'height': image.height,
                                    'rgba': base64.b64encode(image.tobytes()).decode('ascii'),
                                    'sha256': digest(image.tobytes()), **extra}
        return identifier

    def texture(self, identifier):
        if identifier in self.textures:
            return identifier
        self.audit.texture(identifier, sprite=True)
        rule = self.audit.sprites.get(identifier, {'type': 'single', 'inputs': [identifier]})
        relative = location('texture', rule['inputs'][0])
        found = self.audit._read(relative)
        if found is None:
            raise StudioError('预览纹理未找到: '+identifier)
        image = Image.open(io.BytesIO(found[0])).convert('RGBA')
        metadata = self.audit._read(relative+'.mcmeta', required=False, minimum=found[2])
        metadata = parse_json(metadata[0]) if metadata else {}
        if self.audit._animation(metadata, image.size, relative+'.mcmeta') is None and 'animation' in metadata:
            raise StudioError('纹理动画元数据无效: '+relative)
        if rule['type'] == 'paletted_permutations':
            key_raw = self.audit._read(location('texture', rule['inputs'][1]))
            palette_raw = self.audit._read(location('texture', rule['inputs'][2]))
            if not key_raw or not palette_raw:
                raise StudioError('缺少实际调色板输入，无法预览派生精灵')
            key = Image.open(io.BytesIO(key_raw[0])).convert('RGBA')
            palette = Image.open(io.BytesIO(palette_raw[0])).convert('RGBA')
            if key.width*key.height != palette.width*palette.height:
                raise StudioError('实际调色板的像素数量不相同')
            mapping = {a[:3]: b for a, b in zip(key.getdata(), palette.getdata()) if a[3]}
            image.putdata([mapping[p[:3]][:3]+(p[3]*mapping[p[:3]][3]//255,) if p[3] and p[:3] in mapping else p for p in image.getdata()])
        animation = metadata.get('animation')
        if animation is None:
            self.sprite_frames[identifier] = [image]
        else:
            fw, fh = animation.get('width'), animation.get('height')
            if fw is None and fh is None:fw = fh = min(image.size)
            else:fw, fh = fw or image.width, fh or image.height
            sequence = animation.get('frames') or list(range((image.width//fw)*(image.height//fh)))
            indices = sorted({row['index'] if isinstance(row,dict) else row for row in sequence})
            self.sprite_frames[identifier] = [image.crop((n%(image.width//fw)*fw,n//(image.width//fw)*fh,
                n%(image.width//fw)*fw+fw,n//(image.width//fw)*fh+fh)) for n in indices]
        image, frame = frame_at(image, metadata, self.view['time_ms'])
        return self._store_texture(identifier, image, animation=frame, source=found[1]['source'], inputs=rule['inputs'])

    def _reference(self, model, reference):
        seen = set()
        while reference.startswith('#'):
            if reference in seen or reference[1:] not in model.get('textures', {}):
                raise StudioError('纹理别名无法解析: '+reference)
            seen.add(reference)
            reference = model['textures'][reference[1:]]
        return resource_id(reference)

    def _biome_color(self):
        settings = self.view['biome_tint']
        if not settings:
            return None
        if settings['mode'] == 'water':
            return rgb(settings['water_color'])
        relative = location('texture', settings.get('colormap') or 'minecraft:colormap/'+settings['mode'])
        found = self.audit._read(relative)
        if not found:
            raise StudioError('需要实际来源中的草色图或叶色图，不能从截图猜测生物群系颜色')
        image = Image.open(io.BytesIO(found[0])).convert('RGBA')
        if image.size != (256, 256):
            raise StudioError('目标草色图或叶色图须为 256×256')
        return colormap_sample(image, settings['temperature'], settings['downfall'])

    def _light(self, point, local, normal, origin, face, model, tint_index, gui_light):
        context, env = self.view['context'], self.view['environment']
        colors = self.view['block_tints' if context == 'block' else 'item_tints']
        tint = rgb(colors[str(tint_index)]) if str(tint_index) in colors and tint_index >= 0 else [255]*4
        biome = self.view['biome_tint']
        if biome and tint_index == biome['index'] and (context == 'block' or biome['item']):
            tint = self.biome_color
        tint = [a*b/255 for a, b in zip(tint, face['color'])]
        if context != 'block':
            if gui_light == 'front':
                shade = 1.
            else:
                directions = [unit((.2, 1., -.7)), unit((-.2, 1., .7))]
                shade = min(1., .4 + .6 * sum(max(0., dot(normal, n)) for n in directions))
            return [n/255 * shade for n in tint[:3]]+[tint[3]/255]
        block = env['block_light']
        for source in self.view['emission_sources']:
            # This explicit unoccluded source is a controlled lighting probe,
            # never an inference that forge_data changes world illumination.
            distance = sum(abs(point[i]/16-(source['pos'][i]+.5)) for i in range(3))
            block = max(block, max(0, source['level']-int(distance)))
        block = max(block, face['block_light'], self.view['self_light'])
        sky = max(env['sky_light'], face['sky_light'])
        light = lightmap(block, sky, **{k: env[k] for k in ('sky_darken','gamma','ambient','flicker','night_vision','force_bright')})
        ao = ambient_occlusion(local, normal, origin, self.samples) if self.view['ao'] and model.get('ambientocclusion', True) and face['ambient_occlusion'] else 1.
        shade = direction_shade(normal, shade=model.get('_face_shade', True), constant_ambient=env['force_bright'])
        return [tint[i]/255 * light[i]/255 * ao * shade for i in range(3)]+[tint[3]/255]

    def _add_model(self, identifier, model, row, instance):
        context = self.view['context']
        render_type = self.view['render_type']
        if render_type == 'auto':
            render_type = model.get('render_type', 'minecraft:solid').removeprefix('minecraft:')
            if 'render_type' not in model:
                self.issue('RENDER_LAYER_FROM_PREVIEW_DEFAULT', '模型未声明 render_type；按 solid 预览，实际注册的渲染层需由项目核对', identifier)
        rules = layer_rules(render_type, context)
        for element_index, element in enumerate(model.get('elements', [])):
            for direction, data in element.get('faces', {}).items():
                texture = self.texture(self._reference(model, data['texture']))
                points, uv, normal, baked_facing = baked_face(element, direction, data, row)
                pose = model.get('_poses', {}).get(element_index)
                if pose:
                    origin_pose = pose['origin']
                    columns = [sub(p, origin_pose) for p in pose['basis']]
                    points = [add(origin_pose, tuple(sum(columns[j][i]*p[j] for j in range(3)) for i in range(3))) for p in points]
                    normal = unit(cross(sub(points[1],points[0]),sub(points[2],points[0])))
                origin = tuple(instance.get('pos', [0, 0, 0]))
                extra = block_rotation(instance.get('x', 0), instance.get('y', 0))
                points = [add(apply(extra, sub(p, (8,8,8))), (8,8,8)) for p in points]
                normal = unit(apply(extra, normal));baked_facing = facing(normal)
                local = points
                world = [add(p, mul(origin, 16)) for p in points]
                cull = data.get('cullface')
                if context == 'block' and cull in NORMALS:
                    combined = apply(extra, apply(block_rotation(row.get('x', 0), row.get('y', 0)), NORMALS[cull]))
                    neighbor = tuple(origin[i]+int(round(combined[i])) for i in range(3))
                    if self.samples.get(neighbor, {}).get('light_block', 0) == 15:
                        continue
                face = forge_face_data(data.get('forge_data', element.get('forge_data')))
                lighting_normal = normal if face['calculate_normals'] else NORMALS[baked_facing]
                if context != 'block':
                    world = [display_transform(p, model, context) for p in points]
                    lighting_normal = display_normal(lighting_normal, model, context)
                colors = [self._light(p, lp, lighting_normal, origin, face,
                                     {**model, '_face_shade': element.get('shade', True)}, data.get('tintindex', -1),
                                     model.get('gui_light', 'side')) for p, lp in zip(world, local)]
                render_uv = [[uv[i][n]*.999+uv[(i+2)%4][n]*.001 for n in range(2)] for i in range(4)]
                self.faces.append({'points': [list(p) for p in world], 'uv': render_uv, 'source_uv': [list(p) for p in uv],
                    'normal': list(normal), 'colors': colors, 'texture': texture, 'layer': rules,
                    'double_sided': False, 'model': identifier, 'element': element_index,
                    'face': direction, 'tintindex': data.get('tintindex', -1), 'forge_data': face})
                tex = self.textures[texture]
                if any(n < -1e-6 or n > 1+1e-6 for pair in uv for n in pair):
                    self.issue('PREVIEW_UV_OUTSIDE_SPRITE', '面 UV 超出精灵范围；预览按边缘采样，图集相邻精灵不可由独立纹理推断', identifier)
                lengths = [math.sqrt(dot(sub(points[3], points[0]), sub(points[3], points[0]))),
                           math.sqrt(dot(sub(points[1], points[0]), sub(points[1], points[0])))]
                spans = [math.hypot((uv[b][0]-uv[a][0])*tex['width'], (uv[b][1]-uv[a][1])*tex['height']) for a,b in [(0,3),(0,1)]]
                density = [16*span/length if length > 1e-9 else None for span, length in zip(spans, lengths)]
                self.density.append({'model': identifier, 'element': element_index, 'face': direction,
                                     'texture': texture, 'texels_per_block': density, 'texture_size': [tex['width'], tex['height']]})
                if len(self.faces) > MAX_FACES:
                    raise StudioError('场景超过 16384 个面；请缩小状态或实例范围')

    def _builtin(self, identifier, seen=None):
        seen = set() if seen is None else seen
        if identifier in seen:
            return None
        if identifier.startswith('minecraft:builtin/'):
            return identifier.split('/')[-1]
        seen.add(identifier)
        raw = self.audit._json(location('model', identifier))
        return self._builtin(resource_id(raw['parent']), seen) if raw and raw.get('parent') else None

    def _model(self, identifier, row, instance):
        self.audit.model(identifier)
        model = self.audit._resolve_model(identifier)
        if model is None:
            return
        if self.view['context'] != 'block':
            props = self.view['item_properties']
            normalized = {resource_id(k): v for k,v in props.items()}
            for override in reversed(model.get('overrides', [])):
                if all(resource_id(key) in normalized and normalized[resource_id(key)] >= n for key,n in override['predicate'].items()):
                    identifier = resource_id(override['model']);model = self.audit._resolve_model(identifier)
                    break
        root = self._builtin(identifier)
        if root == 'entity':
            self.issue('PREVIEW_CUSTOM_RENDERER_REQUIRED', 'builtin/entity 使用实际游戏渲染器，无法由普通元素模型推断', identifier, 'error')
            return
        if root == 'generated':
            model = self._generated(model)
        self.selected.append({'model': identifier, 'rotation': [row.get('x', 0), row.get('y', 0)],
                              'uvlock': row.get('uvlock', False), 'pos': instance.get('pos', [0,0,0])})
        self._add_model(identifier, model, row, instance)

    def _generated(self, model):
        generated = {**deepcopy(model), 'elements': [], 'ambientocclusion': False,
                     'render_type': model.get('render_type', 'minecraft:translucent'), 'gui_light': model.get('gui_light', 'front')}
        for layer in range(5):
            ref = '#layer'+str(layer)
            if ref[1:] not in model.get('textures', {}):
                break
            texture = self.texture(self._reference(model, ref));tex = self.textures[texture]
            w,h = tex['width'],tex['height']
            frames = self.sprite_frames.get(texture) or [Image.frombytes('RGBA',(w,h),base64.b64decode(tex['rgba']))]
            faces = {'south': {'texture': ref, 'tintindex': layer, 'uv': [0,0,16,16]},
                     'north': {'texture': ref, 'tintindex': layer, 'uv': [16,0,0,16]}}
            generated['elements'].append({'from':[0,0,7.5],'to':[16,16,8.5],'faces':faces})
            # The target merges all transitions at the same anchor, across every
            # used animation frame, including gaps between silhouette segments.
            for direction in ('up','down','west','east'):
                outer = h if direction in ('up','down') else w
                inner = w if direction in ('up','down') else h
                dx,dy = {'up':(0,-1),'down':(0,1),'west':(-1,0),'east':(1,0)}[direction]
                for anchor in range(outer):
                    transitions=[]
                    for frame in frames:
                        pixels=frame.load()
                        def alpha(x,y):return 0<=x<w and 0<=y<h and pixels[x,y][3]!=0
                        for at in range(inner):
                            x,y = (at,anchor) if direction in ('up','down') else (anchor,at)
                            if alpha(x,y) and not alpha(x+dx,y+dy):transitions.append(at)
                    if transitions:
                        left,right=min(transitions),max(transitions)+1
                        if direction in ('up','down'):
                            y=(h-anchor-(1 if direction=='down' else 0))*16/h
                            a,b=[left*16/w,y,7.5],[right*16/w,y,8.5]
                            uv=[left*16/w,anchor*16/h,right*16/w,(anchor+1)*16/h]
                        else:
                            x=(anchor+(1 if direction=='east' else 0))*16/w
                            a,b=[x,(h-right)*16/h,7.5],[x,(h-left)*16/h,8.5]
                            uv=[anchor*16/w,right*16/h,(anchor+1)*16/w,left*16/h]
                            # Sprite side labels are reversed in ItemModelGenerator.
                            a[1],b[1]=b[1],a[1]
                        face_direction={'west':'east','east':'west'}.get(direction,direction)
                        generated['elements'].append({'from':a,'to':b,'faces':{face_direction:{'texture':ref,'tintindex':layer,'uv':uv}}})
        return generated

    def _document(self, instance):
        doc = self.document
        plan = doc.animation
        moment = self.view['time_ms'];sample = None
        if doc.scene_animation is not None:
            from .scene_animation import sample as scene_sample
            from .scene_program import texture_control
            sample = scene_sample(doc.scene_animation, doc.shapes['model'], moment)
            texture_view = texture_control(doc.scene_animation, moment)
            moment = texture_view['time_ms']
            held = texture_view.get('frame') if texture_view.get('mode') == 'hold' else None
        else:held=None
        from .texture_animation import frame_at as playback_frame
        frame = held if held is not None else plan['steps'][playback_frame(plan['steps'], moment, plan['loop'])]['frame']
        from .minecraft_animation import sample as sample_texture, enabled as texture_interpolated
        image, _ = sample_texture(doc.canvas.composite(), plan, moment, texture_interpolated(doc), held)
        texture = self._store_texture('pixforge_preview:block/current', image, source='current-document')
        model = deepcopy(doc.shapes['model'])
        if model is None:
            model = {'textures':{'layer0':texture},'gui_light':'front'}
            model = self._generated(model)
        else:
            for element in model['elements']:
                for face in element['faces'].values():face['texture']=texture
            model['textures'] = {'current':texture}
            if sample:model['_poses']={p['element']:p for p in sample['parts']}
        if sample:
            shift = mul(instance.get('pos', [0,0,0]), 16)
            env=self.view['environment'];color=lightmap(env['block_light'],env['sky_light'],**{k:env[k] for k in ('sky_darken','gamma','ambient','flicker','night_vision','force_bright')})
            for particle in sample['particles']:
                self.particles.append({'position':list(add(particle['position'],shift)),'size':particle['size'],
                    'color':[particle['color'][i]/255*color[i]/255 for i in range(3)]+[particle['color'][3]/255],
                    'blend':particle['blend']})
        self.selected.append({'model':'current-document','frame':frame,'pos':instance.get('pos',[0,0,0])})
        self._add_model('current-document', model, {}, instance)


    def _select(self, subject, state, instance):
        kind, identifier = subject['kind'], subject['id']
        if kind == 'document':
            self._document(instance);return
        if kind == 'texture':
            self.texture(identifier)
            model = self._generated({'textures':{'layer0':identifier},'gui_light':'front'})
            self._add_model(identifier, model, {}, instance);return
        if kind == 'model':
            self._model(identifier, {}, instance);return
        self.audit.blockstate(identifier)
        definition = self.audit._json(location('blockstate', identifier))
        if definition is None:return
        domains, cases = state_cases(definition, self.view['property_domains'])
        self.catalog.update(property_values=domains, cases=cases,
                            property_domain_source='explicit' if self.view['property_domains'] else 'declared-resource-conditions')
        if self.view['context']!='block':
            domain,path=identifier.split(':',1);item_model=self.view['item_model'] or domain+':item/'+path
            if self.audit._read(location('model',item_model),required=False) is None:
                self.issue('PREVIEW_ITEM_MODEL_REQUIRED','所选方块未找到实际物品模型；请提供 models/item 资源或显式 item_model，不能用方块状态冒充物品模型',item_model,'error');return
            self._model(item_model,{},instance);return
        if not state and cases:state=cases[0]['state']
        groups = matching_groups(definition, state)
        if not groups:
            self.issue('PREVIEW_STATE_UNMATCHED', '当前属性没有匹配的模型；资源条件不等同于实际注册状态全集', identifier, 'error');return
        for slot, rows in groups:
            if slot in self.view['weighted_choices']:
                index = self.view['weighted_choices'][slot]
                if index >= len(rows):raise StudioError('加权候选索引越界: '+slot)
                row = rows[index]
            else:
                number = JavaRandom(self.view['seed']).weighted_number(sum(r.get('weight',1) for r in rows))
                if number < 0:continue
                row = None
                for candidate in rows:
                    number -= candidate.get('weight',1)
                    if number < 0:row=candidate;break
                if row is None:continue
            self._model(resource_id(row['model']), row, instance)

    def build(self):
        try:
            self.audit._open();self.audit._index_sprites()
            self.biome_color = self._biome_color()
            self.catalog['resources'] = [{'kind':'document','id':'current'}, *[row for row in self.config['entries'] if row['kind'] in ('blockstate','model','texture')]]
            instances = self.view['instances']
            if not instances:
                positions = {'single':[[0,0,0]],'grid':[[x,0,z] for x in (0,1) for z in (0,1)],
                             'glass_layers':[[0,0,z] for z in (0,1,2)],'corner':[[0,0,0]]}[self.view['arrangement']]
                instances = [{'pos':p} for p in positions]
            if self.view['arrangement'] == 'corner' and not self.samples:
                self.samples = {p:{'pos':list(p),'shade_brightness':.2,'light_block':15,'sky_light':0,'block_light':0}
                                for p in [(-1,0,0),(0,-1,0),(-1,-1,0),(0,0,-1),(-1,0,-1),(0,-1,-1)]}
            for instance in instances:
                subject = instance.get('subject', self.view['subject'])
                state = instance.get('state', self.view['state'])
                self._select(subject, state, instance)
            if self.view['catalog_only']:
                self.faces=[];self.textures={};self.density=[]
            densities = [n for row in self.density for n in row['texels_per_block'] if n is not None and n>1e-9]
            if densities and max(densities)/min(densities)>2+1e-6:
                self.issue('PREVIEW_TEXEL_DENSITY_SPREAD','所选模型的面像素密度相差超过两倍；请检查窄支架与大面的实际纹理尺度')
            validation = self.audit.report()
            points = [p for face in self.faces for p in face['points']]
            bounds = [[min(p[i] for p in points) for i in range(3)],[max(p[i] for p in points) for i in range(3)]] if points else [[0,0,0],[16,16,16]]
            scene = {'schema':'pixforge.minecraft-scene/v1','profile':'forge-1.20.1','options':self.view,
                     'textures':list(self.textures.values()),'faces':self.faces,'particles':self.particles,'bounds':bounds,
                     'selected_models':self.selected,'catalog':self.catalog,'density':self.density,
                     'density_summary':{'min':min(densities) if densities else 0,'max':max(densities) if densities else 0},
                     'validation':validation,'document_id':self.document.document_id,'revision':self.document.revision,
                     'content_digest':self.document.art_digest(),'read_only':True,'in_game_validated':False,
                     'coverage':{'rendering':'Standard Forge layers and an explicit controlled preview world.',
                                 'AO':'Full-voxel shade-brightness samples; custom partial occlusion shapes are not inferred.',
                                 'tints':'Explicit block/item color providers or actual source colormap pixels.',
                                 'emission':'Face minimum light is separate from explicitly placed local light probes.',
                                 'shaders':'No third-party GLSL, bloom or Fabulous postprocessing execution.'}}
            scene['coverage']['atlas']='Independent sprite textures with the standard face corner inset; actual atlas packing, atlas-size shrink and neighboring-sprite bleed are not inferred.'
            scene['scene_digest']=digest(encode(scene))
            return scene
        finally:
            for source in self.audit.sources:source.close()


def build_scene(document, *, settings=None, view=None):
    try:
        return SceneBuilder(document, settings, view).build()
    except (ValueError, KeyError, TypeError, OSError, OverflowError) as error:
        if isinstance(error, StudioError):raise
        raise StudioError('Minecraft 预览无法解析当前输入: '+str(error), 'INVALID_MINECRAFT_PREVIEW') from error
