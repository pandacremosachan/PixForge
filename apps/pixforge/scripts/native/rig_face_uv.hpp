#pragma once
namespace pf {
static const J& faceTexture(const App& app,const J& face){
    if(face["texture"].isString())for(const auto& t:app.playerRig()["textures"].arr())if(t["uuid"]==face["texture"])return t;
    return nullPart();
}
void App::updateFaceCamera(RECT r){
    uvPort={D(12),D(37),pf::max(D(16),r.right-D(12)),pf::max(D(41),r.bottom-D(79))};
}
POINT App::uvToScreen(double u,double v)const{
    return {(uvPort.left+uvPort.right)/2+rounded((u-uvCenterX)*uvZoom*facePixelW),(uvPort.top+uvPort.bottom)/2+rounded((v-uvCenterY)*uvZoom*facePixelH)};
}
void App::focusFace(bool whole){
    if(partIndices.empty())return;const auto& face=partCube(rigCubeId)["faces"][activeFace];const auto& t=faceTexture(*this,face);
    if(!t.isObject())return;auto& size=t["uv_size"];auto& a=face["uv"];auto& rect=t["rect"];
    double w=size[0].number(),h=size[1].number();facePixelW=rect[2].number()/w;facePixelH=rect[3].number()/h;
    uvCenterX=whole?w*.5:(a[0].number()+a[2].number())*.5;uvCenterY=whole?h*.5:(a[1].number()+a[3].number())*.5;
    double fw=whole?w:pf::max(16.,std::abs(a[2].number()-a[0].number())*2.8),fh=whole?h:pf::max(16.,std::abs(a[3].number()-a[1].number())*2.8);
    uvZoom=pf::clamp(pf::min((uvPort.right-uvPort.left)/(fw*facePixelW),(uvPort.bottom-uvPort.top)/(fh*facePixelH)),.08,50.);
    uvFocus=rigCubeId+activeFace;
}
static void edgeBox(HDC dc,RECT r,COLORREF c,int n=1){line(dc,r.left,r.top,r.right,r.top,c,n);line(dc,r.right,r.top,r.right,r.bottom,c,n);line(dc,r.right,r.bottom,r.left,r.bottom,c,n);line(dc,r.left,r.bottom,r.left,r.top,c,n);}
static RECT between(POINT a,POINT b){return {pf::min(a.x,b.x),pf::min(a.y,b.y),pf::max(a.x,b.x),pf::max(a.y,b.y)};}
static std::array<double,4> readRectUV(const J& face){const auto& a=face["uv"];return {a[0].number(),a[1].number(),a[2].number(),a[3].number()};}
void App::facePaint(HDC dc,RECT r){
    fill(dc,r,RGB(27,34,44));line(dc,0,0,0,r.bottom,RGB(66,79,93));
    text(dc,L"逐面 UV",{D(13),D(3),r.right/2,D(31)},RGB(235,239,244));updateFaceCamera(r);
    if(partIndices.empty()){text(dc,L"在左侧点选一个方块",{D(8),D(42),r.right-D(8),r.bottom-D(30)},RGB(163,178,195),DT_CENTER|DT_VCENTER|DT_SINGLELINE);return;}
    const auto& f=partCube(rigCubeId)["faces"][activeFace];const auto& t=faceTexture(*this,f);
    const auto& all=partCube(rigCubeId)["faces"];
    text(dc,linkFaces?L"同向面联动 ●":L"单方块 ○",{r.right-D(126),D(3),r.right-D(12),D(31)},linkFaces?groupMint:RGB(165,181,198),DT_RIGHT|DT_VCENTER|DT_SINGLELINE);
    fill(dc,uvPort,RGB(18,24,32));
    if(t.isObject()){
        if(uvFocus!=rigCubeId+activeFace)focusFace();
        auto& sz=t["uv_size"];double w=sz[0].number(),h=sz[1].number();auto a=uvToScreen(0,0),b=uvToScreen(w,h);
        auto& rect=t["rect"];auto atlas=canvas.composed.crop({rect[0].integer(),rect[1].integer(),rect[2].integer(),rect[3].integer()});
        int saved=SaveDC(dc);IntersectClipRect(dc,uvPort.left,uvPort.top,uvPort.right,uvPort.bottom);imageToDC(dc,atlas,{a.x,a.y,b.x,b.y},true);
        if(uvZoom*facePixelW>=D(10)&&uvZoom*facePixelH>=D(10)){
            int u0=pf::max(0,int(uvCenterX-(uvPort.right-uvPort.left)/2/(uvZoom*facePixelW))-1),v0=pf::max(0,int(uvCenterY-(uvPort.bottom-uvPort.top)/2/(uvZoom*facePixelH))-1);
            for(int u=u0;u<=w;u++){auto p=uvToScreen(u,0);if(p.x>uvPort.right)break;line(dc,p.x,a.y,p.x,b.y,RGB(55,61,66));}
            for(int v=v0;v<=h;v++){auto p=uvToScreen(0,v);if(p.y>uvPort.bottom)break;line(dc,a.x,p.y,b.x,p.y,RGB(55,61,66));}
        }
        for(auto side:sourceSides){auto& other=all[side];if(side==activeFace||other["texture"]!=f["texture"]||!other["uv"].isArray())continue;
            auto uv=readRectUV(other);edgeBox(dc,between(uvToScreen(uv[0],uv[1]),uvToScreen(uv[2],uv[3])),RGB(98,166,170));}
        auto uv=uvGrip>=0?uvDraft:readRectUV(f);auto p=uvToScreen(uv[0],uv[1]),q=uvToScreen(uv[2],uv[3]);edgeBox(dc,between(p,q),RGB(31,32,33),D(4));edgeBox(dc,between(p,q),groupGold,D(2));
        for(int i=0;i<4;++i){int x=i&1?q.x:p.x,y=i&2?q.y:p.y,rr=D(4);fill(dc,{x-rr-1,y-rr-1,x+rr+2,y+rr+2},RGB(30,33,39));fill(dc,{x-rr,y-rr,x+rr+1,y+rr+1},i==0?groupMint:groupGold);}
        RestoreDC(dc,saved);auto detail=wide(t["name"].str())+L"    "+wide(J::array({uv[0],uv[1],uv[2],uv[3]}).dump());
        text(dc,detail,{D(13),uvPort.bottom+D(2),r.right-D(8),uvPort.bottom+D(24)},RGB(201,213,225),DT_LEFT|DT_VCENTER|DT_SINGLELINE|DT_END_ELLIPSIS);
    }else text(dc,L"此面未绑定贴图",uvPort,RGB(186,197,209),DT_CENTER|DT_VCENTER|DT_SINGLELINE);
    int l=D(12),width=pf::max(6,int(r.right)-2*l);for(int i=0;i<6;++i){
        RECT a{l+width*i/6,r.bottom-D(51),l+width*(i+1)/6-D(3),r.bottom-D(29)};
        fill(dc,a,activeFace==sourceSides[i]?RGB(84,74,59):RGB(44,53,65));text(dc,faceNames[i],a,activeFace==sourceSides[i]?groupGold:RGB(188,202,217),DT_CENTER|DT_VCENTER|DT_SINGLELINE);}
    text(dc,L"拖框平移 · 拖角缩放 · 滚轮缩放 · 右拖平移",{D(12),r.bottom-D(26),r.right-D(4),r.bottom-D(3)},RGB(161,177,192),DT_LEFT|DT_VCENTER|DT_SINGLELINE|DT_END_ELLIPSIS);
}
void App::sendFaceEdit(J op){
    if(partIndices.empty())return;op["op"]="face_uv";op["face"]=activeFace;
    op["cube_ids"]=linkFaces?partSelection:J::array({rigCubeId});rigCommit(op);
}
static void putUV(Face& f,std::array<double,4> a,const Rect& rect,int w,int h){
    f.uv={{{a[0],a[1]},{a[0],a[3]},{a[2],a[3]},{a[2],a[1]}}};std::rotate(f.uv.begin(),f.uv.begin()+f.uvTurn,f.uv.end());
    for(auto& uv:f.uv){uv[0]=(rect.x+uv[0]*rect.w)/w;uv[1]=(rect.y+uv[1]*rect.h)/h;}
}
void App::previewUV(){
    if(uvGrip<0||partIndices.empty())return;int side=int(std::find(sourceSides.begin(),sourceSides.end(),activeFace)-sourceSides.begin());
    for(auto i:partIndices){
        if(!linkFaces&&i!=partIndices.back())continue;const auto& s=partCube(studioMesh.cubes[i].id)["faces"][activeFace];const auto& t=faceTexture(*this,s);if(!t.isObject())continue;
        auto a=readRectUV(s);for(int n=0;n<4;++n)a[n]+=uvDraft[n]-uvStart[n];
        auto& size=t["uv_size"];for(int n=0;n<4;++n)a[n]/=size[n%2].number();
        if(side>=4){std::swap(a[0],a[2]);std::swap(a[1],a[3]);}
        const auto& rect=t["rect"];Rect region{rect[0].integer(),rect[1].integer(),rect[2].integer(),rect[3].integer()};
        if(rigTexture>=0)region=studioMesh.textures[rigTexture];
        for(auto& f:studioMesh.faces)if(f.element==i&&f.side==side)putUV(f,a,region,studioMesh.sheetW,studioMesh.sheetH);
    }
}
LRESULT App::faceEvent(UINT m,WPARAM w,LPARAM l){
    RECT r;GetClientRect(faceView->hwnd,&r);updateFaceCamera(r);int x=GET_X_LPARAM(l),y=GET_Y_LPARAM(l);
    if(partIndices.empty())return UNHANDLED;
    if(m==WM_LBUTTONDOWN&&y<uvPort.top&&x>r.right-D(128)){linkFaces=!linkFaces;faceView->redraw();return 0;}
    if(m==WM_LBUTTONDOWN&&y>=r.bottom-D(51)&&y<=r.bottom-D(29)){
        int i=pf::clamp((x-D(12))*6/pf::max(1,int(r.right)-D(24)),0,5);activeFace=sourceSides[i];uvFocus.clear();redrawRig();return 0;}
    const auto& f=partCube(rigCubeId)["faces"][activeFace];if(!faceTexture(*this,f).isObject())return UNHANDLED;
    if(m==WM_MOUSEWHEEL){POINT p{x,y};ScreenToClient(faceView->hwnd,&p);double du=(p.x-(uvPort.left+uvPort.right)*.5)/facePixelW,dv=(p.y-(uvPort.top+uvPort.bottom)*.5)/facePixelH;
        double old=uvZoom;uvZoom=pf::clamp(old*std::pow(1.33,GET_WHEEL_DELTA_WPARAM(w)/double(WHEEL_DELTA)),.08,80.);
        uvCenterX+=du*(1/old-1/uvZoom);uvCenterY+=dv*(1/old-1/uvZoom);faceView->redraw();return 0;}
    if(m==WM_RBUTTONDOWN||m==WM_MBUTTONDOWN){uvGrip=-2;faceMouse={x,y};SetCapture(faceView->hwnd);return 0;}
    if(m==WM_MOUSEMOVE&&uvGrip==-2){uvCenterX-=(x-faceMouse.x)/(uvZoom*facePixelW);uvCenterY-=(y-faceMouse.y)/(uvZoom*facePixelH);faceMouse={x,y};faceView->redraw();return 0;}
    if((m==WM_RBUTTONUP||m==WM_MBUTTONUP)&&uvGrip==-2){uvGrip=-1;ReleaseCapture();return 0;}
    if(m==WM_LBUTTONDOWN&&PtInRect(&uvPort,{x,y})){
        if(!canWrite()||rigLoaded!=rigWanted)return 0;uvStart=uvDraft=readRectUV(f);
        auto p=uvToScreen(uvStart[0],uvStart[1]),q=uvToScreen(uvStart[2],uvStart[3]);
        double best=D(8);int grip=-1;for(int i=0;i<4;++i){double gap=std::hypot(double(x-(i&1?q.x:p.x)),double(y-(i&2?q.y:p.y)));if(gap<best){best=gap;grip=i;}}
        RECT box=between(p,q);InflateRect(&box,2,2);if(grip<0&&PtInRect(&box,{x,y}))grip=4;
        if(grip>=0){uvGrip=grip;partObserved=tokens();faceMouse={x,y};SetCapture(faceView->hwnd);return 0;}
        return 0;
    }
    if(m==WM_MOUSEMOVE&&uvGrip>=0){
        double snap=(w&MK_SHIFT)?.125:1.;double du=std::round((x-faceMouse.x)/(uvZoom*facePixelW)/snap)*snap,dv=std::round((y-faceMouse.y)/(uvZoom*facePixelH)/snap)*snap;uvDraft=uvStart;
        if(uvGrip==4){for(int i=0;i<4;++i)uvDraft[i]+=i%2?dv:du;}else{uvDraft[(uvGrip&1)?2:0]+=du;uvDraft[(uvGrip&2)?3:1]+=dv;}
        redrawRig();return 0;}
    if(m==WM_LBUTTONUP&&uvGrip>=0){uvGrip=-1;ReleaseCapture();if(uvStart!=uvDraft&&partObserved==tokens()){
        J delta=J::array();for(int i=0;i<4;++i)delta.arr().push_back(uvDraft[i]-uvStart[i]);sendFaceEdit(J::object({{"delta",delta}}));}
        redrawRig();return 0;}
    if(m==WM_CAPTURECHANGED){uvGrip=-1;redrawRig();return 0;}
    if(m==WM_LBUTTONDBLCLK){focusFace(true);faceView->redraw();return 0;}return UNHANDLED;
}
}

