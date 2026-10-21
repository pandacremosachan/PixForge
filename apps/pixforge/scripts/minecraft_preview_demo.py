"""Create original synthetic Forge preview resources in a new/empty directory.

No Mojang assets, game installation, live user project or export approval is used.
The same small resource set supports the application example and regression tests.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from PIL import Image, ImageDraw

DOMAIN = 'pixforge_preview_demo'
FACES = ('north','south','east','west','up','down')


def build_assets(root):
    root=Path(root)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError('Choose a new or empty example directory')
    root.mkdir(parents=True,exist_ok=True)
    assets=root/'assets'/DOMAIN
    for folder in ('models/block','models/item','blockstates','textures/block','textures/item','textures/colormap'):
        (assets/folder).mkdir(parents=True,exist_ok=True)
    def save(name,value):
        path=assets/name;path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    def element(start,end,texture,**extras):
        face_options=extras.pop('face_options',{})
        return {'from':start,'to':end,'faces':{face:{'texture':texture,**face_options} for face in FACES},**extras}
    frame=Image.new('RGBA',(32,32));p=frame.load()
    for y in range(32):
        for x in range(32):
            band=((x//4+y//4)%2);p[x,y]=(122+band*18,99+band*15,67+band*10,255)
    ImageDraw.Draw(frame).rectangle((1,1,30,30),outline=(222,191,119,255),width=1)
    frame.save(assets/'textures/block/frame.png')
    glass=Image.new('RGBA',(32,32),(66,169,213,56));draw=ImageDraw.Draw(glass)
    draw.rectangle((0,0,31,31),outline=(103,219,235,210),width=2);draw.line((5,25,25,5),fill=(176,241,247,106),width=2)
    glass.save(assets/'textures/block/glass.png')
    leaves=Image.new('RGBA',(16,16));p=leaves.load()
    for y in range(16):
        for x in range(16):
            value=170+((x*7+y*11)%6)*12;p[x,y]=(value,value,value,255 if (x+2*y)%5 not in (0,1) else 0)
    leaves.save(assets/'textures/block/leaves.png')
    glow=Image.new('RGBA',(16,16),(82,223,248,255));glow.save(assets/'textures/block/glow.png')
    icon=Image.new('RGBA',(16,16));d=ImageDraw.Draw(icon);d.polygon([(8,1),(13,7),(10,14),(5,14),(2,7)],fill=(204,211,219,255));d.line((8,3,8,12),fill=(255,255,255,255),width=1);icon.save(assets/'textures/item/diagnostic.png')
    colormap=Image.new('RGBA',(256,256));p=colormap.load()
    for y in range(256):
        for x in range(256):p[x,y]=(int(55+x*.55),int(220-y*.45),int(65+(255-x)*.2),255)
    colormap.save(assets/'textures/colormap/grass.png')
    display={'gui':{'rotation':[30,225,0],'scale':[.625]*3},'ground':{'translation':[0,3,0],'scale':[.25]*3},
             'thirdperson_righthand':{'rotation':[75,45,0],'translation':[0,2.5,0],'scale':[.375]*3},
             'firstperson_righthand':{'rotation':[0,45,0],'scale':[.4]*3},
             'fixed':{'rotation':[0,180,0],'scale':[.5]*3}}
    save('models/block/display_base.json',{'display':display,'ambientocclusion':True,'gui_light':'side'})
    frame_model={'parent':DOMAIN+':block/display_base','render_type':'minecraft:solid','textures':{'frame':DOMAIN+':block/frame'},
        'elements':[element([0,0,0],[16,2,16],'#frame'),element([0,14,0],[16,16,16],'#frame'),
                    *[element([x,2,z],[x+2,14,z+2],'#frame') for x in (0,14) for z in (0,14)]]}
    glass_model={'parent':DOMAIN+':block/display_base','render_type':'minecraft:translucent','textures':{'glass':DOMAIN+':block/glass'},
                 'elements':[element([2,2,2],[14,14,14],'#glass')]}
    leaves_model={'parent':DOMAIN+':block/display_base','render_type':'minecraft:cutout_mipped','textures':{'leaves':DOMAIN+':block/leaves'},
                  'elements':[element([3,7,3],[13,7,13],'#leaves',face_options={'tintindex':0})]}
    glow_model={'parent':DOMAIN+':block/display_base','render_type':'minecraft:cutout','textures':{'glow':DOMAIN+':block/glow'},
                'elements':[element([4,3,3],[12,4,4],'#glow',shade=False,forge_data={'block_light':15,'ambient_occlusion':False})]}
    for name,value in [('frame',frame_model),('glass',glass_model),('leaves',leaves_model),('glow',glow_model)]:save('models/block/'+name+'.json',value)
    multipart=[]
    for direction,y in [('north',0),('east',90),('south',180),('west',270)]:
        for part in ('frame','glass','leaves'):
            multipart.append({'when':{'facing':direction},'apply':{'model':DOMAIN+':block/'+part,'y':y,'uvlock':True}})
        multipart.append({'when':{'AND':[{'facing':direction},{'active':'true'}]},'apply':{'model':DOMAIN+':block/glow','y':y,'uvlock':True}})
    save('blockstates/machine.json',{'multipart':multipart})
    combined=deepcopy(frame_model);combined['render_type']='minecraft:translucent'
    combined['textures']={**frame_model['textures'],**glass_model['textures'],**leaves_model['textures'],**glow_model['textures']}
    combined['elements']=[*frame_model['elements'],*glass_model['elements'],*leaves_model['elements'],*glow_model['elements']]
    save('models/item/machine.json',combined)
    asymmetric={'parent':DOMAIN+':block/display_base','render_type':'minecraft:cutout_mipped',
        'textures':{'frame':DOMAIN+':block/frame','leaves':DOMAIN+':block/leaves'},
        'elements':[element([0,0,0],[16,2,16],'#frame'),element([0,2,0],[3,16,3],'#frame',face_options={'uv':[0,0,16,16]}),
                    element([4,4,4],[15,12,15],'#leaves',face_options={'tintindex':0})]}
    save('models/block/asymmetric.json',asymmetric)
    save('models/block/asymmetric_alt.json',{**deepcopy(asymmetric),'display':{'gui':{'rotation':[0,0,0],'scale':[.5]*3}}})
    save('models/item/asymmetric.json',{'parent':DOMAIN+':block/asymmetric'})
    save('blockstates/asymmetric.json',{'variants':{
        'facing='+f:([{'model':DOMAIN+':block/asymmetric','y':y,'uvlock':True,'weight':3},{'model':DOMAIN+':block/asymmetric_alt','y':y,'uvlock':False,'weight':1}]
                    if f=='north' else {'model':DOMAIN+':block/asymmetric','y':y,'uvlock':True})
        for f,y in [('north',0),('east',90),('south',180),('west',270)]}})
    generated={'parent':'minecraft:builtin/generated','textures':{'layer0':DOMAIN+':item/diagnostic'},
               'display':{'gui':{'rotation':[0,0,0]},'ground':{'rotation':[0,0,0],'translation':[0,2,0],'scale':[.5]*3}},
               'overrides':[{'predicate':{'custom_model_data':1},'model':DOMAIN+':item/diagnostic_lit'}]}
    save('models/item/diagnostic.json',generated)
    save('models/item/diagnostic_lit.json',{'parent':'minecraft:builtin/generated','textures':{'layer0':DOMAIN+':block/glow'}})
    config={'schema':'pixforge.minecraft-project/v1','profile':'forge-1.20.1','namespace':DOMAIN,
            'sources':[{'name':'original-preview-example','path':'.','role':'project'}],
            'entries':[{'kind':'blockstate','id':DOMAIN+':machine'},{'kind':'blockstate','id':DOMAIN+':asymmetric'},
                       {'kind':'model','id':DOMAIN+':item/diagnostic'}],'binding':None,
            'description':'Original controlled Forge 1.20.1 preview example; no Mojang assets'}
    (root/'target.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8',newline='\n')
    view={'subject':{'kind':'blockstate','id':DOMAIN+':machine'},'state':{'facing':'east','active':'true'},
          'block_tints':{'0':'#70b94b'},'item_tints':{'0':'#d6ad66'},'camera':{'yaw':35,'pitch':22,'distance':56},'size':512}
    (root/'preview.json').write_text(json.dumps(view,indent=2)+'\n',encoding='utf-8',newline='\n')
    return config,view


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);args=parser.parse_args()
    build_assets(args.output);print(args.output.resolve())
