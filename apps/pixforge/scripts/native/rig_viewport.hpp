#pragma once
namespace pf {
constexpr COLORREF rigAxisColors[]={RGB(244,141,135),RGB(131,215,164),RGB(132,176,255)};
const char* const rigChannels[]={"rotation","position","scale"};
const char* const rigStyles[]={"linear","step","catmullrom","bezier"};
int App::selectedBone()const{
    for(int i=0;i<int(studioMesh.bones.size());++i)if(studioMesh.bones[i].name==rigBone)return i;return -1;
}
const J& App::rigKeys()const{
    int i=selectedBone();static const J none;if(i<0)return none;return rigTracks[studioMesh.bones[i].id][rigChannel];
}
void App::setRigCube(std::string id){if(partMode){chooseParts(J::array({id}));return;}rigCubeId=std::move(id);rigPicked=true;refreshRigTree();rigFocusedKey();redrawRig();}
void App::rigFocusedKey(){
    rigKeyId.clear();if(!studio())return;
    const auto& keys=rigKeys();if(keys.isArray())for(const auto& k:keys.arr())if(std::abs(k["time"].number()*1000-rigTime)<.1){rigKeyId=k["uuid"].str();
        int i=0;while(i<3&&k["interpolation"].str()!=rigStyles[i])++i;comboSet(rigStyleCombo,i);break;}
}
void App::rigCommit(J op){
    if(!canWrite()||(!partMode&&rigWanted!=rigLoaded))return;
    mutate("rig_edit",J::object({{"operations",J::array({std::move(op)})}}));
}
void App::insertRigKey(){
    if(rigClip.empty()||selectedBone()<0)return;J v=J::array();for(int i=0;i<3;++i)v.arr().push_back(rigValue(rigKeys(),i,rigTime/1000,rigLoop,rigChannel=="scale"?1:0));
    rigCommit(J::object({{"op","key"},{"bone",rigBone},{"clip",rigClip},{"channel",rigChannel},{"time_ms",rigTime},{"value",v},{"interpolation",rigStyles[pf::max(0,comboIndex(rigStyleCombo))]}}));
}
void App::loadStudio(bool reset){
    if(reset){resetPartView();partMode=studio()&&playerRig()["clips"].empty();}
    if(!studio()){rigLoaded.clear();rigWanted.clear();return;}
    studioMesh.load(state["shapes"]["model"]);rigFrameKey.clear();if(partMode){partDrag=0;uvGrip=-1;syncParts();}
    auto& clips=playerRig()["clips"];bool has=false;
    for(const auto& a:clips.arr())if(a["name"].str()==rigClip)has=true;
    if(reset||!has){rigClip=clips.empty()?"":clips[0]["name"].str();for(const auto& a:clips.arr())if(a["name"].str()=="idle")rigClip="idle";
        rigTime=0;rigTexture=-1;rigGrab=0;rigPicked=false;rigCubeId.clear();}
    std::vector<std::wstring> names;int selected=0;
    for(const auto& a:clips.arr()){if(a["name"].str()==rigClip)selected=int(names.size());names.push_back(wide(a["name"].str()));}
    rigClipsList.set(sceneStateCombo,std::move(names),selected);names={L"按模型面绑定"};
    for(const auto& t:playerRig()["textures"].arr())names.push_back(wide(t["name"].str()));
    rigTexturesList.set(rigTextureCombo,std::move(names),rigTexture+1);
    comboSet(rigChannelCombo,rigChannel=="rotation"?0:rigChannel=="position"?1:2);comboSet(rigAxisCombo,rigAxis);
    loadRigClip();
}
void App::changeRigClip(const std::string& name){
    rigClip=name;rigTime=0;playing=false;rigKeyId.clear();loadRigClip();syncStateControls();redrawRig();
}
void App::loadRigClip(bool force){
    std::string key=state["content_digest"].str()+":"+rigClip;if(!force&&rigWanted==key)return;rigWanted=key;
    if(rigClip.empty()){rigLoaded=key;rigTracks=J::object();rigEnd=1;return;}
    for(const auto& c:playerRig()["clips"].arr())if(c["name"].str()==rigClip){rigEnd=pf::max(1.,c["duration_ms"].number());rigLoop=c["loop"].str()=="loop";break;}
    rigTime=pf::clamp(rigTime,0.,rigEnd);
    rpc->call(payload("rig_inspect",J::object({{"clip",rigClip},{"native",true}})),[this,key](const J& result){if(rigWanted!=key)return;
        rigTracks=result["tracks"];rigLoaded=key;rigFocusedKey();redrawRig();});
}
void App::redrawRig(){rigFrameKey.clear();if(faceView&&facePanel)faceView->redraw();sceneView->redraw();if(rigGraph)rigGraph->redraw();if(timeline)timeline->redraw();}
static RECT rigSquare(RECT r){int side=pf::max(1,pf::min(r.right-12,r.bottom-12));int x=(r.right-side)/2,y=(r.bottom-side)/2;return {x,y,x+side,y+side};}
void App::studioFrame(RECT r){
    RECT q=rigSquare(r);rigSize=pf::clamp(q.right-q.left,96,1000);
    auto key=state["content_digest"].str()+":"+rigLoaded+":"+std::to_string(rigSize)+":"+std::to_string(yaw)+":"+std::to_string(pitch)+":"+std::to_string(sceneZoom)+":"+std::to_string(rigTime)+":"+std::to_string(rigTexture)+":"+std::to_string(rigDelta)+":"+std::to_string(rigGrab)+":"+std::to_string(showModel);
    key+=":"+std::to_string(frame)+(partMode?":model":":pose");for(bool active:overlays)key+=active?'1':'0';if(key==rigFrameKey)return;rigFrameKey=key;
    if(partMode){studioMesh.pose(J(),0,false,rigTexture);posePartsForView();previewUV();}
    else studioMesh.pose(rigTracks,rigTime/1000,rigLoop,rigTexture,rigGrab==1?selectedBone():-1,rigAxis,rigDelta,rigChannel);
    auto rect=currentRect();Image tile;
    const Image* atlas=&canvas.composed;
    if(rect.x||rect.y||rect.w!=atlas->w||rect.h!=atlas->h){tile=atlas->crop(rect);atlas=&tile;}
    static const Image clay(1,1,{149,163,171,255});
    if(partMode&&!hasVisiblePixels(*atlas))atlas=&clay;
    rigFrame=studioMesh.draw(*atlas,rigSize,yaw,pitch,sceneZoom,true,showModel,state["shapes"],visibleOverlays());if(partMode)highlightParts();
}
POINT App::rigHandlePoint(RECT r)const{
    int b=selectedBone();if(b<0||b>=int(studioMesh.pivots.size()))return {-100,-100};
    RECT q=rigSquare(r);Camera c(studioMesh.center,studioMesh.radius,rigSize,yaw,pitch,pf::min(40,rigSize*.10),sceneZoom);
    auto v=c.project(studioMesh.pivots[b]);double s=(q.right-q.left)/double(rigSize);return {q.left+rounded(v.x*s),q.top+rounded(v.y*s)};
}
void App::studioPaint(HDC dc,RECT r){
    fill(dc,r,RGB(20,27,37));studioFrame(r);RECT q=rigSquare(r);imageToDC(dc,rigFrame,q,false);
    if(partMode){partOverlay(dc,r);return;}
    if(rigPicked&&selectedBone()>=0){auto p=rigHandlePoint(r);auto color=rigAxisColors[rigAxis];int d=D(13);
        auto pen=CreatePen(PS_SOLID,D(2),color);auto old=SelectObject(dc,pen);auto br=SelectObject(dc,GetStockObject(NULL_BRUSH));Ellipse(dc,p.x-d,p.y-d,p.x+d,p.y+d);SelectObject(dc,old);SelectObject(dc,br);DeleteObject(pen);
        line(dc,p.x-d-D(6),p.y,p.x+d+D(6),p.y,color);line(dc,p.x,p.y-D(5),p.x,p.y+D(5),color);
        std::wstring note=wide(rigBone)+L"  /  "+std::wstring(1,L"XYZ"[rigAxis]);if(rigGrab==1)note+=L"   "+std::to_wstring(rounded(rigStartVal+rigDelta));
        text(dc,note,{p.x+d+D(6),p.y-D(17),r.right,p.y+D(13)},color);
    }
    text(dc,L"点击选部件  ·  左拖改姿势  ·  右拖转视角",{D(12),r.bottom-D(26),r.right,r.bottom-D(3)},RGB(161,173,191));
}
LRESULT App::studioEvent(UINT m,WPARAM w,LPARAM l){
    int x=GET_X_LPARAM(l),y=GET_Y_LPARAM(l);RECT r;GetClientRect(sceneView->hwnd,&r);
    if(m==WM_MOUSEWHEEL){sceneZoom=pf::clamp(sceneZoom*std::pow(1.2,GET_WHEEL_DELTA_WPARAM(w)/double(WHEEL_DELTA)),.1,8.);redrawRig();statusBar->redraw();return 0;}
    if(m==WM_RBUTTONDOWN||m==WM_MBUTTONDOWN){SetFocus(sceneView->hwnd);panning=true;lastMouseX=x;lastMouseY=y;SetCapture(sceneView->hwnd);return 0;}
    if(m==WM_MOUSEMOVE&&panning){yaw=std::remainder(yaw-(x-lastMouseX)*.55,360.);pitch=pf::clamp(pitch+(y-lastMouseY)*.55,-89.,90.);lastMouseX=x;lastMouseY=y;syncCamera();redrawRig();return 0;}
    if((m==WM_RBUTTONUP||m==WM_MBUTTONUP)&&panning){panning=false;ReleaseCapture();return 0;}
    if(m==WM_LBUTTONDOWN&&!partMode&&(w&(MK_CONTROL|MK_SHIFT))){auto id=rigCubeId;bool old=rigPicked;changePartMode(true);chooseParts(old&&!id.empty()?J::array({id}):J::array());GetClientRect(sceneView->hwnd,&r);}
    if(partMode)return partEvent(m,w,l,x,y,r);
    if(m==WM_LBUTTONDOWN){
        if(!canWrite()||rigWanted!=rigLoaded)return 0;SetFocus(sceneView->hwnd);playing=false;studioFrame(r);
        auto q=rigSquare(r);int xx=(x-q.left)*rigSize/(q.right-q.left),yy=(y-q.top)*rigSize/(q.bottom-q.top);
        auto pivot=rigHandlePoint(r);bool handle=rigPicked&&std::hypot(double(x-pivot.x),double(y-pivot.y))<=D(17);
        if(!handle){
            int i=xx>=0&&xx<rigSize&&yy>=0&&yy<rigSize?pickedCube(studioMesh.hits[yy*rigSize+xx]):-1;
            if(i<0){rigPicked=false;redrawRig();return 0;}
            auto& c=studioMesh.cubes[i];rigBone=studioMesh.bones[c.bone].name;setRigCube(c.id);
        }
        if(rigClip.empty())return 0;rigObserved=tokens();rigGrab=1;rigDownX=x;rigDownY=y;rigDelta=0;
        rigStartVal=rigValue(rigKeys(),rigAxis,rigTime/1000,rigLoop,rigChannel=="scale"?1:0);
        SetCapture(sceneView->hwnd);syncPlayback();return 0;
    }
    if(m==WM_MOUSEMOVE&&rigGrab==1){rigDelta=(x-rigDownX-(y-rigDownY)*.35)*(rigChannel=="rotation"?.65:rigChannel=="position"?.065:.0075);redrawRig();return 0;}
    if(m==WM_LBUTTONUP&&rigGrab==1){
        auto diff=rigDelta;rigGrab=0;rigDelta=0;ReleaseCapture();if(std::abs(diff)>.0001&&rigObserved==tokens()){
            J values=J::array();for(int a=0;a<3;a++)values.arr().push_back(rigValue(rigKeys(),a,rigTime/1000,rigLoop,rigChannel=="scale"?1:0));
            values[rigAxis]=rigStartVal+diff;
            J op=J::object({{"op","key"},{"clip",rigClip},{"bone",rigBone},{"channel",rigChannel},{"time_ms",rigTime}});
            if(!rigKeyId.empty()){op["uuid"]=rigKeyId;op["axis"]=std::string(1,"xyz"[rigAxis]);op["axis_value"]=rigStartVal+diff;}else op["value"]=values;
            rigCommit(op);
        }redrawRig();return 0;
    }
    if(m==WM_CAPTURECHANGED){panning=false;if(rigGrab==1){rigGrab=0;rigDelta=0;redrawRig();}return 0;}
    return UNHANDLED;
}
static std::wstring rigNumber(double x){wchar_t b[36];std::swprintf(b,36,L"%.2f",x);return b;}
void App::graphPaint(HDC dc,RECT r){
    fill(dc,r,RGB(29,35,46));int l=D(52),rr=r.right-D(14),t=D(30),b=r.bottom-D(22);if(b<=t||rr<=l)return;
    const auto& ks=rigKeys();auto axisColor=rigAxisColors[rigAxis];auto cap=wide(rigClip)+L"  /  "+wide(rigBone)+L"  /  "+wide(rigChannel)+L"."+std::wstring(1,L"xyz"[rigAxis]);
    text(dc,cap,{D(10),0,rr,D(25)},RGB(224,229,240));rigDots.clear();rigDotIds.clear();
    if(ks.empty()){text(dc,L"此通道还没有关键帧。拖动模型可记录姿势。",{l,t,rr,b},RGB(156,168,186),DT_CENTER|DT_VCENTER|DT_SINGLELINE);return;}
    if(rigGrab!=2){rigGraphLo=1e20;rigGraphHi=-1e20;for(const auto& k:ks.arr()){double v=rigPoint(k,rigAxis,false,k["time"].number());rigGraphLo=pf::min(rigGraphLo,v);rigGraphHi=pf::max(rigGraphHi,v);}
        double pad=pf::max((rigGraphHi-rigGraphLo)*.18,rigChannel=="scale"?.05:rigChannel=="rotation"?3.:.5);rigGraphLo-=pad;rigGraphHi+=pad;}
    auto X=[&](double ms){return l+rounded((rr-l)*ms/rigEnd);};auto Y=[&](double v){return b-rounded((v-rigGraphLo)/(rigGraphHi-rigGraphLo)*(b-t));};
    for(int j=0;j<3;++j){double v=rigGraphLo+(rigGraphHi-rigGraphLo)*j/2;text(dc,rigNumber(v),{1,Y(v)-D(9),l-D(5),Y(v)+D(9)},RGB(143,158,179),DT_RIGHT|DT_VCENTER|DT_SINGLELINE);line(dc,l,Y(v),rr,Y(v),RGB(57,67,83));}
    for(int j=0;j<=4;++j){int x=l+(rr-l)*j/4;line(dc,x,t,x,b,RGB(48,59,73));text(dc,rigNumber(rigEnd*j/4000)+L"s",{x-D(18),b+D(1),x+D(40),r.bottom},RGB(143,158,179));}
    int lastX=l,lastY=Y(rigValue(ks,rigAxis,0,rigLoop,0));auto pen=CreatePen(PS_SOLID,D(2),axisColor);auto old=SelectObject(dc,pen);
    MoveToEx(dc,lastX,lastY,nullptr);for(int x=l+2;x<=rr;x+=2){double sec=rigEnd*(x-l)/(rr-l)/1000;LineTo(dc,x,pf::clamp(Y(rigValue(ks,rigAxis,sec,rigLoop,0)),t-1,b+1));}SelectObject(dc,old);DeleteObject(pen);
    int now=X(rigTime);line(dc,now,t,now,b,RGB(229,202,123));
    for(const auto& k:ks.arr()){bool selected=k["uuid"].str()==rigKeyId;POINT p{X(k["time"].number()*1000),Y(rigPoint(k,rigAxis,false,k["time"].number()))};
        if(selected&&rigGrab==2){p.x=X(rigNewTime);p.y=Y(rigStartVal+rigDelta);}
        rigDots.push_back(p);rigDotIds.push_back(k["uuid"].str());int d=selected?D(5):D(3);fill(dc,{p.x-d,p.y-d,p.x+d+1,p.y+d+1},selected?RGB(255,228,156):axisColor);}
}
LRESULT App::graphEvent(UINT m,WPARAM,LPARAM l){
    RECT r;GetClientRect(rigGraph->hwnd,&r);int x=GET_X_LPARAM(l),y=GET_Y_LPARAM(l),left=D(52),right=r.right-D(14),top=D(30),bottom=r.bottom-D(22);
    double time=pf::clamp((x-left)*rigEnd/pf::max(1,right-left),0.,rigEnd);
    if(m==WM_LBUTTONDOWN){
        if(!canWrite()||rigWanted!=rigLoaded)return 0;double best=D(11);int found=-1;for(int i=0;i<int(rigDots.size());++i){
            double dist=std::hypot(x-double(rigDots[i].x),y-double(rigDots[i].y));if(dist<=best){best=dist;found=i;}}
        if(found<0){seekTime(time);return 0;}playing=false;rigObserved=tokens();rigGrab=2;rigDownX=x;rigDownY=y;rigDelta=0;rigKeyId=rigDotIds[found];
        for(const auto& k:rigKeys().arr())if(k["uuid"].str()==rigKeyId){rigTime=rigNewTime=k["time"].number()*1000;rigStartVal=rigPoint(k,rigAxis,false,rigTime/1000);break;}
        rigFocusedKey();SetCapture(rigGraph->hwnd);redrawRig();return 0;
    }
    if(m==WM_MOUSEMOVE&&rigGrab==2){rigNewTime=pf::clamp(rigTime+(x-rigDownX)*rigEnd/pf::max(1,right-left),0.,rigEnd);
        rigDelta=(rigDownY-y)*(rigGraphHi-rigGraphLo)/pf::max(1,bottom-top);rigGraph->redraw();return 0;}
    if(m==WM_LBUTTONUP&&rigGrab==2){rigGrab=0;ReleaseCapture();if(rigObserved==tokens()&&(std::abs(rigNewTime-rigTime)>.01||std::abs(rigDelta)>1e-8)){
        J op=J::object({{"op","key"},{"clip",rigClip},{"bone",rigBone},{"channel",rigChannel},{"uuid",rigKeyId},{"time_ms",rigNewTime}});
        if(std::abs(rigDelta)>1e-8){op["axis"]=std::string(1,"xyz"[rigAxis]);op["axis_value"]=rigStartVal+rigDelta;}
        rigTime=rigNewTime;rigCommit(op);
    }rigDelta=0;redrawRig();return 0;}
    if(m==WM_CAPTURECHANGED&&rigGrab==2){rigGrab=0;rigDelta=0;redrawRig();return 0;}return UNHANDLED;
}
}

