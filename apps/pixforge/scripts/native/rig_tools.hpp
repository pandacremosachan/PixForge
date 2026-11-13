#pragma once
#include <sstream>
namespace pf {
inline J rigNumbers(const std::string& s,size_t expected){
    std::string t=s;for(char& c:t)if(c==','||c=='['||c==']')c=' ';
    std::istringstream stream(t);J out=J::array();double v;
    while(stream>>v)out.arr().push_back(v);
    if(!stream.eof()||out.size()!=expected)throw std::runtime_error("坐标数量不对，请以空格或逗号分隔数字");
    return out;
}
inline std::wstring rigText(const J& obj,const char* key,const wchar_t* fallback){
    return obj.contains(key)?wide(obj[key].dump()):fallback;
}
void App::newRig(){
    auto r=inputDialog(hwnd,font,L"新建骨骼玩家模型",{{L"角色名称",L"player"},{L"图集宽、高（像素）",L"128 128"}});
    if(!r.accepted)return;
    auto size=rigNumbers(r.values[1],2);
    saveBefore([this,name=r.values[0],size]{mutate("create_project",J::object({{"settings",J::object({{"preset","player_rig"},{"name",name},{"texture_size",size}})}}));});
}
void App::createRigTools(){
    createPartTools();
    rigTextureCombo=combo(hwnd,"rig_texture",{});rigChannelCombo=combo(hwnd,"rig_channel",{L"旋转  °",L"位移  px",L"缩放  ×"});
    rigAxisCombo=combo(hwnd,"rig_axis",{L"X 轴",L"Y 轴",L"Z 轴"});rigStyleCombo=combo(hwnd,"rig_interpolation",{L"线性",L"阶跃",L"平滑 · Catmull–Rom",L"贝塞尔"});
    comboSet(rigChannelCombo,0);comboSet(rigAxisCombo,0);comboSet(rigStyleCombo,0);
    rigGraph=surface(hwnd,49,[this](HDC dc,RECT r){graphPaint(dc,r);});handles["rig_graph"]=rigGraph->hwnd;
    rigGraph->event=[this](UINT m,WPARAM w,LPARAM l){return graphEvent(m,w,l);};
    button(hwnd,"rig_graph_toggle",L"动画曲线",[this]{rigCurve=!rigCurve;layout();},[this]{return rigCurve;});
    button(hwnd,"rig_insert",L"插入关键帧",[this]{insertRigKey();});
    rigBoneCombo=combo(hwnd,"rig_bone",{});rigCubeCombo=combo(hwnd,"rig_cube",{});
    for(auto [id,title]:{std::pair<const char*,const wchar_t*>{"add_bone",L"添加骨骼"},{"edit_bone",L"编辑骨骼"},
        {"add_cube",L"添加方块"},{"edit_cube",L"编辑方块"},{"key",L"关键帧"},{"more",L"更多…"}}){
        button(hwnd,"rig_"+std::string(id),title,[this,id]{editRig(id);});
    }
}
void App::refreshRigTree(){
    const auto& rig=playerRig();if(rig.null())return;
    std::map<std::string,std::vector<const J*>> children;
    for(auto& b:rig["bones"].arr())children[b["parent"].str()].push_back(&b);
    std::vector<std::wstring> labels;rigBoneNames.clear();
    std::function<void(std::string,int)> append=[&](std::string root,int depth){
        for(auto b:children[root]){std::string name=(*b)["name"].str();rigBoneNames.push_back(name);
            labels.push_back(std::wstring(depth*2,L' ')+wide(name));append(name,depth+1);}
    };append("",0);
    auto bit=std::find(rigBoneNames.begin(),rigBoneNames.end(),rigBone);
    if(bit==rigBoneNames.end()){
        auto first=std::find_if(rig["bones"].arr().begin(),rig["bones"].arr().end(),[](const J& b){return !b["cubes"].empty();});
        if(first!=rig["bones"].arr().end())bit=std::find(rigBoneNames.begin(),rigBoneNames.end(),(*first)["name"].str());
    }
    int bi=bit==rigBoneNames.end()?0:int(bit-rigBoneNames.begin());
    rigBone=rigBoneNames.at(bi);rigBoneChoices.set(rigBoneCombo,std::move(labels),bi);
    labels.clear();rigCubeNames.clear();rigCubeIds.clear();
    for(const auto& b:rig["bones"].arr())if(b["name"].str()==rigBone)
        for(auto& c:b["cubes"].arr()){rigCubeIds.push_back(c["uuid"].str());rigCubeNames.push_back(c["name"].str());labels.push_back(wide(c["name"].str()));}
    auto cit=std::find(rigCubeNames.begin(),rigCubeNames.end(),rigCube);
    int ci=cit==rigCubeNames.end()?(rigCubeNames.empty()?-1:0):int(cit-rigCubeNames.begin());
    if(studio()){auto it=std::find(rigCubeIds.begin(),rigCubeIds.end(),rigCubeId);if(it!=rigCubeIds.end())ci=int(it-rigCubeIds.begin());rigCubeId=ci<0?"":rigCubeIds[ci];}
    rigCube=ci<0?"":rigCubeNames[ci];rigCubeChoices.set(rigCubeCombo,std::move(labels),ci);EnableWindow(handles.at("rig_edit_cube"),ci>=0);
}
void App::editRig(const std::string& mode){
    if(!canWrite())return;
    auto observed=tokens();const auto source=playerRig();J b,c;
    for(const auto& v:source["bones"].arr())if(v["name"].str()==rigBone)b=v;
    if(!b.isObject())return;
    for(const auto& v:b["cubes"].arr())if(studio()?v["uuid"].str()==rigCubeId:v["name"].str()==rigCube)c=v;
    auto pick=[&](const wchar_t* title,std::vector<std::pair<std::wstring,std::wstring>> fields){
        auto result=inputDialog(hwnd,font,title,std::move(fields));if(result.accepted&&observed!=tokens())throw std::runtime_error("工程已变化，请重新选择部件");
        return result;
    };
    J op=J::object({{"bone",rigBone}});
    if(studio()&&(mode=="edit_cube"||mode=="delete_cube"))op["cube_id"]=rigCubeId;
    if(mode=="add_bone"||mode=="edit_bone"){
        bool add=mode=="add_bone";std::string suggested="Bone"+std::to_string(source["bones"].size()+1);
        auto r=pick(add?L"添加子骨骼":L"编辑骨骼",{{L"名称",wide(add?suggested:rigBone)},
             {L"父骨骼（空白为根）",wide(add?rigBone:b["parent"].str())},{L"支点 X Y Z",rigText(b,"pivot",L"0 0 0")},
             {L"静止旋转 X Y Z（度）",add?L"0 0 0":rigText(b,"rotation",L"0 0 0")}});
        if(!r.accepted)return;op["op"]="bone";op["bone"]=add?r.values[0]:rigBone;
        if(!add&&r.values[0]!=rigBone)op["rename"]=r.values[0];
        op["parent"]=r.values[1].empty()?J():J(r.values[1]);op["pivot"]=rigNumbers(r.values[2],3);op["rotation"]=rigNumbers(r.values[3],3);
        rigBone=r.values[0];rigCube.clear();
    }else if(mode=="add_cube"||mode=="edit_cube"){
        bool add=mode=="add_cube";if(add)c=J::object();
        auto r=pick(add?L"添加方块":L"编辑方块",{{L"方块名称",add?L"Cube"+std::to_wstring(b["cubes"].size()+1):wide(rigCube)},
            {L"起点 X Y Z",rigText(c,"from",L"-1 12 -1")},{L"终点 X Y Z",rigText(c,"to",L"1 14 1")},
            {L"旋转支点 X Y Z",rigText(c,"pivot",wide(b["pivot"].dump()).c_str())},{L"旋转 X Y Z（度）",rigText(c,"rotation",L"0 0 0")},
            {L"盒式 UV 左上角（留空保留逐面 UV）",(studio()?!c["box_uv"].boolean(true):c.contains("faces"))?L"":rigText(c,"uv",L"0 0")}});
        if(!r.accepted)return;op["op"]="cube";op["name"]=add?r.values[0]:rigCube;
        if(!add&&r.values[0]!=rigCube)op["rename"]=r.values[0];
        op["from"]=rigNumbers(r.values[1],3);op["to"]=rigNumbers(r.values[2],3);op["pivot"]=rigNumbers(r.values[3],3);
        op["rotation"]=rigNumbers(r.values[4],3);if(!r.values[5].empty())op["uv"]=rigNumbers(r.values[5],2);rigCube=r.values[0];
    }else if(mode=="add_texture"){
        auto path=chooseFile(hwnd,workspace,false,L"PNG 图集\0*.png\0",nullptr);if(path.empty())return;auto s=readFile(path);
        op=J::object({{"op","add_texture"},{"name",pathText(path.filename())},{"source","data:image/png;base64,"+base64(std::vector<uint8_t>(s.begin(),s.end()))}});
    }else if(mode=="face_texture"){
        if(rigTexture<0||rigCubeId.empty())return;const auto& material=source["textures"][rigTexture];
        auto r=pick(L"绑定所选贴图",{{L"应用于面（以空格分隔）",L"north east south west up down"}});if(!r.accepted)return;
        op["op"]="face_texture";op["cube_id"]=rigCubeId;op["texture"]=material["uuid"];J faces=J::array();std::istringstream stream(r.values[0]);std::string face;while(stream>>face)faces.arr().push_back(face);op["faces"]=faces;
    }else if(mode=="handles"){
        if(rigKeyId.empty())return;const J* key=nullptr;for(const auto& k:rigKeys().arr())if(k["uuid"].str()==rigKeyId)key=&k;
        if(!key)return;auto r=pick(L"贝塞尔手柄",{{L"左侧时间偏移（秒）X Y Z",rigText(*key,"bezier_left_time",L"-0.1 -0.1 -0.1")},
            {L"左侧数值偏移 X Y Z",rigText(*key,"bezier_left_value",L"0 0 0")},{L"右侧时间偏移（秒）X Y Z",rigText(*key,"bezier_right_time",L"0.1 0.1 0.1")},
            {L"右侧数值偏移 X Y Z",rigText(*key,"bezier_right_value",L"0 0 0")}});
        if(!r.accepted)return;op["op"]="key";op["clip"]=rigClip;op["channel"]=rigChannel;op["uuid"]=rigKeyId;op["time_ms"]=rigTime;op["interpolation"]="bezier";
        int i=0;for(auto field:{"bezier_left_time","bezier_left_value","bezier_right_time","bezier_right_value"})op[field]=rigNumbers(r.values[i++],3);
    }else if(mode=="key"||mode=="delete_key"){
        std::string clip=studio()?rigClip:scenePlayer?scenePlayer->state:source["clips"].size()?source["clips"][0]["name"].str():"idle";
        J v=J::array();for(int j=0;j<3;++j)v.arr().push_back(studio()?rigValue(rigKeys(),j,rigTime/1000,rigLoop,rigChannel=="scale"?1:0):0);
        auto r=pick(mode=="key"?L"设置骨骼关键帧":L"移除骨骼关键帧",{{L"动作名称",wide(clip)},{L"通道：rotation / position / scale",studio()?wide(rigChannel):L"rotation"},
            {L"时间（毫秒）",wide(J(sceneClock()).dump())},{L"数值 X Y Z",wide(v.dump())}});
        if(!r.accepted)return;op["op"]=mode;op["clip"]=r.values[0];op["channel"]=r.values[1];op["time_ms"]=rigNumbers(r.values[2],1)[0];op["value"]=rigNumbers(r.values[3],3);
    }else if(mode=="clip"){
        auto r=pick(L"添加或调整动作",{{L"动作名称",L"walk"},{L"时长（毫秒）",L"1000"},{L"循环：1 是，0 否",L"1"}});
        if(!r.accepted)return;op["op"]="clip";op["name"]=r.values[0];op["duration_ms"]=rigNumbers(r.values[1],1)[0];op["loop"]=r.values[2]=="1";
    }else if(mode=="delete_cube"){if(rigCube.empty())return;op["op"]=mode;op["name"]=rigCube;
    }else if(mode=="delete_bone"){op["op"]=mode;
    }else{
        choice::Menu menu;menu.item(1,L"动作名称与时长…");menu.item(2,L"删除关键帧…");
        menu.item(3,L"删除所选方块");menu.item(4,L"删除骨骼及其子级");
        if(studio()){menu.separator();menu.item(5,L"添加 PNG 贴图…");menu.item(6,L"将预览贴图绑定到所选面…",false,rigTexture>=0&&!rigCubeId.empty());menu.item(7,L"编辑选中帧的贝塞尔手柄…",false,!rigKeyId.empty());}
        int n=menu.open(handles.at("rig_more"));
        if(n)editRig(std::array<const char*,7>{"clip","delete_key","delete_cube","delete_bone","add_texture","face_texture","handles"}[n-1]);return;
    }
    mutate("rig_edit",J::object({{"operations",J::array({op})}}));
}
void App::saveRig(bool ysm){
    if(!canWrite())return;auto observed=tokens();
    auto path=chooseFile(hwnd,workspace/(ysm?L"player.zip":L"player.bbmodel"),true,
                         ysm?L"YSM 模型包\0*.zip\0":L"Blockbench 工程\0*.bbmodel\0",ysm?L"zip":L"bbmodel");
    if(path.empty())return;if(observed!=tokens())throw std::runtime_error("工程已变化，请重新选择导出文件");
    auto options=J::object({{"path",pathText(path)},{"format",ysm?"ysm":"bbmodel"},{"overwrite",true}});
    if(!ysm||state["approved_for_export"].boolean()){mutate("rig_export",options);return;}
    mutate("approve",J::object({{"user_request","用户选择导出当前 YSM 玩家模型包"},{"source","desktop_user"}}),[this,options](const J& result){
        auto p=options;p["expected_document_id"]=result["state"]["document_id"];p["expected_revision"]=result["state"]["revision"];
        rpc->call(payload("rig_export",p),[this](const J&){fetch();});
    });
}
}
