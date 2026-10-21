"""Headless reference rasterizer for the application's Minecraft scene bundle.

Native desktop orbiting uses its persistent C++/OpenGL renderer. This independent
implementation produces discussion images and deterministic batch comparisons.
"""
import base64
from copy import deepcopy
import math

from PIL import Image, ImageDraw, ImageFont

from .minecraft_geometry import add, sub, mul, dot, cross, unit
from .minecraft_sampling import mipmaps, rgb


def camera_for(scene, size):
    view = scene['options'];camera = view['camera']
    yaw, pitch = math.radians(camera['yaw']), math.radians(camera['pitch'])
    right = (math.cos(yaw), 0., -math.sin(yaw))
    up = (-math.sin(pitch)*math.sin(yaw), math.cos(pitch), -math.sin(pitch)*math.cos(yaw))
    depth = (math.cos(pitch)*math.sin(yaw), math.sin(pitch), math.cos(pitch)*math.cos(yaw))
    center = tuple((a+b)/2 for a,b in zip(*scene['bounds'])) if view['context']=='block' else (0.,0.,0.)
    perspective = camera['projection']=='perspective'
    scale = size*.5 / math.tan(math.radians(camera['fov'])*.5) * camera['zoom']
    if not perspective:
        half_height = camera['distance']*math.tan(math.radians(camera['fov'])*.5) if view['context']=='block' else 8.
        scale = size*.5 / half_height * camera['zoom']
    eye = add(center, mul(depth,camera['distance']))
    return center,right,up,depth,scale,perspective,eye


def _clip(vertices, near=.1):
    result=[]
    for previous,current in zip(vertices[-1:]+vertices[:-1],vertices):
        a,b=previous['p'][2],current['p'][2]
        if (a>=near)!=(b>=near):
            factor=(near-a)/(b-a)
            result.append({key:tuple(x+(y-x)*factor for x,y in zip(previous[key],current[key])) for key in ('p','uv','c')})
        if b>=near:result.append(current)
    return result


def _edge(a,b,x,y):
    return (b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0])


def _top_left(a,b):
    dy,dx=b[1]-a[1],b[0]-a[0]
    return dy<0 or (abs(dy)<1e-10 and dx>0)


def _sample(levels,u,v,lod):
    lod=max(0.,min(len(levels)-1,lod));lo=int(lod);fraction=lod-lo
    colors=[]
    for level in (lo,min(lo+1,len(levels)-1)):
        image,pixels=levels[level]
        x=min(image.width-1,max(0,int(math.floor(u*image.width))))
        y=min(image.height-1,max(0,int(math.floor(v*image.height))))
        colors.append(pixels[x,y])
    return tuple(a+(b-a)*fraction for a,b in zip(*colors))


def render_scene(scene, size=None, measure_coverage=False):
    view=scene['options'];size=size or view['size']
    if not scene['validation']['passed']:
        raise ValueError('资源检查失败，不能用占位图代替当前素材')
    image=Image.new('RGBA',(size,size),tuple(rgb(view['background'])[:3])+ (255,))
    target=image.load();zbuffer=[float('inf')]*(size*size)
    center,right,up,depth,scale,perspective,eye=camera_for(scene,size)
    faces=list(scene['faces']);textures={row['id']:row for row in scene['textures']}
    if scene.get('particles'):
        textures['$particle']={'width':1,'height':1,'rgba':base64.b64encode(b'\xff'*4).decode()}
        for particle in scene['particles']:
            p=particle['position'];r=mul(right,particle['size']*.5);u=mul(up,particle['size']*.5)
            points=[add(sub(p,r),u),sub(sub(p,r),u),sub(add(p,r),u),add(add(p,r),u)]
            additive=particle['blend']=='additive'
            faces.append({'points':points,'uv':[(0,0),(0,1),(1,1),(1,0)],'colors':[particle['color']]*4,
                          'normal':depth,'double_sided':True,'texture':'$particle',
                          'layer':{'name':'particle','blend':True,'alpha_cutoff':.1,'mipmapped':False,
                                   'depth_write':not additive,'additive':additive}})
    def pass_index(face):
        name=face['layer']['name']
        return 3 if name=='particle' else 2 if name=='tripwire' and view['context']=='block' else 1 if face['layer']['blend'] else 0
    def sort_key(item):
        index,face=item;pass_id=pass_index(face)
        point=tuple(sum(p[i] for p in face['points'])/4 for i in range(3))
        distance=dot(sub(point,eye),sub(point,eye))
        return pass_id,(-distance if view['sort_translucent'] and pass_id in (1,2) else index)
    faces=[face for _,face in sorted(enumerate(faces),key=sort_key)]
    cache={};metrics={'faces':len(faces),'triangles':0,'fragments':0,'mipmap_levels_used':set()}
    blended_hits = {} if measure_coverage else None
    layer_fragments = {}
    for face in faces:
        points=face['points'];normal=unit(cross(sub(points[1],points[0]),sub(points[2],points[0])))
        if not face['double_sided'] and dot(normal,sub(eye,points[0]))<=1e-9:continue
        vertices=[]
        for p,uv,color in zip(points,face['uv'],face['colors']):
            rel=sub(p,center)
            vertices.append({'p':(dot(rel,right),dot(rel,up),view['camera']['distance']-dot(rel,depth)),
                             'uv':tuple(uv),'c':tuple(color)})
        vertices=_clip(vertices)
        if len(vertices)<3:continue
        projected=[]
        for vertex in vertices:
            x,y,z=vertex['p'];q=1/z if perspective else 1.
            projected.append((size/2+x*scale*q,size/2-y*scale*q,z,q,vertex['uv'],vertex['c']))
        rule=face['layer'];texture=textures[face['texture']]
        use_mips=rule['mipmapped'] and view['mipmap_levels']>0
        cache_key=(face['texture'],use_mips)
        if cache_key not in cache:
            base=Image.frombytes('RGBA',(texture['width'],texture['height']),base64.b64decode(texture['rgba']))
            chain=mipmaps(base,view['mipmap_levels']) if use_mips else [base]
            cache[cache_key]=[(level,level.load()) for level in chain]
        levels=cache[cache_key]
        for index in range(1,len(projected)-1):
            tri=[projected[0],projected[index],projected[index+1]]
            area=_edge(tri[0],tri[1],tri[2][0],tri[2][1])
            if abs(area)<1e-9:continue
            if area<0:tri[1],tri[2]=tri[2],tri[1];area=-area
            metrics['triangles']+=1
            lo_x=max(0,int(math.ceil(min(p[0] for p in tri)-.5)));hi_x=min(size-1,int(math.floor(max(p[0] for p in tri)-.5)))
            lo_y=max(0,int(math.ceil(min(p[1] for p in tri)-.5)));hi_y=min(size-1,int(math.floor(max(p[1] for p in tri)-.5)))
            if lo_x>hi_x or lo_y>hi_y:continue
            # Screen-space barycentric derivatives; quotient-rule UV derivatives
            # retain the perspective footprint used for automatic mip selection.
            dx=[(tri[1][1]-tri[2][1])/area,(tri[2][1]-tri[0][1])/area,(tri[0][1]-tri[1][1])/area]
            dy=[(tri[2][0]-tri[1][0])/area,(tri[0][0]-tri[2][0])/area,(tri[1][0]-tri[0][0])/area]
            qs=[p[3] for p in tri];us=[p[4][0]*p[3] for p in tri];vs=[p[4][1]*p[3] for p in tri]
            qdx=sum(a*b for a,b in zip(dx,qs));qdy=sum(a*b for a,b in zip(dy,qs))
            udx=sum(a*b for a,b in zip(dx,us));udy=sum(a*b for a,b in zip(dy,us))
            vdx=sum(a*b for a,b in zip(dx,vs));vdy=sum(a*b for a,b in zip(dy,vs))
            edges=[(tri[1],tri[2]),(tri[2],tri[0]),(tri[0],tri[1])]
            inclusive=[_top_left(a,b) for a,b in edges]
            for y in range(lo_y,hi_y+1):
                for x in range(lo_x,hi_x+1):
                    weights=[_edge(a,b,x+.5,y+.5) for a,b in edges]
                    if any(n< -1e-8 or (abs(n)<=1e-8 and not include) for n,include in zip(weights,inclusive)):continue
                    weights=[n/area for n in weights];q=sum(a*b for a,b in zip(weights,qs))
                    if q<=0:continue
                    z=1/q if perspective else sum(w*p[2] for w,p in zip(weights,tri))
                    offset=y*size+x
                    if z>zbuffer[offset]+1e-7:continue
                    u=sum(a*b for a,b in zip(weights,us));v=sum(a*b for a,b in zip(weights,vs))
                    lod=0.
                    if use_mips:
                        if view['mip_level']>=0:lod=view['mip_level']
                        else:
                            dux=(udx*q-u*qdx)/(q*q)*texture['width'];duy=(udy*q-u*qdy)/(q*q)*texture['width']
                            dvx=(vdx*q-v*qdx)/(q*q)*texture['height'];dvy=(vdy*q-v*qdy)/(q*q)*texture['height']
                            lod=math.log2(max(1.,math.hypot(dux,dvx),math.hypot(duy,dvy)))
                    texel=_sample(levels,u/q,v/q,lod)
                    color=[sum(weights[i]*tri[i][5][c]*qs[i] for i in range(3))/q for c in range(4)]
                    alpha=texel[3]/255*color[3]
                    if (texel[3]/255 if rule.get('alpha_test_texture_only',False) else alpha)+1e-10<rule['alpha_cutoff']:continue
                    source=[texel[i]*color[i] for i in range(3)];dest=target[x,y]
                    if rule['blend']:
                        old=1. if rule.get('additive',False) else 1-alpha
                        output=[min(255,max(0,int(source[i]*alpha+dest[i]*old+.5))) for i in range(3)]
                    else:output=[min(255,max(0,int(n+.5))) for n in source]
                    target[x,y]=tuple(output)+(255,)
                    if rule['depth_write']:zbuffer[offset]=z
                    metrics['fragments']+=1;metrics['mipmap_levels_used'].add(min(len(levels)-1,max(0,int(lod))))
                    if measure_coverage:
                        name=rule['name'];layer_fragments[name]=layer_fragments.get(name,0)+1
                        if rule['blend'] and alpha>0:blended_hits[offset]=blended_hits.get(offset,0)+1
    metrics['mipmap_levels_used']=sorted(metrics['mipmap_levels_used'])
    if measure_coverage:
        metrics['coverage']={'layer_fragments':layer_fragments,'blended_pixels':len(blended_hits),
            'blended_screen_fraction':len(blended_hits)/(size*size),
            'mean_blended_depth':sum(blended_hits.values())/max(1,len(blended_hits)),
            'max_blended_depth':max(blended_hits.values(),default=0),
            'scope':'depth-passing visible alpha fragments in this controlled viewport; no GPU timing'}
    return image,metrics


def comparison_sheet(images, labels, columns=4):
    if not images:raise ValueError('没有可预览的状态')
    width,height=images[0].size;columns=min(columns,len(images));rows=(len(images)+columns-1)//columns
    sheet=Image.new('RGBA',(columns*width,rows*(height+48)),(29,33,41,255));draw=ImageDraw.Draw(sheet)
    try:font=ImageFont.load_default(size=13)
    except TypeError:font=ImageFont.load_default()
    for index,(image,label) in enumerate(zip(images,labels)):
        x=index%columns*width;y=index//columns*(height+48)
        sheet.paste(image,(x,y))
        for line,text in enumerate(label.split('\n')[:2]):
            while draw.textlength(text,font=font)>width-16 and len(text)>1:text=text[:-2]+'…'
            draw.text((x+8,y+height+5+line*18),text,font=font,fill=(228,232,241,255))
    return sheet
