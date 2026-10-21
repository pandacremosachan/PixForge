"""LabPBR 1.3 byte data, separate from color layers and alpha compositing."""
from copy import copy, deepcopy
import base64
from collections import Counter
import hashlib
import io
import json
import math
from pathlib import Path
import re
import zipfile

from PIL import Image, ImageDraw
from .document import StudioError

SCHEMA = 'pixforge.material-data/v1'
CAPABILITY = 'minecraft-material/v1'
PROFILE = 'labpbr-1.3'
ROLES = ('normal', 'specular')
DEFAULTS = {'normal': (128,128,255,255), 'specular': (0,10,0,255)}
FEATURES = ('normals','smoothness','f0','hardcoded_metals','ao','height','porosity','sss','emission')
CHANNELS = {'normal': ('normal_x','normal_y_directx','material_ao','height'),
            'specular': ('perceptual_smoothness','f0_or_metal','porosity_or_sss','emission')}
METALS = ('iron','gold','aluminum','chrome','copper','lead','platinum','silver')
MAX_PIXELS = 16_777_216
MAX_PNG = 32*1024*1024
REFERENCES = ['https://shaderlabs.org/index.php?title=LabPBR_Material_Standard&oldid=935',
              'https://shaderlabs.org/index.php?title=LabPBR_Implementation_Requirements&oldid=878',
              'https://github.com/sp614x/optifine/blob/master/OptiFineDoc/doc/texture.properties']


def fail(message, code='INVALID_MATERIAL_DATA'):
    raise StudioError(message, code)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def _pixels(image):return image.get_flattened_data() if hasattr(image,'get_flattened_data') else image.getdata()


def png(image):
    # A new image deliberately strips gamma/ICC/transparency metadata. RGBA bytes
    # including RGB hidden behind alpha=0 are copied, never alpha-composited.
    stream=io.BytesIO();Image.frombytes('RGBA',image.size,image.tobytes()).save(stream,format='PNG')
    raw=stream.getvalue()
    if len(raw)>MAX_PNG:fail('数据 PNG 超过 32 MiB，请减少图集尺寸')
    return raw


def read_png(raw, size=None):
    if not isinstance(raw,bytes) or len(raw)>MAX_PNG or not raw.startswith(b'\x89PNG\r\n\x1a\n'):
        fail('数据贴图须为不超过 32 MiB 的 PNG')
    try:
        image=Image.open(io.BytesIO(raw))
        if image.format!='PNG' or raw[24]!=8 or image.mode not in ('RGB','RGBA','L','LA','P') or image.width*image.height>MAX_PIXELS:
            fail('数据贴图使用 8 bit PNG，最多 16M 像素；16 bit 数据须先显式转换')
        if getattr(image,'n_frames',1)!=1:fail('APNG 不作为数据图集导入；使用显式帧条及 .mcmeta')
        if size is not None and image.size!=tuple(size):fail('数据图集尺寸必须与原生颜色图集完全一致；不会自动缩放')
        image.load();return image.convert('RGBA')
    except (OSError,ValueError,Image.DecompressionBombError) as error:
        if isinstance(error,StudioError):raise
        fail('无法解码数据 PNG：'+str(error))


def pack(image):return {'size':list(image.size),'png':base64.b64encode(png(image)).decode('ascii'),'rgba_sha256':sha(image.tobytes())}


def unpack(row):
    try:raw=base64.b64decode(row['png'],validate=True)
    except (KeyError,ValueError,TypeError):fail('数据贴图编码无效')
    image=read_png(raw,row.get('size'))
    if sha(image.tobytes())!=row.get('rgba_sha256'):fail('数据贴图 RGBA 指纹不匹配')
    return image


def target(value, base=None):
    if value is None:return None
    if not isinstance(value,dict) or set(value)-{'name','version','loader','loader_version','features','path','sha256','options','minecraft','forge'}:
        fail('着色器目标使用 name/version/loader/loader_version/features/path/sha256/options/minecraft/forge')
    out={}
    for key in ('name','version','loader','loader_version'):
        v=value.get(key)
        if not isinstance(v,str) or not v.strip() or len(v)>160:fail('着色器目标须明确填写 '+key)
        out[key]=v.strip()
    feature=value.get('features',{})
    if not isinstance(feature,dict) or set(feature)-set(FEATURES) or any(v is not None and type(v) is not bool for v in feature.values()):fail('features 使用受支持的能力名及 true/false/null')
    out['features']={k:feature.get(k) for k in FEATURES}
    options=value.get('options',{})
    if not isinstance(options,dict) or len(json.dumps(options))>8192 or any(not isinstance(k,str) or not isinstance(v,(str,int,float,bool)) or type(v) is float and not math.isfinite(v) for k,v in options.items()):fail('着色器选项使用至多 8 KiB 的有限标量对象')
    out['options']=deepcopy(options)
    for key in ('minecraft','forge'):
        if key in value:
            if not isinstance(value[key],str) or not value[key].strip() or len(value[key])>40:fail('着色器目标 '+key+' 使用明确版本文字')
            out[key]=value[key]
    if value.get('path'):
        if not isinstance(value['path'],str):fail('着色器来源 path 使用路径文字')
        p=Path(value['path']).expanduser()
        if not p.is_absolute():p=Path(base or Path.cwd())/p
        out['path']=str(p.resolve())
    if value.get('sha256'):
        if not isinstance(value['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',value['sha256']):fail('着色器 SHA-256 使用 64 位小写十六进制')
        out['sha256']=value['sha256']
    return out


def normalize(value, size, base=None):
    if value is None:return None
    if not isinstance(value,dict) or set(value)-{'schema','profile','maps','target'} or value.get('schema',SCHEMA)!=SCHEMA or value.get('profile')!=PROFILE:fail('数据材质仅接受明确的 labpbr-1.3 格式')
    maps=value.get('maps')
    if not isinstance(maps,dict) or not maps or set(maps)-set(ROLES):fail('数据贴图至少包含 normal/specular 中的一项')
    out={}
    for role,row in maps.items():
        if not isinstance(row,dict) or set(row)!={'size','png','rgba_sha256'} or row.get('size')!=list(size):fail('数据贴图尺寸或字段无效')
        unpack(row);out[role]=deepcopy(row)
    return {'schema':SCHEMA,'profile':PROFILE,'maps':out,'target':target(value.get('target'),base)}


def configure(document, settings):
    if settings is None:return None
    if not isinstance(settings,dict) or set(settings)-{'profile','maps','target'} or settings.get('profile',PROFILE)!=PROFILE:fail('配置使用 profile=labpbr-1.3、maps 和 target')
    old=document.material_data or {};roles=settings.get('maps',list(old.get('maps',{})) or list(ROLES))
    if not isinstance(roles,list) or not roles or len(roles)!=len(set(roles)) or any(r not in ROLES for r in roles):fail('maps 使用不重复的 normal/specular 列表')
    size=(document.canvas.w,document.canvas.h)
    if math.prod(size)>MAX_PIXELS:fail('PBR 图集超过 16M 像素')
    maps={r:deepcopy(old['maps'][r]) if r in old.get('maps',{}) else pack(Image.new('RGBA',size,DEFAULTS[r])) for r in roles}
    shader=target(settings['target'],document.workspace) if 'target' in settings else deepcopy(old.get('target'))
    return {'schema':SCHEMA,'profile':PROFILE,'maps':maps,'target':shader}


def summary(data):
    if data is None:return None
    return {'schema':SCHEMA,'profile':data['profile'],'maps':{r:{'size':m['size'],'rgba_sha256':m['rgba_sha256'],'channels':list(CHANNELS[r])} for r,m in data['maps'].items()},'target':deepcopy(data['target']),'alpha_is_opacity':False}


def channel_index(role, channel):
    if role not in ROLES:fail('map 使用 normal/specular')
    if type(channel) is int and 0<=channel<4:return channel
    if channel in ('r','g','b','a'):return ('r','g','b','a').index(channel)
    if channel in CHANNELS[role]:return CHANNELS[role].index(channel)
    fail('channel 使用 r/g/b/a、0..3 或对应的通道语义名')


def decode(normal, specular):
    r,g,b,a=normal;x,y=r/127.5-1,g/127.5-1;q=1-x*x-y*y
    s,f,p,e=specular
    metal=METALS[f-230] if 230<=f<=237 else 'reserved' if 238<=f<=254 else 'albedo' if f==255 else None
    return {'normal_directx':[x,y,math.sqrt(max(0,q))],'normal_unit_disk_valid':q>=0,
        'ao':b/255,'height':a/255,'depth_in_texture':(1-a/255)*.25,
        'perceptual_smoothness':s/255,'linear_roughness':(1-s/255)**2,
        'f0':f/255 if f<230 else None,'metal':metal,
        'porosity':p/64 if p<=64 else 0,'sss':(p-65)/190 if p>=65 else 0,
        'emission':e/254 if e<255 else 0,'emission_alpha_255_ignored':e==255}


def shader_probe(shader):
    """Fingerprint a supplied pack. Feature support remains an explicit project declaration."""
    if shader is None:return {'bound':False,'support_evidence':'unbound','observed_in_game':False}
    result={'bound':True,'declaration':deepcopy(shader),'support_evidence':'project-declared; GLSL is not executed by this inspection','observed_in_game':False}
    if 'path' not in shader:return result
    path=Path(shader['path']);items=[]
    if path.is_dir():
        root=path.resolve();total=0
        for p in sorted(path.rglob('*')):
            if p.is_file():
                if not p.resolve().is_relative_to(root):fail('着色器目录的链接越出来源')
                total+=p.stat().st_size
                if len(items)>=8192 or p.stat().st_size>MAX_PNG or total>128*1024*1024:fail('着色器来源超过检查预算')
                items.append((p.relative_to(root).as_posix(),p.read_bytes()))
        fingerprint=sha(b''.join(n.encode()+b'\0'+sha(b).encode()+b'\n' for n,b in items))
    elif path.is_file() and path.suffix.lower()=='.zip':
        if path.stat().st_size>512*1024*1024:fail('着色器 ZIP 超过 512 MiB')
        fingerprint=sha(path.read_bytes())
        with zipfile.ZipFile(path) as z:
            names=z.namelist()
            if len(names)>8192 or len(names)!=len(set(names)):fail('着色器 ZIP 条目过多或重名')
            for info in z.infolist():
                if info.is_dir():continue
                if info.filename.startswith('/') or '\\' in info.filename or '..' in Path(info.filename).parts or info.file_size>MAX_PNG:fail('着色器 ZIP 路径或文件大小无效')
                if info.filename.endswith('shaders.properties'):items.append((info.filename,z.read(info)))
    else:fail('着色器来源须为存在的目录或 ZIP')
    result.update(sha256=fingerprint,source_file_count=len(items),expected_sha256_matches=not shader.get('sha256') or shader['sha256']==fingerprint,shader_properties=[n for n,b in items if n.endswith('shaders.properties')])
    return result


def report(data):
    if data is None:return {'schema':'pixforge.material-report/v1','configured':False,'profile':PROFILE,'capability':CAPABILITY,'references':REFERENCES,'passed':True,'issues':[],'in_game_validated':False}
    issues=[];maps={};used={'smoothness','f0','normals'}
    def issue(code,message,severity='error',**details):issues.append({'code':code,'message':message,'severity':severity,**details})
    images={r:unpack(m) for r,m in data['maps'].items()}
    for role,image in images.items():
        hist=[Counter(_pixels(c)) for c in image.split()]
        maps[role]={'size':list(image.size),'rgba_sha256':sha(image.tobytes()),'channels':{CHANNELS[role][i]:{'minimum':min(h),'maximum':max(h),'mean':sum(k*v for k,v in h.items())/(image.width*image.height),'distinct_values':len(h),'histogram':{str(k):v for k,v in sorted(h.items())}} for i,h in enumerate(hist)}}
        if role=='normal':
            invalid=sum(c for (r,g),c in Counter((p[0],p[1]) for p in _pixels(image)).items() if (r/127.5-1)**2+(g/127.5-1)**2>1)
            if invalid:issue('PBR_NORMAL_UNIT_DISK',f'{invalid} 个法线 XY 超出单位圆；目标 sqrt(1-dot(xy,xy)) 无有效实数 Z',pixels=invalid)
            if min(hist[2])<255:used.add('ao')
            if min(hist[3])<255:used.add('height')
            if 0 in hist[3]:issue('PBR_ZERO_HEIGHT','高度 0 可导致部分着色器的 POM 问题；检查目标实现，软件保留原始值','warning',pixels=hist[3][0])
        else:
            if max(hist[1])>=230:used.add('hardcoded_metals') if any(230<=v<=254 for v in hist[1]) else None
            reserved=sum(n for v,n in hist[1].items() if 238<=v<=254)
            if reserved:issue('PBR_RESERVED_METAL','绿通道包含 238..254 的未命名金属值；不同着色器可能采用不同回退','warning',pixels=reserved)
            if any(1<=v<=64 for v in hist[2]):used.add('porosity')
            if any(v>65 for v in hist[2]):used.add('sss')
            if any(0<v<255 for v in hist[3]):used.add('emission')
            maps[role]['emission_alpha_255_ignored_pixels']=hist[3].get(255,0)
    try:probe=shader_probe(data['target'])
    except (OSError,ValueError,zipfile.BadZipFile) as error:
        issue('PBR_SHADER_SOURCE',str(error));probe={'bound':bool(data['target']),'observed_in_game':False}
    if not probe['bound']:issue('PBR_SHADER_UNBOUND','尚未绑定明确版本的着色器；可导出 LabPBR 数据，实际效果需在消费项目验证','warning')
    else:
        if 'path' not in data['target']:issue('PBR_SHADER_SOURCE_UNBOUND','目标记录了名称和版本，尚未绑定本机来源；能力声明不代替实际着色器加载证据','warning')
        if probe.get('expected_sha256_matches') is False:issue('PBR_SHADER_CHANGED','着色器来源与目标记录的 SHA-256 不一致')
        for name in sorted(used):
            support=data['target']['features'][name]
            if support is False:issue('PBR_SHADER_UNSUPPORTED',f'目标声明不支持当前使用的 {name}',feature=name)
            elif support is None:issue('PBR_SHADER_SUPPORT_UNKNOWN',f'目标未明确声明 {name} 支持情况','warning',feature=name)
    return {'schema':'pixforge.material-report/v1','configured':True,'profile':PROFILE,'maps':maps,'features_used':sorted(used),'shader':probe,'issues':issues,'passed':not any(i['severity']=='error' for i in issues),'normal_convention':'DirectX Y-; +green points down; Z reconstructed from XY','alpha_is_opacity':False,'sampling':'raw UNORM8; no sRGB/ICC conversion, compositing or resampling','references':REFERENCES,'in_game_validated':False}


def edit(data, role, channel, operations):
    if data is None or role not in data['maps']:fail('先配置并导入要编辑的数据贴图')
    index=channel_index(role,channel)
    if not isinstance(operations,list) or not 1<=len(operations)<=4096:fail('每次提交 1..4096 个数据绘制操作')
    image=unpack(data['maps'][role]);plane=image.getchannel('RGBA'[index]);draw=ImageDraw.Draw(plane);budget=0
    for operation in operations:
        if not isinstance(operation,dict) or set(operation)!={'rect','value'}:fail('数据绘制操作使用 rect:[x,y,width,height] 和整数 value')
        rect,value=operation['rect'],operation['value']
        if not isinstance(rect,list) or len(rect)!=4 or any(type(n) is not int for n in rect) or type(value) is not int or not 0<=value<=255:fail('坐标为整数，通道值为 0..255')
        x,y,w,h=rect;budget+=w*h
        if min(x,y)<0 or min(w,h)<1 or x+w>image.width or y+h>image.height or budget>MAX_PIXELS*2:fail('数据绘制越出图集或超过本次像素预算')
        draw.rectangle((x,y,x+w-1,y+h-1),fill=value)
    channels=list(image.split());channels[index]=plane;image=Image.merge('RGBA',channels)
    candidate=deepcopy(data);candidate['maps'][role]=pack(image);return candidate


def remap(data, rectangles, order, new_rectangles, size):
    if data is None:return None
    candidate=deepcopy(data)
    for role,row in data['maps'].items():
        original=unpack(row);image=Image.new('RGBA',size,DEFAULTS[role])
        for i,old in enumerate(order):
            if old is not None:
                x,y,w,h=rectangles[old];image.paste(original.crop((x,y,x+w,y+h)),new_rectangles[i][:2])
        candidate['maps'][role]=pack(image)
    return candidate


def frames(document, time_ms=0, held_frame=None):
    if document.material_data is None:return {}
    from .minecraft_animation import sample, enabled
    return {role:sample(unpack(row),document.animation,time_ms,enabled(document),held_frame)[0] for role,row in document.material_data['maps'].items()}


def expanded_map(document, role, plan=None):
    from .minecraft_animation import expanded
    source=unpack(document.material_data['maps'][role])
    if plan is None:main,plan=expanded(document);count=len(main)
    else:count=max([len(document.animation['rectangles'])-1]+[s['frame'] for s in plan['steps']])+1
    images=[source.crop((x,y,x+w,y+h)) for x,y,w,h in document.animation['rectangles']]
    images += [None]*(count-len(images));at=0
    for step in plan['steps']:
        i=step['frame']
        if images[i] is None:images[i]=frames(document,at)[role]
        at+=step['duration_ms']
    if any(im is None for im in images):fail('展开数据帧与主材质索引不一致')
    return images,plan


class _Canvas:
    def __init__(self,image):self.image=image;self.w,self.h=image.size
    def composite(self):return self.image.copy()


class _Proxy:
    def __init__(self,document,role,plan=None):self._material_source=document;self._material_role=role;self._material_plan=plan;self._material_default=DEFAULTS[role];self.canvas=_Canvas(unpack(document.material_data['maps'][role]))
    def __getattr__(self,key):return getattr(self._material_source,key)


def resource_maps(config, identifier):
    from .minecraft_resources import Audit
    from .minecraft_target import resource_id,location
    identifier=resource_id(identifier);audit=Audit(config);audit._open();result={}
    try:
        for role,suffix in [('albedo',''),('normal','_n'),('specular','_s')]:
            path=location('texture',identifier+suffix);found=audit._read(path,required=role=='albedo')
            if found:result[role]={'image':read_png(found[0]),'source':found[1],'path':path,'raw':found[0]}
        if 'albedo' not in result:fail('找不到颜色贴图：'+identifier)
        for role in ROLES:
            if role in result and result[role]['image'].size!=result['albedo']['image'].size:fail('数据贴图与颜色贴图尺寸不一致：'+role)
        return result
    finally:
        for source in audit.sources:source.close()


def inspect(document, role='normal', channel='r', view='channel', pixel=None, resource=None, settings=None, time_ms=None, max_size=1024):
    if type(max_size) is not int or not 16<=max_size<=4096:fail('数据预览 max_size 使用 16..4096 的整数')
    data=document.material_data;provenance=None
    if resource is not None:
        from .minecraft_target import normalize as target_config
        config=target_config(settings if settings is not None else document.minecraft_project,document.workspace)
        if config is None:fail('读取资源需要明确的 Minecraft 来源配置')
        sources=resource_maps(config,resource);provenance={k:v['source'] for k,v in sources.items()};data={'schema':SCHEMA,'profile':PROFILE,'maps':{k:pack(v['image']) for k,v in sources.items() if k in ROLES},'target':(document.material_data or {}).get('target')}
        if not data['maps']:fail('该资源未提供 _n/_s 数据贴图')
    result=report(data);result.update(read_only=True,source_resources=provenance)
    if data is None:return {'report':result}
    if role not in data['maps']:role=next(iter(data['maps']))
    source=unpack(data['maps'][role]);index=channel_index(role,channel)
    if time_ms is not None and resource is None:
        source=frames(document,time_ms)[role]
    if view=='channel':plane=source.getchannel('RGBA'[index]);image=Image.merge('RGBA',(plane,plane,plane,Image.new('L',source.size,255)))
    elif view=='packed':image=source.copy();image.putalpha(255)
    elif view=='normal_vectors':
        if role!='normal':fail('normal_vectors 视图需要 normal 贴图')
        image=Image.new('RGBA',source.size);image.putdata([(r,g,round(math.sqrt(max(0,1-(r/127.5-1)**2-(g/127.5-1)**2))*255),255) for r,g,b,a in _pixels(source)])
    elif view=='decoded':
        image=Image.new('RGBA',source.size)
        if role=='normal':image.putdata([(b,b,b,255) for r,g,b,a in _pixels(source)])
        else:image.putdata([(round((a/254 if a<255 else 0)*255),round(b/64*255) if b<=64 else 0,round((b-65)/190*255) if b>=65 else 0,255) for r,g,b,a in _pixels(source)])
    else:fail('view 使用 channel/packed/normal_vectors/decoded')
    result['view']={'map':role,'channel':CHANNELS[role][index],'mode':view,'native_size':list(source.size),'alpha_rendered_as_data':True,'normal_reconstruction_clamps_for_diagnostic_only':view=='normal_vectors'}
    if pixel is not None:
        if not isinstance(pixel,list) or len(pixel)!=2 or any(type(n) is not int for n in pixel) or not 0<=pixel[0]<source.width or not 0<=pixel[1]<source.height:fail('pixel 使用图集内整数 [x,y]')
        all_images={r:unpack(row) for r,row in data['maps'].items()}
        if time_ms is not None and resource is None:all_images=frames(document,time_ms)
        values={r:im.getpixel(tuple(pixel)) for r,im in all_images.items()};result['pixel']={'position':pixel,'raw_rgba':values,'decoded':decode(values.get('normal',DEFAULTS['normal']),values.get('specular',DEFAULTS['specular']))}
    if image.width>max_size or image.height>max_size:
        image.thumbnail((max_size,max_size),Image.Resampling.NEAREST);result['view']['display_downsampled']=True
    return {'report':result,'image':base64.b64encode(png(image)).decode('ascii')}


def review_sheet(data):
    cell=196;rows=len(data['maps']);sheet=Image.new('RGBA',(4*cell,rows*(cell+64)),(25,29,39,255));draw=ImageDraw.Draw(sheet)
    for row,(role,value) in enumerate(data['maps'].items()):
        image=unpack(value)
        for i,meaning in enumerate(CHANNELS[role]):
            plane=image.getchannel('RGBA'[i]);view=Image.merge('RGB',(plane,plane,plane));view.thumbnail((cell-12,cell-12),Image.Resampling.NEAREST)
            if max(view.size)<cell-12:view=view.resize((max(1,round(view.width*(cell-12)/max(view.size))),max(1,round(view.height*(cell-12)/max(view.size)))),Image.Resampling.NEAREST)
            x,y=i*cell,row*(cell+64);draw.text((x+6,y+4),role+' / '+'RGBA'[i],fill='white');draw.text((x+6,y+22),meaning,fill='#bdb0ff');sheet.paste(view,(x+(cell-view.width)//2,y+48+(cell-view.height)//2))
    return sheet


def build(document, config, overlay):
    """Derive sidecars through the SAME layouts as albedo, using uncomposited bytes."""
    if document.material_data is None:return {},None
    result=report(document.material_data);files={};issues=result['issues']
    shader=document.material_data.get('target') or {}
    if shader.get('minecraft','1.20.1')!='1.20.1':issues.append({'severity':'error','code':'PBR_SHADER_MINECRAFT','message':'着色器目标 Minecraft 版本与 Forge 1.20.1 不一致'})
    if shader.get('forge') and config.get('runtime') and shader['forge']!=config['runtime']['forge_version']:issues.append({'severity':'error','code':'PBR_SHADER_FORGE','message':'着色器声明的 Forge 版本与当前运行时目标不同；请按消费项目绑定实际组合'})
    from .minecraft_resources import Source
    existing_format=None
    for setting in config['sources']:
        source=None
        try:
            source=Source(setting);name='assets/minecraft/optifine/texture.properties'
            if name in source.index:
                text=source.read(name).decode('utf-8-sig')
                match=re.search(r'^\s*format\s*=\s*([^\r\n#]+)',text,re.M)
                if match:existing_format=match.group(1).strip()
        except (OSError,ValueError,zipfile.BadZipFile) as error:issues.append({'severity':'error','code':'PBR_SOURCE_FORMAT','message':str(error)})
        finally:
            if source:source.close()
    if existing_format is not None and existing_format!='lab-pbr/1.3':issues.append({'severity':'error','code':'PBR_PACK_FORMAT_CONFLICT','message':'生效来源使用 '+existing_format+'，不能静默覆盖整个资源包的数据格式声明'})
    if not config.get('runtime') and config['binding'] is None:
        issues.append({'severity':'error','code':'PBR_EXPORT_BINDING','message':'数据贴图须绑定当前颜色纹理或 Forge 场景目标'})
    if config.get('texture_animation',{}).get('interpolate') and 'specular' in document.material_data['maps']:
        image=unpack(document.material_data['maps']['specular']);clips=[image.crop((x,y,x+w,y+h)) for x,y,w,h in document.animation['rectangles']]
        if len(clips)>1:
            for channel,name in [(1,'f0_or_metal'),(2,'porosity_or_sss')]:
                if any(a.getchannel('RGBA'[channel]).tobytes()!=clips[0].getchannel('RGBA'[channel]).tobytes() for a in clips[1:]):
                    issues.append({'severity':'error','code':'PBR_CATEGORICAL_INTERPOLATION','message':f'插值动画跨帧改变 {name}，会插入其他金属或语义区间；关闭插值或保持该数据通道一致'})
    if any(i['severity']=='error' for i in issues):result['passed']=False;return {},result
    for role,suffix in [('normal','_n'),('specular','_s')]:
        if role not in document.material_data['maps']:continue
        plan=next((json.loads(raw)['animation'] for name,raw in overlay.items() if name.endswith('/runtime.json')),None) if config.get('runtime') else None
        proxy=_Proxy(document,role,plan)
        if config.get('runtime'):
            from .forge_export import build as generate
            derived=generate(proxy,config)[0]
        else:
            from .minecraft_export import _binding
            derived=_binding(proxy,config)[0]
        for name,raw in derived.items():
            if name.endswith('.png') and name in overlay:
                path=name[:-4]+suffix+'.png';files[path]=raw
                if name+'.mcmeta' in derived:
                    meta=json.loads(derived[name+'.mcmeta']);animation=meta.get('animation')
                    if animation is not None:files[path+'.mcmeta']=(json.dumps({'animation':animation},sort_keys=True,indent=2)+'\n').encode()
    if not any(n.endswith('.png') for n in files):issues.append({'severity':'error','code':'PBR_NO_DERIVED_TEXTURES','message':'当前绑定没有生成可配对的数据贴图'})
    # OptiFine's public texture-format declaration also prevents a pack being
    # silently interpreted using an older specular format.
    files['assets/minecraft/optifine/texture.properties']=b'format=lab-pbr/1.3\n'
    result['generated_files']={n:sha(b) for n,b in sorted(files.items())};result['passed']=not any(i['severity']=='error' for i in issues)
    result['adapter_sha256']=sha(Path(__file__).read_bytes())
    return files,result
