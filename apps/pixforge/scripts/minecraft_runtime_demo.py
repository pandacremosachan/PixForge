"""Create original, standalone 1.20.1 animation/regression authoring examples."""
from copy import deepcopy
import json
from pathlib import Path
from pixelforge.document import Document


def create(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    source=Path(__file__).resolve().parent.parent/'examples/forge-runtime-1.20.1/runtime-demo.pixforge'
    machine=Document(root,root/'.runtime/machine');machine.open(source)
    config=deepcopy(machine.minecraft_project);config['runtime']['regression']=True
    config['runtime']['scene']['lifecycle']={'unloaded':'pause','max_catch_up_ticks':2400,'sync_interval_ticks':20}
    config['texture_animation']={'interpolate':True};machine.configure_minecraft(config)
    machine.save(root/'machine-runtime.pixforge')
    (root/'machine-target.json').write_text(json.dumps(machine.minecraft_project,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    return {'machine':'machine-runtime.pixforge'}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);args=parser.parse_args();print(json.dumps(create(args.output)))
