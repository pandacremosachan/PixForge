"""Discussion-only single and paged batch previews; no artwork publication."""
import base64
from copy import deepcopy
import io

from .document import StudioError
from .minecraft_view import build_scene, finite
from .minecraft_sampling import ITEM_CONTEXTS
from .minecraft_raster import render_scene, comparison_sheet
from .minecraft_resources import digest


def preview(document, *, settings=None, view=None, batch=False, contexts=None, case_offset=0, case_limit=16):
    if type(batch) is not bool:
        raise StudioError('batch 须为布尔值')
    finite(case_offset,0,4096,'case_offset',True);finite(case_limit,1,16,'case_limit',True)
    initial=build_scene(document,settings=settings,view=view)
    if not initial['validation']['passed']:
        return {'validation':initial['validation'],'scene':{k:initial[k] for k in ('scene_digest','catalog','coverage')},'read_only':True}
    chosen_contexts=contexts if contexts is not None else [initial['options']['context']]
    if not isinstance(chosen_contexts,list) or not chosen_contexts or len(chosen_contexts)>9 or any(c not in ('block',*ITEM_CONTEXTS) for c in chosen_contexts):
        raise StudioError('contexts 使用 block 与目标物品显示场景的非空列表')
    cases=initial['catalog'].get('cases') or [{'state':initial['options']['state'],'weighted_choices':initial['options']['weighted_choices']}]
    if not batch:
        cases=[{'state':initial['options']['state'],'weighted_choices':initial['options']['weighted_choices']}]
        chosen_contexts=[initial['options']['context']]
    combinations=[(case,context) for case in cases for context in chosen_contexts]
    if case_offset>=len(combinations):
        raise StudioError('case_offset 超出状态/视图对照范围')
    selected=combinations[case_offset:case_offset+case_limit] if batch else combinations
    images,labels,rows=[],[],[]
    for case,context in selected:
        current=deepcopy(view or {});current.update(context=context,state=case['state'],weighted_choices=case['weighted_choices'])
        if context!=initial['options']['context']:
            current['camera']={**current.get('camera',{}),'yaw':30. if context=='block' else 0.,
                               'pitch':25. if context=='block' else 0.,'zoom':1.,
                               'projection':'perspective' if context=='block' else 'orthographic'}
        current['catalog_only']=False
        scene=build_scene(document,settings=settings,view=current)
        if not scene['validation']['passed']:
            raise StudioError('所选状态无法解析；未用占位图片代替素材','MINECRAFT_PREVIEW_INVALID',details=scene['validation'])
        tile_size=min(scene['options']['size'],256) if batch else scene['options']['size']
        image,metrics=render_scene(scene,tile_size)
        label=context+'\n'+','.join(k+'='+v for k,v in case['state'].items())
        if case['weighted_choices']:label+=' '+','.join(key+'#'+str(n) for key,n in case['weighted_choices'].items())
        images.append(image);labels.append(label)
        rows.append({'label':label,'context':context,'state':case['state'],'weighted_choices':case['weighted_choices'],
                     'scene_digest':scene['scene_digest'],'validation_digest':scene['validation']['validation_digest'],
                     'density':scene['density'],'density_summary':scene['density_summary'],'metrics':metrics,
                     'image_rgba_sha256':digest(image.tobytes()),'options':scene['options']})
    image=comparison_sheet(images,labels) if batch else images[0]
    stream=io.BytesIO();image.save(stream,format='PNG')
    return {'image':base64.b64encode(stream.getvalue()).decode('ascii'),
            'validation':initial['validation'],'report':{'schema':'pixforge.minecraft-preview/v1','passed':True,
                'batch':batch,'total_cases':len(combinations),'case_offset':case_offset,'case_count':len(rows),
                'next_case_offset':case_offset+len(rows) if batch and case_offset+len(rows)<len(combinations) else None,
                'cases':rows,'size':list(image.size),'png_sha256':digest(stream.getvalue()),
                'content_digest':document.art_digest(),'coverage':initial['coverage'],
                'catalog':initial['catalog'],'read_only':True,'in_game_validated':False,'approval_issued':False}}
