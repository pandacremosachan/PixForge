"""Generate an owned Forge 1.20.1 LabPBR diagnostic project and optional shader pack."""
from pathlib import Path
import argparse,hashlib,json,math,shutil,zipfile
from PIL import Image
from pixelforge.document import Document
from pixelforge.material_data import PROFILE,review_sheet


def generate(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    shader=output/'shader-pack/shaders';shader.mkdir(parents=True,exist_ok=True)
    source=Path(__file__).with_name('material_probe_shaders')
    for f in source.rglob('*'):
        if f.is_file():p=shader/f.relative_to(source);p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,p)
    for alias in ('gbuffers_textured_lit','gbuffers_entities','gbuffers_block','gbuffers_hand'):
        for suffix in ('.vsh','.fsh'):shutil.copy2(shader/('gbuffers_terrain'+suffix),shader/(alias+suffix))
    (output/'shader-pack/README.txt').write_text('PixForge LabPBR Probe 1.0.0. Owned diagnostic source, not a production lighting pack. No POM/SSS/porosity/named-metals/SSR. No automatic installation or game acceptance.\n',encoding='utf-8',newline='\n')
    archive=output/'PixForge-LabPBR-Probe-1.0.0.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for f in sorted((output/'shader-pack').rglob('*')):
            if f.is_file():info=zipfile.ZipInfo(f.relative_to(output/'shader-pack').as_posix(),(2026,10,19,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,f.read_bytes())
    contract={'name':archive.name,'version':'1.0.0','loader':'optifine','loader_version':'1.20.1_HD_U_I6','minecraft':'1.20.1','forge':'47.2.18','sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'features':{'normals':True,'smoothness':True,'f0':True,'hardcoded_metals':False,'ao':True,'height':False,'porosity':False,'sss':False,'emission':True},'options':{}}
    size=64;albedo=Image.new('RGBA',(size,size));normal=Image.new('RGBA',(size,size));specular=Image.new('RGBA',(size,size))
    colors=[(49,116,127),(55,146,160),(219,136,68),(75,99,112),(235,114,45),(69,121,103),(108,80,135),(133,141,149)]
    for y in range(size):
        for x in range(size):
            tile=(x//16+(y//16)%2*4)%8;u,v=x%16,y%16;edge=min(u,v,15-u,15-v)<1;rgb=colors[tile];albedo.putpixel((x,y),tuple(round(c*(.55 if edge else 1)) for c in rgb)+(255,));nx=round(128+25*math.sin(u/15*2*math.pi)) if tile==5 else 128;ny=round(128+20*math.sin(v/15*2*math.pi)) if tile==5 else 128;ao=100 if tile==3 and (u in (4,5,10,11) or v in (4,5,10,11)) else 255;normal.putpixel((x,y),(nx,ny,ao,255));smooth=230 if tile in (1,2,6) else 35;metal=255 if tile==2 else 10;emission=140 if tile==4 and (u%5==0 or v%5==0) else 255;specular.putpixel((x,y),(smooth,metal,0,emission))
    for name,image in [('albedo',albedo),('normal',normal),('specular',specular)]:image.save(output/(name+'.png'))
    d=Document(output,output/'.runtime/generator',size,size);d.canvas.active.img=albedo
    faces={face:{'texture':'#all','uv':[0,0,16,16]} for face in ('north','south','east','west','up','down')}
    model={'textures':{'all':'pixforge_material_demo:block/pbr_panel'},'texture_size':[64,64],'elements':[{'from':[0,0,0],'to':[16,16,16],'faces':faces}]}
    d.configure_shapes({**d.shapes,'model':model});d.configure_scene({'schema':'pixelforge.scene-animation/v2','duration_ms':2000,'loop':True,'transforms':[],'emitters':[],'texture':{'mode':'hold','frame':0}})
    target={'namespace':'pixforge_material_demo','description':'PixForge owned LabPBR 1.3 diagnostic example','binding':None,'runtime':{'java_package':'dev.pixforge.materialdemo','forge_version':'47.2.18','scene':{'block':'pixforge_material_demo:pbr_panel','render_type':'solid'},'regression':True}}
    d.configure_minecraft(target);d.configure_material({'profile':PROFILE,'target':contract});d.import_material('normal',path=output/'normal.png');d.import_material('specular',path=output/'specular.png')
    d.save(output/'material-demo.pixforge');review_sheet(d.material_data).save(output/'channels.png')
    for name,value in [('shader-target.json',contract),('target.json',d.minecraft_project)]:
        (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    assert d.approval is None
    return {'project':str(output/'material-demo.pixforge'),'profile':PROFILE,'shader_zip':archive.name,'shader_sha256':contract['sha256'],'in_game_validated':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=Path(__file__).resolve().parent.parent/'examples/forge-labpbr-1.20.1');args=p.parse_args();print(json.dumps(generate(args.output)))
