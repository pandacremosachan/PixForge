#pragma once
namespace pf {
inline constexpr std::array<const char*,6> sourceSides={"north","south","east","west","up","down"};
inline constexpr std::array<const wchar_t*,6> faceNames={L"北",L"南",L"东",L"西",L"上",L"下"};
inline constexpr COLORREF groupGold=RGB(248,193,110),groupMint=RGB(107,211,204);
inline const J& nullPart(){static const J empty;return empty;}
const J& App::partCube(const std::string& id)const{
    if(!id.empty())for(const auto& b:playerRig()["bones"].arr())for(const auto& c:b["cubes"].arr())if(c["uuid"].str()==id)return c;
    return nullPart();
}
void App::syncParts(){
    J kept=J::array();partIndices.clear();
    for(const auto& id:partSelection.arr()){
        const auto& cubes=studioMesh.cubes;auto it=std::find_if(cubes.begin(),cubes.end(),[&](const auto& c){return c.id==id.str();});
        if(it!=cubes.end()&&std::find(kept.arr().begin(),kept.arr().end(),id)==kept.arr().end()){partIndices.push_back(int(it-cubes.begin()));kept.arr().push_back(id);}
    }
    partSelection=std::move(kept);
    if(!partIndices.empty()){
        auto& c=studioMesh.cubes[partIndices.back()];rigBone=studioMesh.bones[c.bone].name;rigCubeId=c.id;rigCube=c.name.substr(c.name.find('/')+1);
        const auto& faces=partCube(c.id)["faces"];
        if(!faces.contains(activeFace)||faces[activeFace]["texture"].null()){
            for(auto f:sourceSides)if(faces.contains(f)&&!faces[f]["texture"].null()){activeFace=f;break;}}
    }
}
void App::chooseParts(const J& ids,bool centerUV){
    partSelection=ids;syncParts();playing=false;partDrag=0;partAmount=0;uvGrip=-1;rigPicked=!partIndices.empty();
    if(rigPicked)refreshRigTree();if(centerUV)uvFocus.clear();
    redrawRig();if(faceView)faceView->redraw();layout();
}
void App::pickPart(int hit,int side,bool toggle){
    if(hit<0){if(!toggle)chooseParts(J::array());return;}
    auto ids=toggle?partSelection:J::array();auto id=J(studioMesh.cubes[hit].id);
    auto it=std::find(ids.arr().begin(),ids.arr().end(),id);
    if(it!=ids.arr().end())ids.arr().erase(it);else{ids.arr().push_back(id);if(side>=0)activeFace=sourceSides[side];}
    chooseParts(ids);
}
void App::changePartMode(bool enabled){
    partMode=enabled;playing=false;partDrag=0;partAmount=0;
    if(enabled&&partSelection.empty()&&!rigCubeId.empty())chooseParts(J::array({rigCubeId}));
    if(!enabled){facePanel=false;uvGrip=-1;}layout();redrawRig();
}
void App::toggleFaces(bool enabled){
    if(enabled&&!partMode)changePartMode(true);
    facePanel=enabled;uvGrip=-1;playing=false;layout();redrawRig();if(faceView)faceView->redraw();
}
void App::setPartAxis(){
    if(partTool!=0&&partAxis==3)partAxis=0;comboSet(partAxisCombo,partAxis);comboSet(partToolCombo,partTool);if(loaded)redrawRig();
}
void App::resetPartView(){partMode=false;facePanel=false;partDrag=0;partAmount=0;partSelection=J::array();partIndices.clear();uvGrip=-1;uvFocus.clear();}
void App::createPartTools(){
    button(hwnd,"part_mode",L"部件建模",[this]{changePartMode(!partMode);},[this]{return partMode;});
    button(hwnd,"part_uv",L"逐面 UV",[this]{toggleFaces(!facePanel);},[this]{return facePanel;});
    partToolCombo=combo(hwnd,"part_transform",{L"缩放部件",L"旋转部件",L"移动支点"});partAxisCombo=combo(hwnd,"part_axis",{L"X 轴",L"Y 轴",L"Z 轴",L"等比"});setPartAxis();
    button(hwnd,"part_numbers",L"输入数值…",[this]{componentDialog();});
    button(hwnd,"part_anchor",L"各自支点",[this]{partAnchor=1-partAnchor;redrawRig();},[this]{return partAnchor==1;});
    faceView=surface(hwnd,51,[this](HDC dc,RECT r){facePaint(dc,r);});handles["rig_uv_editor"]=faceView->hwnd;
    faceView->event=[this](UINT m,WPARAM w,LPARAM l){return faceEvent(m,w,l);};SetWindowTextW(faceView->hwnd,L"逐面 UV 编辑器");
}
void App::componentDialog(){
    if(partIndices.empty())return;auto observed=tokens();auto ids=partSelection;
    auto r=inputDialog(hwnd,font,L"批量变换 · 静止模型",{{L"各轴缩放倍率 X Y Z",L"1 1 1"},{L"旋转增量 X Y Z（度）",L"0 0 0"},
        {L"支点偏移 X Y Z（模型单位）",L"0 0 0"},{L"变换中心：selection / individual / X Y Z",partAnchor?L"individual":L"selection"},
        {L"统一支点 X Y Z（留空使用偏移）",L""}});
    if(!r.accepted||observed!=tokens())return;J anchor=r.values[3]=="selection"||r.values[3]=="individual"?J(r.values[3]):rigNumbers(r.values[3],3);
    auto op=J::object({{"op","transform_cubes"},{"cube_ids",ids},{"scale",rigNumbers(r.values[0],3)},{"rotation",rigNumbers(r.values[1],3)},{"anchor",anchor}});
    if(r.values[4].empty())op["pivot_delta"]=rigNumbers(r.values[2],3);else op["pivot"]=rigNumbers(r.values[4],3);rigCommit(op);
}
static Vec componentProduct(Vec p,Vec q){return {p.x*q.x,p.y*q.y,p.z*q.z};}
static Vec partAxisVector(int axis,double value,double other=0){Vec out{other,other,other};if(axis==3)return {value,value,value};out.at(axis)=value;return out;}
void App::posePartsForView(){
    if(partIndices.empty())return;
    const auto& elems=static_cast<const J&>(state)["shapes"]["model"]["elements"];
    std::vector<Vec> centers(studioMesh.cubes.size()),pivots(centers.size());std::vector<bool> selected(centers.size(),false);
    modelHandle={};modelPivots.clear();
    for(auto i:partIndices){
        selected[i]=true;auto& c=studioMesh.cubes[i];auto& e=elems[i];auto cubeWorld=studioMesh.world[c.bone].after(c.bind);
        centers[i]=cubeWorld.point((vec(e["from"])+vec(e["to"]))*0.5);pivots[i]=studioMesh.world[c.bone].point(rigFlip(vec(e["pivot"])));
        modelHandle=modelHandle+(partTool==2||partAnchor?pivots[i]:centers[i]);modelPivots.push_back(pivots[i]);
    }
    modelHandle=modelHandle*(1./partIndices.size());if(partDrag!=1||partAmount==0)return;
    Vec scale=partTool==0?partAxisVector(partAxis,partAmount,1):Vec{1,1,1};
    Vec ang=partTool==1?rigFlip(partAxisVector(partAxis,partAmount)):Vec{};
    auto turn=RigMatrix::transform({},ang,{1,1,1});
    if(partTool==2){Vec diff=rigFlip(partAxisVector(partAxis,partAmount));modelHandle=modelHandle+diff;for(auto& p:modelPivots)p=p+diff;return;}
    for(auto& f:studioMesh.faces){
        int i=f.element;if(!selected[i])continue;auto& c=studioMesh.cubes[i];auto m=studioMesh.world[c.bone].after(c.bind);
        Vec anchor=partAnchor?pivots[i]:modelHandle,mid=centers[i];Vec newmid=anchor+turn.dir(componentProduct(mid-anchor,scale));
        for(auto& p:f.points){auto v=p-mid;Vec local{v.dot(m.col[0]),v.dot(m.col[1]),v.dot(m.col[2])};p=newmid+turn.dir(m.dir(componentProduct(local,scale)));}
        f.normal=turn.dir(f.normal);
    }
}
void App::highlightParts(){
    if(partIndices.empty())return;int w=rigSize;std::vector<bool> selected(studioMesh.cubes.size(),false);for(auto i:partIndices)selected[i]=true;
    auto& hits=studioMesh.hits;
    for(int y=1;y<w-1;++y)for(int x=1;x<w-1;++x){int p=y*w+x,i=pickedCube(hits[p]);if(i<0||!selected[i])continue;
        bool edge=i!=pickedCube(hits[p-1])||i!=pickedCube(hits[p+1])||i!=pickedCube(hits[p-w])||i!=pickedCube(hits[p+w]);
        if(edge){rigFrame.set(x,y,i==partIndices.back()?Pixel{255,202,115,255}:Pixel{92,224,215,255});}
    }
}
void App::partOverlay(HDC dc,RECT r){
    RECT q=rigSquare(r);double z=(q.right-q.left)/double(rigSize);Camera cam(studioMesh.center,studioMesh.radius,rigSize,yaw,pitch,pf::min(40,rigSize*.1),sceneZoom);
    auto screen=[&](Vec v){auto p=cam.project(v);return POINT{q.left+rounded(p.x*z),q.top+rounded(p.y*z)};};
    if(!partIndices.empty()){
        auto p=screen(modelHandle);int k=D(7);if(partTool==2){for(auto v:modelPivots){auto a=screen(v);line(dc,a.x-k,a.y,a.x+k,a.y,groupMint);line(dc,a.x,a.y-k,a.x,a.y+k,groupMint);}}
        line(dc,p.x-k,p.y,p.x+k,p.y,groupGold,D(2));line(dc,p.x,p.y-k,p.x,p.y+k,groupGold,D(2));
        if(partDrag==1){auto value=partTool==0?L"× "+rigNumber(partAmount):rigNumber(partAmount)+(partTool==1?L"°":L" px");
            text(dc,value,{p.x+D(10),p.y-D(17),r.right,p.y+D(10)},groupGold);}
    }
    int y=D(10);text(dc,L"静止模型    /    "+std::to_wstring(partIndices.size())+L" 个方块",{D(12),y,r.right,y+D(23)},partIndices.empty()?RGB(166,180,194):groupGold);
    text(dc,L"Shift / Ctrl 点选增减  ·  左拖变换  ·  右拖转视角",{D(12),r.bottom-D(25),r.right,r.bottom-D(3)},RGB(164,180,194));
}
LRESULT App::partEvent(UINT m,WPARAM w,LPARAM,int x,int y,RECT r){
    if(m==WM_LBUTTONDOWN){
        if(!canWrite())return 0;SetFocus(sceneView->hwnd);studioFrame(r);auto q=rigSquare(r);
        int xx=(x-q.left)*rigSize/(q.right-q.left),yy=(y-q.top)*rigSize/(q.bottom-q.top);int pos=(xx>=0&&yy>=0&&xx<rigSize&&yy<rigSize)?yy*rigSize+xx:-1;
        PickId pixel=pos<0?0:studioMesh.hits[pos];int hit=pickedCube(pixel),side=pixel?int(pixel&7):-1;bool toggle=(w&(MK_SHIFT|MK_CONTROL))!=0;
        if(toggle||hit<0||std::find(partIndices.begin(),partIndices.end(),hit)==partIndices.end()){pickPart(hit,side,toggle);if(toggle||hit<0)return 0;}
        else {auto ids=partSelection;auto id=J(studioMesh.cubes[hit].id);auto it=std::find(ids.arr().begin(),ids.arr().end(),id);ids.arr().erase(it);ids.arr().push_back(id);if(side>=0)activeFace=sourceSides[side];chooseParts(ids);}
        partObserved=tokens();partDrag=1;partAmount=partTool==0?1:0;rigDownX=x;rigDownY=y;SetCapture(sceneView->hwnd);return 0;
    }
    if(m==WM_MOUSEMOVE&&partDrag==1){double d=(x-rigDownX)-(y-rigDownY)*.35;
        partAmount=partTool==0?std::exp(d*.0065):partTool==1?d*.4:d*.035;redrawRig();return 0;}
    if(m==WM_LBUTTONUP&&partDrag==1){
        double v=partAmount;partDrag=0;partAmount=0;ReleaseCapture();if(partObserved==tokens()&&std::abs(v-(partTool==0?1:0))>1e-7){
            J op=J::object({{"op","transform_cubes"},{"cube_ids",partSelection},{"anchor",partAnchor?"individual":"selection"}});
            op[partTool==0?"scale":partTool==1?"rotation":"pivot_delta"]=sceneVector(partAxisVector(partAxis,v,partTool==0?1:0));rigCommit(op);
        }redrawRig();return 0;}
    if(m==WM_CAPTURECHANGED){partDrag=0;partAmount=0;panning=false;redrawRig();return 0;}return UNHANDLED;
}
J App::partStatus()const{
    J out=J::object({{"cube_ids",partSelection},{"active_cube",partIndices.empty()?J():partSelection[partSelection.size()-1]},
         {"mode",partMode?"model":"pose"},{"tool",std::array<const char*,3>{"scale","rotate","pivot"}[partTool]},
         {"axis",std::array<const char*,4>{"x","y","z","all"}[partAxis]},{"anchor",partAnchor?"individual":"selection"},
         {"uv_editor",facePanel},{"face",activeFace},{"linked_faces",linkFaces}});
    if(partMode&&!partIndices.empty()){const auto& f=partCube(partSelection[partSelection.size()-1].str())["faces"][activeFace];out["face_data"]=f;}
    return out;
}
}

