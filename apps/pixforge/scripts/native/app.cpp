#include "window_images.hpp"
#include "app.hpp"
#include "uv.hpp"
#include "rig_viewport.hpp"
#include "rig_tools.hpp"
#include "rig_components.hpp"
#include "rig_face_uv.hpp"
#include "scene_editor.hpp"
#include "minecraft_editor.hpp"
#include "minecraft_preview.hpp"
#include "minecraft_workbench.hpp"
#include "material_editor.hpp"

namespace pf {
static constexpr wchar_t PROJECT_FILTER[]=L"工程 / 模型 / 材质\0*.pixforge;*.bbmodel;*.json;*.png;*.px\0所有文件\0*.*\0";
static constexpr wchar_t SAVE_FILTER[]=L"PixForge 工程\0*.pixforge\0";
App::App(fs::path work,fs::path run,std::string path,bool start):workspace(fs::absolute(work)),runtime(fs::absolute(run)),startupPath(std::move(path)){
    static bool registered=false;if(!registered){WNDCLASSEXW wc{sizeof wc};wc.lpfnWndProc=proc;wc.hInstance=GetModuleHandleW(nullptr);wc.lpszClassName=L"PixForgeNativeMain";wc.hCursor=LoadCursorW(nullptr,IDC_ARROW);applicationIcons(wc);RegisterClassExW(&wc);registered=true;}
    hwnd=CreateWindowExW(WS_EX_CONTROLPARENT,L"PixForgeNativeMain",L"PixForge",WS_OVERLAPPEDWINDOW|WS_CLIPCHILDREN,CW_USEDEFAULT,CW_USEDEFAULT,CW_USEDEFAULT,CW_USEDEFAULT,nullptr,nullptr,GetModuleHandleW(nullptr),this);if(!hwnd)throw std::runtime_error("Cannot create native window");dpi=int(GetDpiForWindow(hwnd));updateWindowIcons(hwnd);updateFont();create();
    rpc=std::make_unique<Rpc>(hwnd,runtime);rpc->onError=[this](const J& value){error(value);};renderer=std::make_unique<Renderer>(hwnd);frontend=std::make_unique<Frontend>(hwnd,runtime/L"gui");SetTimer(hwnd,1,500,nullptr);SetTimer(hwnd,2,16,nullptr);if(start)startPage.show(false);else layout();ShowWindow(hwnd,SW_SHOW);UpdateWindow(hwnd);fetch();
    auto dwm=LoadLibraryW(L"dwmapi.dll");if(dwm){using Fn=HRESULT(WINAPI*)(HWND,DWORD,LPCVOID,DWORD);auto f=reinterpret_cast<Fn>(GetProcAddress(dwm,"DwmSetWindowAttribute"));BOOL enabled=TRUE;if(f)f(hwnd,20,&enabled,sizeof enabled);FreeLibrary(dwm);}
}
App::~App(){frontend.reset();renderer.reset();gpu.reset();rpc.reset();if(IsWindow(hwnd))DestroyWindow(hwnd);if(font)DeleteObject(font);if(boldFont)DeleteObject(boldFont);}
void App::updateFont(){if(font)DeleteObject(font);if(boldFont)DeleteObject(boldFont);font=CreateFontW(-MulDiv(10,dpi,72),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Microsoft YaHei UI");boldFont=CreateFontW(-MulDiv(10,dpi,72),0,0,0,FW_SEMIBOLD,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Microsoft YaHei UI");for(auto& s:surfaces)s->font=font;EnumChildWindows(hwnd,[](HWND c,LPARAM f)->BOOL{SendMessageW(c,WM_SETFONT,WPARAM(f),TRUE);return TRUE;},LPARAM(font));}
HWND App::button(HWND parent,std::string name,std::wstring title,std::function<void()> callback,std::function<bool()> checked){int id=nextButton++;HWND h=CreateWindowExW(0,L"BUTTON",title.c_str(),WS_CHILD|WS_VISIBLE|WS_TABSTOP|BS_OWNERDRAW,0,0,1,1,parent,reinterpret_cast<HMENU>(INT_PTR(id)),GetModuleHandleW(nullptr),nullptr);SendMessageW(h,WM_SETFONT,WPARAM(font),TRUE);buttons.emplace(id,Button{h,title,std::move(callback),std::move(checked)});handles[name]=h;installButtonFocus(h);return h;}
HWND App::combo(HWND parent,std::string name,std::initializer_list<std::wstring> values){HWND h=CreateWindowExW(0,L"COMBOBOX",L"",WS_CHILD|WS_VISIBLE|WS_TABSTOP|CBS_DROPDOWNLIST|WS_VSCROLL,0,0,1,1,parent,reinterpret_cast<HMENU>(INT_PTR(nextButton++)),GetModuleHandleW(nullptr),nullptr);SendMessageW(h,WM_SETFONT,WPARAM(font),TRUE);for(auto& s:values)SendMessageW(h,CB_ADDSTRING,0,LPARAM(s.c_str()));choice::styleSelect(h);comboSet(h,0);handles[name]=h;return h;}
Surface* App::surface(HWND parent,int id,std::function<void(HDC,RECT)> draw){auto s=std::make_unique<Surface>(parent,id,font,std::move(draw));auto ptr=s.get();ptr->onError=[this](const std::string& error){panning=false;if(dragging||strokePending)endStroke(true);auto capture=GetCapture();if(capture&&(capture==hwnd||IsChild(hwnd,capture)))ReleaseCapture();message=L"无法完成操作："+wide(error);if(statusBar)statusBar->redraw();};surfaces.push_back(std::move(s));return ptr;}
void App::error(const J& failure){
    message=wide(failure["code"].str()+": "+failure["error"].str());statusBar->redraw();std::string abandonedLease=lease;
    if(strokePending||strokeCommitting||dragging){if(stroke.before.w&&loaded)canvas.layers[canvas.active].image=stroke.before;dragging=strokePending=strokeCommitting=false;strokeReleased=false;lease.clear();canvas.composite();frameDirty=true;canvasView->redraw();}
    fetching=mutationPending=false;afterFetch={};userActions.clear();
    if(startPage.visible)startPage.layout();
    if(!abandonedLease.empty()&&rpc){rpc->call(payload("stroke_end",J::object({{"lease",abandonedLease},{"cancel",true}})),[this](const J&){fetch();},true);return;}
    if(rpc&&rpc->idle()&&failure["code"].str()!="SESSION_UNAVAILABLE")fetch();
}
J App::tokens()const{return J::object({{"expected_document_id",state["document_id"]},{"expected_revision",state["revision"]}});}
J App::payload(std::string action,J fields)const{fields["action"]=action;return fields;}
bool App::canWrite()const{return !selecting&&!dragging&&!strokePending&&!strokeCommitting&&!fetching&&!mutationPending;}
void App::mutate(std::string action,J fields,std::function<void(const J&)> after){if(!loaded||!canWrite()){message=L"正在提交或同步，请稍候。";statusBar->redraw();return;}playing=false;if(action=="open"||action=="new"||action=="create_project"){clearSelection();tool=HAND;pendingTool=-1;}mutationPending=true;auto observed=tokens();for(auto& [key,value]:observed.obj())fields[key]=value;rpc->call(payload(action,std::move(fields)),[this,after](const J& response){if(after)after(response);fetch();});}
void App::fetch(){if(!rpc||fetching||dragging||strokePending||strokeCommitting)return;fetching=true;rpc->call(payload("snapshot"),[this](J& response){fetching=false;apply(response);});}
void App::apply(J& response){
    // The visible canvas and state advance together, once per completed snapshot.
    const J& previous=state;
    J& incoming=response["state"];
    bool first=!loaded,changedDocument=first||previous["document_id"]!=incoming["document_id"];
    bool removedModel=!first&&!previous["shapes"]["model"].null()&&incoming["shapes"]["model"].null();
    bool changedScene=changedDocument||previous["scene_animation"]!=incoming["scene_animation"];
    auto oldLayer=loaded?canvas.layers[canvas.active].name:std::string();
    auto oldRect=loaded&&frame>=0&&frame<int(previous["animation"]["rectangles"].size())?rectJson(previous["animation"]["rectangles"][frame]):Rect{};
    nativePatches=response["native_protocol"]["stroke_patches"].boolean();fastPoll=response["native_protocol"]["fast_poll"].boolean();
    canvas=Canvas::decode(response["canvas"]);state=std::move(incoming);loaded=true;
    undoCount=response["undo_count"].integer();redoCount=response["redo_count"].integer();
    if(changedDocument){
        step=0;tool=HAND;pendingTool=-1;firstFit=true;playing=false;inspectorVisible=true;inspectorTab=0;uvGuides=false;timelineVisible=true;
        grid=tiled=onion=false;showModel=true;std::fill(std::begin(overlays),std::end(overlays),false);
        panel=state["shapes"]["model"].null()?0:1;yaw=25;pitch=20;sceneZoom=1;
    }else if(removedModel)panel=0;
    step=pf::clamp(step,0,int(state["animation"]["steps"].size())-1);frame=state["animation"]["steps"][step]["frame"].integer();
    numberField::range(sizeField,1,brushLimit());
    if(changedDocument||oldLayer!=canvas.layers[canvas.active].name||oldRect.json()!=currentRect().json())clearSelection();
    if(changedScene)resetScenePlayer();
    if(changedDocument||modelUv!=response["model_uv"]){modelUv=std::move(response["model_uv"]);clearUvPin();}
    if(changedDocument){
        hiddenSkin.fill(false);
        if(playerSkin()){panel=0;inspectorTab=2;uvGuides=true;}
    }
    if(first)readyTime=milliseconds()-bootTime;
    mutationPending=false;loadStudio(changedDocument);refresh();
    if(pendingTool>=0){int requested=pendingTool;pendingTool=-1;selectTool(requested);}
    if(firstFit&&!startPage.visible){firstFit=false;fit();}
    if(!startupPath.empty()){auto path=std::move(startupPath);startupPath.clear();openProject(fs::path(wide(path)));}
    if(afterFetch){auto next=std::move(afterFetch);afterFetch={};next();}
    while(canWrite()&&!userActions.empty()){auto action=std::move(userActions.front());userActions.pop_front();action();}
}
void App::poll(){if(panning&&panel!=0)return;if(!loaded){if(rpc->idle())fetch();return;}if(!canWrite()){if(!lease.empty()&&milliseconds()-lastRecovery>20000){lastRecovery=milliseconds();rpc->call(payload("stroke_keepalive",J::object({{"lease",lease}})),{},true);}return;}if(!rpc->idle()||fetching)return;++pollCount;rpc->call(payload(fastPoll?"view_poll":"status"),[this](const J& value){if(value.contains("error")){fastPoll=false;return;}auto key=J::object({{"document_id",value["document_id"]},{"revision",value["revision"]},{"project_path",value["project_path"]},{"saved_digest",value["saved_digest"]},{"dirty",value["dirty"]},{"dependency_current",value.contains("dependency_current")?value["dependency_current"]:value["animation_source_current"]}});if(value["document_id"]!=state["document_id"]||value["revision"]!=state["revision"]||(!lastPoll.empty()&&key!=lastPoll))fetch();lastPoll=key;},true);}
void App::refresh(){
    loading=true;frameDirty=true;frameCache=-1;renderKey.clear();message.clear();
    refreshPalette();
    syncLayers();
    refreshRigTree();
    EnableWindow(handles.at("undo"),undoCount>0);EnableWindow(handles.at("redo"),redoCount>0);
    if(adjusting()&&!canvas.layers[canvas.active].visible)message=L"当前图层已隐藏";
    loading=false;layout();syncPlayback();canvasView->redraw();details->redraw();
}
Rect App::currentRect()const{if(!loaded)return{0,0,32,32};return rectJson(state["animation"]["rectangles"][frame]);}
bool App::saveBefore(std::function<void()> next){if(!loaded||!canWrite())return false;if(!state["dirty"].boolean()){next();return true;}int answer=MessageBoxW(hwnd,L"当前工程尚未保存。先保存可编辑工程，再继续？\n选择“否”会保留核心恢复稿。",L"PixForge",MB_YESNOCANCEL|MB_ICONQUESTION);if(answer==IDCANCEL)return false;if(answer==IDNO){next();return true;}auto observed=tokens();fs::path path=state["project_path"].isString()?fs::path(wide(state["project_path"].str())):chooseFile(hwnd,workspace/L"未命名.pixforge",true,SAVE_FILTER,L"pixforge");if(path.empty())return false;if(observed!=tokens())throw std::runtime_error("工程已变化，请重新保存");afterFetch=std::move(next);mutate("save",J::object({{"path",pathText(path)}}));return true;}
void App::openProject(fs::path path,std::string armModel){
    if(!loaded||!canWrite())return;auto observed=tokens();
    if(path.empty())path=chooseFile(hwnd,workspace,false,armModel.empty()?PROJECT_FILTER:L"玩家皮肤 PNG\0*.png\0",nullptr);
    if(path.empty())return;
    if(observed!=tokens())throw std::runtime_error("工程已变化，请重新打开文件");
    saveBefore([this,path,armModel]{firstFit=true;step=frame=0;J options=J::object({{"path",pathText(path)}});
        if(!armModel.empty())options["arm_model"]=armModel;
        mutate("open",options,[this](const J&){if(startPage.visible)afterFetch=[this]{startPage.hide();};});});
}
void App::saveProject(bool as){if(!loaded||!canWrite())return;auto observed=tokens();fs::path path=state["project_path"].isString()?fs::path(wide(state["project_path"].str())):workspace/L"未命名.pixforge";if(as||state["project_path"].null())path=chooseFile(hwnd,path,true,SAVE_FILTER,L"pixforge");if(path.empty())return;if(observed!=tokens())throw std::runtime_error("工程已变化，请重新保存");mutate("save",J::object({{"path",pathText(path)}}));}
void App::exportPng(){
    if(!loaded||!canWrite())return;auto observed=tokens();
    auto path=chooseFile(hwnd,workspace/L"atlas.png",true,L"PNG\0*.png\0",L"png");if(path.empty())return;
    if(observed!=tokens())throw std::runtime_error("工程在选择路径期间已变化，请重新导出");
    J options=J::object({{"path",pathText(path)},{"overwrite",true}});
    if(state["approved_for_export"].boolean()){mutate("export",options);return;}
    mutate("approve",J::object({{"user_request","用户选择导出当前材质 PNG"},{"source","desktop_user"}}),[this,options](const J& result){
        auto request=options;request["expected_document_id"]=result["state"]["document_id"];request["expected_revision"]=result["state"]["revision"];
        rpc->call(payload("export",request),[this](const J&){fetch();});
    });
}
void App::seek(int target,bool pause){if(!loaded||!canWrite())return;if(pause){playing=false;double time=0;for(int i=0;i<pf::clamp(target,0,int(state["animation"]["steps"].size())-1);++i)time+=state["animation"]["steps"][i]["duration_ms"].number();if(scenePlayer)scenePlayer->setTextureTime(time);else elapsed=time;playStart=milliseconds();}int previousFrame=frame;step=pf::clamp(target,0,int(state["animation"]["steps"].size())-1);frame=state["animation"]["steps"][step]["frame"].integer();if(frame!=previousFrame){clearSelection();uvX=uvY=-1;if(!uvRegion.empty())details->redraw();else clearUvPin();}frameDirty=true;++frameSwitches;canvasView->redraw();details->redraw();syncPlayback();statusBar->redraw();requestRender();if(frame!=previousFrame)syncLayers();if(pause)rpc->call(payload("view",J::object({{"frame",frame}})),{},true);}
void App::playback(){if(!playing||!loaded||!canWrite())return;double now=milliseconds();if(studio()){if(now-lastSceneTick<30)return;lastSceneTick=now;rigTime+=now-playStart;playStart=now;if(rigTime>=rigEnd){if(rigLoop)rigTime=std::fmod(rigTime,rigEnd);else{rigTime=rigEnd;playing=false;}}rigFocusedKey();redrawRig();syncPlayback();return;}if(IsIconic(hwnd)){playStart=now;return;}double delta=now-playStart;playStart=now;if(scenePlayer){advanceProgram(delta);if(now-lastSceneTick>=(gpu&&gpu->available?16:50)){lastSceneTick=now;requestRender();timeline->redraw();}return;}elapsed+=delta;auto& steps=state["animation"]["steps"];double total=0;for(auto& item:steps.arr())total+=item["duration_ms"].number();double at=state["animation"]["loop"].boolean()?std::fmod(elapsed,total):pf::min(elapsed,total-.0000001);double t=0;int found=int(steps.size()-1);for(int i=0;i<int(steps.size());++i){t+=steps[i]["duration_ms"].number();if(at<t){found=i;break;}}if(found!=step)seek(found,false);if(!state["scene_animation"].null()){double duration=state["scene_animation"]["duration_ms"].number();if(!state["scene_animation"]["loop"].boolean()&&elapsed>=duration){elapsed=duration;playing=false;syncPlayback();}if(now-lastSceneTick>=(gpu&&gpu->available?16:50)){lastSceneTick=now;requestRender();timeline->redraw();}}else if(!state["animation"]["loop"].boolean()&&elapsed>=total){playing=false;syncPlayback();}}
void App::seekTime(double value,bool pause){if(!loaded||!canWrite())return;if(pause)playing=false;if(studio()){rigTime=pf::clamp(value,0.,rigEnd);rigFocusedKey();redrawRig();syncPlayback();return;}if(scenePlayer){scenePlayer->seek(pf::clamp(value,0.,sceneDuration()));elapsed=scenePlayer->clock();playStart=milliseconds();programTextureStep();syncStateControls();timeline->redraw();requestRender();return;}elapsed=pf::clamp(value,0.,state["scene_animation"]["duration_ms"].number());playStart=milliseconds();double total=0;for(auto& s:state["animation"]["steps"].arr())total+=s["duration_ms"].number();double at=state["animation"]["loop"].boolean()?std::fmod(elapsed,total):pf::min(elapsed,total-1e-7),sum=0;int found=0;for(auto& s:state["animation"]["steps"].arr()){sum+=s["duration_ms"].number();if(at<sum)break;++found;}seek(pf::clamp(found,0,int(state["animation"]["steps"].size())-1),false);timeline->redraw();requestRender();}
void App::setColor(Pixel c){
    ink=c;auto hsv=toHsv(c);if(hsv[1]>0)colorHue=hsv[0];
    InvalidateRect(handles.at("color_chip"),nullptr,FALSE);colorField->redraw();swatches->redraw();
}
void App::setZoom(double value,int x,int y){pixelAutoFit=false;value=pf::clamp(value,.01,64.);if(x>=0&&y>=0){RECT r;GetClientRect(canvasView->hwnd,&r);auto rect=currentRect();int n=tiled?3:1;double ox=(r.right-rect.w*n*zoom)/2.+panX,oy=(r.bottom-rect.h*n*zoom)/2.+panY;double ix=(x-ox)/zoom,iy=(y-oy)/zoom;panX=x-ix*value-(r.right-rect.w*n*value)/2.;panY=y-iy*value-(r.bottom-rect.h*n*value)/2.;}zoom=value;canvasView->redraw();statusBar->redraw();syncButtons();}
void App::fit(){if(panel==1){sceneZoom=1;requestRender();statusBar->redraw();return;}RECT r;GetClientRect(canvasView->hwnd,&r);auto f=currentRect();int n=tiled?3:1;panX=panY=0;setZoom(pf::min((r.right-D(72))/double(f.w*n),(r.bottom-D(72))/double(f.h*n)));pixelAutoFit=true;}
void App::frameCacheUpdate(){
    if(!loaded)return;
    auto frameRect=currentRect();
    bool full=frameDirty||frameCache!=frame;
    if(!full&&!framePatch.w)return;
    auto area=full?frameRect:intersect(frameRect,framePatch);
    frameWidth=frameRect.w;frameHeight=frameRect.h;frameDib.resize(size_t(frameWidth)*frameHeight);
    const auto& animation=static_cast<const J&>(state)["animation"];
    int count=int(animation["steps"].size());Rect neighbors[2]{};
    if(onion&&count>1)for(int i=0;i<2;++i){
        int k=step+(i?1:-1);if(animation["loop"].boolean())k=(k+count)%count;
        if(k>=0&&k<count)neighbors[i]=rectJson(animation["rectangles"][animation["steps"][k]["frame"].integer()]);
    }
    for(int y=area.y;y<area.y+area.h;++y)for(int x=area.x;x<area.x+area.w;++x){
        int fx=x-frameRect.x,fy=y-frameRect.y;auto c=canvas.composed.get(x,y);
        if(onion&&count>1){
            Pixel ghost{};for(int i=0;i<2;++i)if(neighbors[i].w){
                Pixel tint=i?Pixel{233,118,147,64}:Pixel{92,182,231,72};
                tint[3]=uint8_t(rounded(canvas.composed.get(neighbors[i].x+fx,neighbors[i].y+fy)[3]*tint[3]/255.));
                ghost=over(ghost,tint);
            }c=over(ghost,c);
        }
        Pixel bg=(fx/4+fy/4)%2?Pixel{65,70,80,255}:Pixel{55,59,68,255};
        unsigned alpha=c[3];auto mix=[&](int i){return (c[i]*alpha+bg[i]*(255-alpha)+127)/255;};
        frameDib[size_t(fy)*frameWidth+fx]=(mix(0)<<16)|(mix(1)<<8)|mix(2);
    }
    frameCache=frame;frameDirty=false;framePatch={};
}
void App::drawFrame(HDC dc,RECT dest)const{
    BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=frameWidth;info.bmiHeader.biHeight=-frameHeight;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;
    SetStretchBltMode(dc,COLORONCOLOR);StretchDIBits(dc,dest.left,dest.top,dest.right-dest.left,dest.bottom-dest.top,0,0,frameWidth,frameHeight,frameDib.data(),&info,DIB_RGB_COLORS,SRCCOPY);
}
void App::paintCanvas(HDC dc,RECT area){double started=milliseconds();fill(dc,area,rgb(backgroundPixel(-1)));if(!loaded){text(dc,message,area,RGB(147,154,169),DT_CENTER|DT_VCENTER|DT_SINGLELINE);return;}frameCacheUpdate();int n=tiled?3:1;double w=frameWidth*zoom,h=frameHeight*zoom,ox=(area.right-w*n)/2.+panX,oy=(area.bottom-h*n)/2.+panY;
    for(int b=0;b<n;++b)for(int a=0;a<n;++a){int x=rounded(ox+a*w),y=rounded(oy+b*h),rw=rounded(ox+(a+1)*w)-x,rh=rounded(oy+(b+1)*h)-y;drawFrame(dc,{x,y,x+rw,y+rh});if(grid&&zoom>=6){for(int xx=0;xx<=frameWidth;++xx){int sx=rounded(x+xx*zoom);if(sx>=0&&sx<area.right)line(dc,sx,pf::max(0,y),sx,pf::min(area.bottom,y+rh),RGB(69,72,82));}for(int yy=0;yy<=frameHeight;++yy){int sy=rounded(y+yy*zoom);if(sy>=0&&sy<area.bottom)line(dc,pf::max(0,x),sy,pf::min(area.right,x+rw),sy,RGB(69,72,82));}}}
    if(tiled){int x=rounded(ox+w),y=rounded(oy+h);line(dc,x,y,rounded(x+w),y,RGB(155,147,255));line(dc,x,y,x,rounded(y+h),RGB(155,147,255));line(dc,rounded(x+w),y,rounded(x+w),rounded(y+h),RGB(155,147,255));line(dc,x,rounded(y+h),rounded(x+w),rounded(y+h),RGB(155,147,255));}
    paintUvGuides(dc,area,ox,oy,n);
    if(selection.w>0){auto f=currentRect();for(int b=0;b<n;++b)for(int a=0;a<n;++a){RECT r{rounded(ox+a*w+(selection.x-f.x)*zoom),rounded(oy+b*h+(selection.y-f.y)*zoom),rounded(ox+a*w+(selection.x-f.x+selection.w)*zoom),rounded(oy+b*h+(selection.y-f.y+selection.h)*zoom)};auto brush=SelectObject(dc,GetStockObject(NULL_BRUSH));HPEN white=CreatePen(PS_SOLID,1,RGB(255,255,255)),dash=CreatePen(PS_DOT,1,RGB(0,0,0));auto old=SelectObject(dc,white);Rectangle(dc,r.left,r.top,r.right,r.bottom);SelectObject(dc,dash);SetBkMode(dc,TRANSPARENT);Rectangle(dc,r.left,r.top,r.right,r.bottom);SelectObject(dc,old);SelectObject(dc,brush);DeleteObject(white);DeleteObject(dash);}}
    ++paintCount;paintSamples.push_back(milliseconds()-started);if(paintSamples.size()>4096)paintSamples.erase(paintSamples.begin(),paintSamples.begin()+2048);
}
int App::canvasCursorSlot()const{
    if(panning)return GRABBING;
    // A temporary mode changes the next click, not a stroke already in progress.
    if(!dragging&&!selecting&&!movingSelection){
        if(tool==HAND||(GetKeyState(VK_SPACE)&0x8000))return HAND;
        if(GetKeyState(VK_MENU)&0x8000)return PICKER;
    }
    return tool;
}
HCURSOR App::canvasCursor(){return canvasCursors.get(canvasCursorSlot(),dpi);}
void App::updateCanvasCursor(){if(!canvasView||panel!=0)return;POINT at;if((GetCapture()==canvasView->hwnd)||(GetCursorPos(&at)&&WindowFromPoint(at)==canvasView->hwnd))SetCursor(canvasCursor());}
LRESULT App::canvasEvent(UINT m,WPARAM w,LPARAM l){
    if(!loaded)return UNHANDLED;if(m==WM_SETCURSOR){SetCursor(canvasCursor());return TRUE;}int x=GET_X_LPARAM(l),y=GET_Y_LPARAM(l);RECT area;GetClientRect(canvasView->hwnd,&area);
    auto pixel=[&](int mx,int my)->std::pair<int,int>{auto r=currentRect();int n=tiled?3:1;double ox=(area.right-r.w*n*zoom)/2.+panX,oy=(area.bottom-r.h*n*zoom)/2.+panY;int px=int(std::floor((mx-ox)/zoom)),py=int(std::floor((my-oy)/zoom));if(px<0||py<0||px>=r.w*n||py>=r.h*n)return{-1,-1};return{r.x+px%r.w,r.y+py%r.h};};
    if(m==WM_MOUSEWHEEL){POINT p{x,y};ScreenToClient(canvasView->hwnd,&p);setZoom(zoom*std::pow(1.25,GET_WHEEL_DELTA_WPARAM(w)/double(WHEEL_DELTA)),p.x,p.y);return 0;}
    if(m==WM_MOUSELEAVE){if(uvGuides&&!uvPinned){uvX=uvY=-1;uvHits.clear();canvasView->redraw();details->redraw();}return 0;}
    if(m==WM_LBUTTONDOWN&&uvGuides&&(GetKeyState(VK_CONTROL)&0x8000)){auto [px,py]=pixel(x,y);if(px>=0){inspectUvPixel(px,py,true);inspectorVisible=true;inspectorTab=2;layout();}return 0;}
    if(m==WM_LBUTTONDOWN||m==WM_MBUTTONDOWN){SetFocus(canvasView->hwnd);if(m==WM_MBUTTONDOWN||tool==HAND||(GetKeyState(VK_SPACE)&0x8000)){panning=true;lastMouseX=x;lastMouseY=y;SetCapture(canvasView->hwnd);updateCanvasCursor();return 0;}auto [px,py]=pixel(x,y);if(px<0)return 0;if(tool==3||(GetKeyState(VK_MENU)&0x8000)){setColor(canvas.composed.get(px,py));return 0;}if(!canWrite())return 0;if(tool==8){playing=false;selecting=true;selectionX=px;selectionY=py;selection={px,py,1,1};SetCapture(canvasView->hwnd);canvasView->redraw();return 0;}if(tool==9){if(!canvas.layers[canvas.active].visible)return 0;if(!selection.w){message=L"先用矩形选区 M 框选要移动的像素，或 Ctrl+A 全选。";statusBar->redraw();return 0;}if(!selection.contains(px,py))return 0;movingSelection=true;selectionStart=selection;selectionX=px;selectionY=py;stroke=Stroke();stroke.before=canvas.layers[canvas.active].image;strokeRegion=currentRect();startLease();SetCapture(canvasView->hwnd);return 0;}beginStroke(px,py);SetCapture(canvasView->hwnd);return 0;}
    if(m==WM_RBUTTONDOWN){auto [px,py]=pixel(x,y);if(px>=0)setColor(canvas.composed.get(px,py));return 0;}
    if(m==WM_MOUSEMOVE){if(panning){pixelAutoFit=false;panX+=x-lastMouseX;panY+=y-lastMouseY;lastMouseX=x;lastMouseY=y;canvasView->redraw();return 0;}auto [px,py]=pixel(x,y);if(uvGuides){TRACKMOUSEEVENT leave{sizeof leave,TME_LEAVE,canvasView->hwnd,0};POINT pointer;if(GetCursorPos(&pointer)&&WindowFromPoint(pointer)==canvasView->hwnd)TrackMouseEvent(&leave);inspectUvPixel(px,py);}if(selecting||movingSelection){if(px>=0)updateSelection(px,py);}else if(dragging){if(px>=0)moveStroke(px,py);else stroke.lastValid=false;}return 0;}
    if(m==WM_LBUTTONUP||m==WM_MBUTTONUP){if(panning){panning=false;ReleaseCapture();updateCanvasCursor();return 0;}if(selecting){selecting=false;canvasView->redraw();}if(dragging)endStroke();movingSelection=false;ReleaseCapture();return 0;}
    if(m==WM_CAPTURECHANGED){if(dragging)endStroke(true);selecting=false;movingSelection=false;panning=false;updateCanvasCursor();return 0;}
    return UNHANDLED;
}
void App::beginStroke(int x,int y){
    if(brushOpacity==0)return;
    if(!canWrite()||!canvas.layers[canvas.active].visible)return;playing=false;stroke=Stroke();stroke.tool=TOOLS[tool];stroke.ink=ink;stroke.size=brushSize;stroke.opacity=brushOpacity/100.;stroke.mx=mirrorX;stroke.my=mirrorY;stroke.solid=solid;if(selection.w&&!selection.contains(x,y))return;stroke.begin(canvas.layers[canvas.active].image,currentRect(),x,y);stroke.clip=selection;strokeRegion={x,y,1,1};fillApplied=false;startLease();moveStroke(x,y);
}
void App::startLease(){playing=false;dragging=strokePending=true;strokeReleased=strokeCancelled=false;lease.clear();lastRecovery=milliseconds();auto request=tokens();request["frame"]=frame;if(!nativePatches)rpc->call(payload("view",J::object({{"frame",frame}})),{},true);rpc->call(payload("stroke_begin",request),[this](const J& result){strokePending=false;lease=result["lease"].str();if(strokeReleased)commitStroke();});}
void App::moveStroke(int x,int y){if(!dragging)return;if(stroke.tool=="fill"&&fillApplied)return;if(stroke.tool=="fill")fillApplied=true;double start=milliseconds();auto dirty=stroke.draw(canvas.layers[canvas.active].image,x,y);if(!dirty.w)return;strokeRegion=unite(strokeRegion,dirty);canvas.composite(dirty);
    if(onion)frameDirty=true;else framePatch=unite(framePatch,dirty);canvasView->redraw();if(inspectorVisible)details->redraw();strokeSamples.push_back(milliseconds()-start);if(strokeSamples.size()>4096)strokeSamples.erase(strokeSamples.begin(),strokeSamples.begin()+2048);}
void App::endStroke(bool cancel){if(!selecting&&!dragging&&!strokePending)return;dragging=false;strokeReleased=true;strokeCancelled=cancel;if(cancel){if(movingSelection)selection=selectionStart;canvas.layers[canvas.active].image=stroke.before;canvas.composite();frameDirty=true;canvasView->redraw();}if(!lease.empty())commitStroke();}
void App::commitStroke(){
    if(strokeCommitting||lease.empty())return;strokeCommitting=true;
    auto finish=[this]{rpc->call(payload("stroke_end",J::object({{"lease",lease},{"cancel",strokeCancelled}})),[this](const J&){strokeCommitting=false;strokePending=false;strokeReleased=false;lease.clear();fetch();});};
    if(strokeCancelled){finish();return;}if(!nativePatches){rpc->call(payload("stroke_end",J::object({{"lease",lease},{"canvas",canvas.encode()}})),[this](const J&){strokeCommitting=strokePending=strokeReleased=false;lease.clear();fetch();});return;}
    auto candidate=std::make_shared<Image>(canvas.layers[canvas.active].image.crop(strokeRegion));auto row=std::make_shared<int>(0);auto continuation=std::make_shared<std::function<void()>>();std::weak_ptr<std::function<void()>> weak=continuation;std::string layerName=canvas.layers[canvas.active].name;
    *continuation=[this,candidate,row,finish,weak,layerName]{if(*row>=candidate->h){finish();return;}int rows=pf::min(candidate->h-*row,pf::max(1,262144/candidate->w));auto patch=candidate->crop({0,*row,candidate->w,rows});J request=J::object({{"lease",lease},{"layer",layerName},{"rect",J::array({strokeRegion.x,strokeRegion.y+*row,candidate->w,rows})},{"data",base64(patch.bytes)}});*row+=rows;auto hold=weak.lock();rpc->call(payload("stroke_patch",request),[hold](const J&){if(hold)(*hold)();});};(*continuation)();
}
void App::clearSelection(){selection={};selecting=false;if(canvasView)canvasView->redraw();}
void App::updateSelection(int x,int y){
    auto f=currentRect();if(selecting){selection={pf::min(selectionX,x),pf::min(selectionY,y),std::abs(x-selectionX)+1,std::abs(y-selectionY)+1};canvasView->redraw();return;}
    if(!movingSelection)return;int dx=pf::clamp(x-selectionX,f.x-selectionStart.x,f.x+f.w-selectionStart.x-selectionStart.w),dy=pf::clamp(y-selectionY,f.y-selectionStart.y,f.y+f.h-selectionStart.y-selectionStart.h);selection={selectionStart.x+dx,selectionStart.y+dy,selectionStart.w,selectionStart.h};auto& image=canvas.layers[canvas.active].image;image=stroke.before;if(dx||dy){auto source=stroke.before.crop(selectionStart);for(int yy=0;yy<selectionStart.h;++yy)for(int xx=0;xx<selectionStart.w;++xx)image.set(selectionStart.x+xx,selectionStart.y+yy,{0,0,0,0});for(int yy=0;yy<source.h;++yy)for(int xx=0;xx<source.w;++xx){int a=selection.x+xx,b=selection.y+yy;image.set(a,b,over(image.get(a,b),source.get(xx,yy)));}}canvas.composite(f);frameDirty=true;canvasView->redraw();if(inspectorVisible)details->redraw();
}
void App::editPixels(Image next,Rect region){if(!canWrite())return;auto before=canvas.layers[canvas.active].image;if(before==next)return;stroke=Stroke();stroke.before=std::move(before);strokeRegion=region;canvas.layers[canvas.active].image=std::move(next);canvas.composite(region);frameDirty=true;canvasView->redraw();if(inspectorVisible)details->redraw();startLease();endStroke();}
void App::selectionAction(std::string action){
    if(!loaded||panel!=0||!canWrite())return;playing=false;if(action=="none"){clearSelection();return;}if(action=="all"){selection=currentRect();canvasView->redraw();return;}auto f=currentRect();if(action=="paste"){if(!canvas.layers[canvas.active].visible)throw std::runtime_error("请先显示当前图层，再粘贴");auto source=pastePixels(hwnd);int x=selection.w?selection.x:f.x,y=selection.w?selection.y:f.y;int width=pf::min(source.w,f.x+f.w-x),height=pf::min(source.h,f.y+f.h-y);auto next=canvas.layers[canvas.active].image;for(int b=0;b<height;++b)for(int a=0;a<width;++a)next.set(x+a,y+b,over(next.get(x+a,y+b),source.get(a,b)));selection={x,y,width,height};editPixels(std::move(next),selection);message=L"已粘贴到当前图层，可用移动工具 V 调整位置；超出当前帧的部分已裁切。";statusBar->redraw();return;}
    if(!selection.w){message=L"请先用矩形选区 M 框选，或 Ctrl+A 全选当前帧。";statusBar->redraw();return;}
    if(action=="copy"||action=="cut")copyPixels(hwnd,canvas.layers[canvas.active].image.crop(selection));if(action=="copy"){message=L"已复制当前图层选区，保留 RGBA 透明度。";statusBar->redraw();return;}if(action=="cut"||action=="delete"){if(!canvas.layers[canvas.active].visible)throw std::runtime_error("请先显示当前图层，再删除或剪切");auto next=canvas.layers[canvas.active].image;for(int y=selection.y;y<selection.y+selection.h;++y)for(int x=selection.x;x<selection.x+selection.w;++x)next.set(x,y,{0,0,0,0});editPixels(std::move(next),selection);}
}
void App::userAction(std::function<void()> callback){if(!loaded){message=L"正在连接工程，请稍候。";statusBar->redraw();return;}if(!canWrite()){if(userActions.size()>=16)throw std::runtime_error("待执行操作过多，请等待当前提交完成");userActions.push_back(std::move(callback));message=L"正在提交，按钮操作会在同步完成后执行。";statusBar->redraw();return;}callback();}
J App::controls()const{
    J rows=J::array();for(auto& [name,h]:handles){
        if(!IsWindowVisible(h))continue;auto b=buttons.find(GetDlgCtrlID(h));
        rows.arr().push_back(J::object({{"name",name},{"id",GetDlgCtrlID(h)},{"class",utf8(Form::className(h))},{"label",stringEdit(h)},
            {"on_screen",true},{"enabled",IsWindowEnabled(h)!=FALSE},{"checked",b!=buttons.end()&&b->second.checked?J(b->second.checked()):J()}}));
    }
    return J::object({{"schema","pixelforge.native-controls/v1"},{"panel",startPage.visible?"start":panel?"shapes":"pixels"},{"window_visible",IsWindowVisible(hwnd)!=FALSE},{"controls",rows}});
}
J App::hiddenSkinOverlays()const{
    J names=J::array();
    if(playerSkin())for(size_t i=0;i<hiddenSkin.size();++i)if(hiddenSkin[i])names.arr().push_back(SKIN_SWITCHES[i]);
    return names;
}
Image App::modelTexture()const{
    Image image=canvas.composed.crop(currentRect());
    if(!playerSkin())return image;
    for(const auto& [name,part]:modelUv["player_skin"]["parts"].obj()){
        auto sw=std::find(SKIN_SWITCHES.begin(),SKIN_SWITCHES.end(),part["overlay"].str());
        if(sw==SKIN_SWITCHES.end()||!hiddenSkin[size_t(sw-SKIN_SWITCHES.begin())])continue;
        for(const auto& [side,box]:part["outer"]["faces"].obj()){
            Rect r=rectJson(box);
            for(int y=r.y;y<r.y+r.h;++y)for(int x=r.x;x<r.x+r.w;++x)image.set(x,y,{0,0,0,0});
        }
    }
    return image;
}
std::vector<std::string> App::visibleOverlays()const{
    constexpr std::array<const char*,3> names={"base","collision","selection"};
    std::vector<std::string> active;for(int i=0;i<3;++i)if(overlays[i])active.emplace_back(names[i]);
    return active;
}
void App::requestRender(){
    if(startPage.visible||!loaded||!renderer||panel==0)return;
    if(studio()){sceneView->redraw();if(rigGraph)rigGraph->redraw();return;}
    std::string context=state["content_digest"].str()+":"+std::to_string(panel)+":"+std::to_string(frame)+":";for(bool b:overlays)context+=b?'1':'0';context+=showModel?'1':'0';
    if(playerSkin())context+=hiddenSkinOverlays().dump();
    std::string geometryContext=context;context+=":studio";std::string key=context+":"+J(yaw).dump()+":"+J(pitch).dump()+":zoom:"+J(sceneZoom).dump();if(panel==1&&!state["scene_animation"].null())key+=":scene:"+J(sceneTime(state["scene_animation"],elapsed)).dump();if(scenePlayer)key+=":state:"+scenePlayer->state+":"+std::to_string(scenePlayer->generation)+":local:"+J(scenePlayer->at).dump();if(key==renderKey)return;renderKey=key;sceneContext=context;++sceneSerial;
    if(gpu&&gpu->available){
        gpu->setBackground(3);if(gpuContext!=geometryContext){gpu->configure(state["shapes"],modelTexture(),visibleOverlays(),showModel,state["scene_animation"]);gpuContext=geometryContext;}
        gpu->time(elapsed);gpu->angles(yaw,pitch);gpu->magnification(sceneZoom);gpu->playback(scenePlayer?scenePlayer->view():J());sceneView->redraw();
        // Continuous orbit updates a persistent GPU scene only. A software hit
        // map is refreshed on release, not once per incoming mouse event.
        if(panning||(panel==1&&!state["scene_animation"].null()))return;
    }
    auto found=renderCache.find(key);if(found!=renderCache.end()){rendered=found->second;presentedSerial=sceneSerial;sceneView->redraw();return;}
    RenderJob job;job.key=key;job.background=3;job.context=context;job.serial=sceneSerial;job.definition=state["shapes"];job.scene=panel==1?state["scene_animation"]:J();job.time=elapsed;job.sceneView=scenePlayer?scenePlayer->view():J();job.atlas=modelTexture();job.size=400;job.yaw=yaw;job.pitch=pitch;job.zoom=sceneZoom;job.overlays=visibleOverlays();job.showModel=showModel;renderer->submit(std::move(job));sceneView->redraw();
}
void App::renderComplete(RenderReady* value){auto result=std::shared_ptr<RenderReady>(value);++renderCount;lastRenderMs=result->ms;if(!renderCache.count(result->key))renderOrder.push_back(result->key);renderCache[result->key]=result;while(renderOrder.size()>16){renderCache.erase(renderOrder.front());renderOrder.pop_front();}
    // An orbit frame remains valid when a newer angle is already queued. Present
    // every newly completed frame for the same document/texture/overlay context.
    if(result->context==sceneContext&&(!rendered||rendered->context!=sceneContext||result->serial>=presentedSerial)){rendered=result;presentedSerial=result->serial;sceneView->redraw();}}
void App::paintScene(HDC dc,RECT r){
    if(studio()){studioPaint(dc,r);return;}
    if(gpu&&gpu->ready()){auto image=gpu->readback();imageToDC(dc,image,r,false);return;}
    fill(dc,r,rgb(backgroundPixel(-1)));if(rendered){auto& image=rendered->result.image;double ratio=pf::min((r.right-D(16))/double(image.w),(r.bottom-D(24))/double(image.h));int w=rounded(image.w*ratio),h=rounded(image.h*ratio),x=(r.right-w)/2,y=(r.bottom-h)/2;imageToDC(dc,image,{x,y,x+w,y+h},false);for(size_t i=0;i<rendered->result.lines.size();++i){auto segment=rendered->result.lines[i];line(dc,x+rounded(segment[0].x*ratio),y+rounded(segment[0].y*ratio),x+rounded(segment[1].x*ratio),y+rounded(segment[1].y*ratio),rgb(rendered->result.lineColors[i]));}}
    if(!rendered||rendered->context!=sceneContext)text(dc,L"正在载入模型…",{D(13),r.bottom-D(35),r.right,r.bottom-D(10)},RGB(155,147,255));}
static J sampleSummary(const std::vector<double>& values){if(values.empty())return J::object({{"samples",0}});auto sorted=values;std::sort(sorted.begin(),sorted.end());return J::object({{"samples",values.size()},{"mean_ms",std::accumulate(values.begin(),values.end(),0.)/values.size()},{"p50_ms",sorted[sorted.size()/2]},{"p95_ms",sorted[pf::min(sorted.size()-1,size_t(sorted.size()*.95))]},{"max_ms",sorted.back()}});}
J App::metrics()const{return J::object({{"schema","pixelforge.native-metrics/v1"},{"startup_to_snapshot_ms",readyTime},{"paint",sampleSummary(paintSamples)},{"stroke_update",sampleSummary(strokeSamples)},{"paint_count",size_t(paintCount)},{"frame_switches",size_t(frameSwitches)},{"render_count",size_t(renderCount)},{"last_scene_render_ms",lastRenderMs},{"last_rpc_ms",rpc?rpc->lastMs:0},{"rpc_count",size_t(rpc?rpc->count:0)},{"poll_count",size_t(pollCount)},{"scene_cache_entries",renderCache.size()},{"render_thread",true},{"gpu",gpu?gpu->metrics():J::object()},{"rpc_thread",true},{"python_loaded_in_frontend",false},{"qt_loaded_in_frontend",false}});}
J App::uiStatus()const{
    int slot=canvasCursorSlot();std::string cursorName=panel!=0?"default":slot==GRABBING?"grabbing":slot==HAND?"grab":TOOLS[slot];
    J visibleOverlays=J::array();for(int i=0;i<3;++i)if(overlays[i])visibleOverlays.arr().push_back(std::array<const char*,3>{"base","collision","selection"}[i]);
    J stateNames=J::array();if(studio())for(const auto& a:playerRig()["clips"].arr())stateNames.arr().push_back(J::object({{"id",a["name"]},{"label",a["name"]},{"duration_ms",a["duration_ms"]},{"loop",a["loop"].str()=="loop"}}));if(scenePlayer)for(auto& s:state["scene_animation"]["states"].arr())stateNames.arr().push_back(J::object({{"id",s["id"]},{"label",s["label"]},{"duration_ms",s["duration_ms"]},{"loop",s["loop"]},{"next",s["next"]}}));
    RECT r;GetClientRect(hwnd,&r);return J::object({{"application","PixForge"},{"version","4.12.1"},{"frontend","native-cpp"},{"platform","windows-x64"},{"loaded",loaded},{"pending",!canWrite()},{"document_id",state["document_id"]},{"revision",state["revision"]},{"content_digest",state["content_digest"]},{"runtime",pathText(runtime)},{"workspace",pathText(workspace)},{"panel",startPage.visible?"start":panel?"shapes":"pixels"},{"start_task",startPage.visible?J(startPage.taskName()):J()},{"tool",TOOLS[tool]},{"canvas_cursor",cursorName},{"selection",selection.w?selection.json():J()},{"selection_coordinates","atlas pixels; bounded to active frame and layer"},{"color",hexColor(ink)},{"brush_size",std::to_string(brushSize)},{"brush_size_range",J::array({1,brushLimit()})},{"opacity",J(brushOpacity).dump()},{"fill",solid},{"mirror_x",mirrorX},{"mirror_y",mirrorY},{"grid",grid},{"tile",tiled},{"onion",onion},{"uv",uvStatus()},{"background",panel==0?"checker":"studio"},{"zoom",zoom},{"pan",J::array({panX,panY})},{"step",step},{"frame",frame},{"playing",playing},{"time_ms",sceneClock()},{"scene_duration_ms",(scenePlayer||studio())?J(sceneDuration()):state["scene_animation"]["duration_ms"]},{"scene_controller",scenePlayer?scenePlayer->summary():J()},{"scene_states",stateNames},{"scene_transform_tracks",sceneEntries(state["scene_animation"],"transforms").size()},{"scene_emitters",sceneEntries(state["scene_animation"],"emitters").size()},{"yaw",yaw},{"pitch",pitch},{"scene_zoom",sceneZoom},{"overlays",visibleOverlays},{"rig_selection",playerRig().isObject()?J::object({{"bone",rigBone},{"cube",rigCube}}):J()},{"hidden_skin_overlays",hiddenSkinOverlays()},{"show_model",showModel},{"adjusting",adjusting()},{"inspector",inspectorVisible},{"timeline",showTransport()},{"inspector_tab",std::array<const char*,3>{"colors","navigation","uv"}[inspectorTab]},{"size",J::array({r.right,r.bottom})},{"dpi",dpi},{"message",utf8(message)},{"rig_components",partStatus()},{"rig_clip",rigClip},{"rig_texture",rigTexture},{"rig_channel",rigChannel},{"rig_axis",std::string(1,"xyz"[rigAxis])},{"rig_key",rigKeyId},{"rig_curve",rigCurve},{"rig_cube_id",rigCubeId},{"scene_ready",(studio()?rigWanted==rigLoaded:(gpu&&gpu->ready()))||(rendered&&rendered->context==sceneContext)}});
}
J App::uiHelp()const{
    return J::object({{"schema","pixelforge.native-ui/v1"},{"transport","private application channel; use workbench commands"},{"read_only_actions",J::array({"ui_status","ui_help","ui_metrics","ui_controls","ui_scene_sample","ui_scene_context"})},{"ui_set",J::object({{"panel",J::array({"pixels","shapes"})},{"tool",J::array({"hand","pen","eraser","fill","picker","line","rect","ellipse","select","move"})},{"color","#RRGGBBAA"},{"brush_size","integer 1..min(frame width, frame height), in pixels"},{"opacity","number 0..100, percent"},{"fill","boolean"},{"mirror_x","boolean"},{"mirror_y","boolean"},{"grid","boolean"},{"tile","boolean"},{"onion","boolean"},{"uv_guides","boolean"},{"uv_pixel","[atlas x,y]; pin all regions sampling this pixel"},{"uv_region","region id (R01...) to pin; null to clear pin"},{"zoom","number .01..64"},{"fit","boolean"},{"pan","[x,y] in logical screen pixels"},{"time_ms","scene clock; finite milliseconds 0..scene duration; view only"},{"scene_state","named state id; select a canonical state preview"},{"scene_event",J::array({"start","stop"})},{"scene_demo","boolean; preview the complete process"},{"scene_repeat","boolean; repeat process preview only"},{"step","zero-based texture playback step"},{"playing","boolean"},{"scene_zoom","number .1..8; 3D magnification; wheel up enlarges; independent of pixel canvas"},{"yaw","number -180..180"},{"pitch","number -89..90"},{"overlays","array of base/collision/selection"},{"rig_mode","pose / model"},{"rig_cubes","ordered array of cube UUIDs; last is active"},{"rig_transform","scale / rotate / pivot"},{"rig_transform_axis","x / y / z / all (uniform scale)"},{"rig_anchor","selection / individual"},{"rig_uv_editor","show UV beside the bind pose"},{"rig_face","north / south / east / west / up / down"},{"rig_link_faces","apply UV drag to same face of all selected cubes"},{"rig_channel","rotation / position / scale"},{"rig_axis","x / y / z"},{"rig_texture","texture name, UUID or null for face bindings"},{"rig_curve","show curve editor"},{"rig_bone","select bone by name (view only)"},{"rig_cube","select cube on current bone by name or UUID (view only)"},{"hidden_skin_overlays","hidden player clothing: hat, jacket, right_sleeve, left_sleeve, right_pants, left_pants; [] shows all"},{"show_model","boolean"},{"inspector","boolean"},{"timeline","boolean"},{"inspector_tab",J::array({"colors","navigation","uv"})},{"window_size","[width,height] client pixels; minimum 680x420"}})},{"ui_capture",J::object({{"path","absolute PNG path for this application's client-area discussion screenshot"},{"overwrite","boolean, default false"}})},{"ui_scene_editor",J::object({{"operation",J::array({"open","status","field","invoke","capture","cancel","apply"})},{"draft_only","field/invoke edit only the independent draft; apply validates observed document tokens and adds one undo step"},{"entry","workbench editor --editor-kind scene --operation open"}})},{"ui_minecraft_editor",J::object({{"operation",J::array({"open","status","field","invoke","capture","cancel","apply"})},{"entry","workbench editor --editor-kind target --operation open"},{"draft_only",true},{"approval_or_export",false}})},{"ui_minecraft_preview",J::object({{"operation",J::array({"open","status","configure","field","invoke","camera","capture","cancel"})},{"entry","workbench editor --editor-kind preview --operation open"},{"read_only",true}})},{"ui_minecraft_workbench",J::object({{"operation",J::array({"open","status","field","invoke","capture","cancel"})},{"entry","workbench editor --editor-kind regression --operation open"},{"draft_only","Inspection is read only; apply actions validate document tokens and add undo history. Never approves or exports."}})},{"ui_minecraft_material_editor",J::object({{"operation",J::array({"open","status","field","invoke","paint","capture","cancel"})},{"entry","workbench editor --editor-kind material --operation open"},{"pixel_semantics","raw 8-bit values; independent channels; alpha is data; mutations use shared undo"}})},{"document_operations","All document commands remain available with document_id/revision. UI commands never approve/export artwork."}});
}
J App::uiCommand(const J& request){
    std::string action=request["action"].str("ui_status");if(action=="ui_minecraft_material_editor")return materialEditorCommand(*this,request);if(action=="ui_minecraft_workbench")return minecraftWorkbenchCommand(*this,request);if(action=="ui_minecraft_preview")return minecraftPreviewCommand(*this,request);if(action=="ui_scene_editor")return sceneEditorCommand(*this,request);if(action=="ui_minecraft_editor")return minecraftEditorCommand(*this,request);if(action=="ui_help")return uiHelp();if(action=="status"||action=="ui_status")return uiStatus();if(action=="desktop_launch"){
        if(request["path"].isString()){auto path=fs::path(wide(request["path"].str()));userAction([this,path]{openProject(path);});}
        else if(!startPage.visible)userAction([this,resume=request["from_editor"].boolean()]{startPage.show(resume);});
        return J::object({{"accepted",true}});
    }if(action=="focus"){ShowWindow(hwnd,SW_RESTORE);SetForegroundWindow(hwnd);return uiStatus();}if(action=="ui_scene_sample"&&studio()){auto command=J::object({{"time_ms",request["time_ms"].number(rigTime)},{"scene_state",request["scene_state"].str(rigClip)}});return httpCall(runtime,payload("scene_sample",command))["sample"];}
    if(action=="ui_scene_sample"){double moment=request.contains("time_ms")?request["time_ms"].number(-1):elapsed;if(moment<0||moment>120000)throw std::runtime_error("time_ms out of range");if(scenePlayer){if(request.contains("scene_state")){auto id=request["scene_state"].str();if(!scenePlayer->hasState(id))throw std::runtime_error("Unknown animation state");return nativeSceneSample(state["scene_animation"],state["shapes"]["model"],moment,J(),id);}if(request.contains("time_ms")){ScenePlayer copy=*scenePlayer;copy.seek(moment);return nativeSceneSample(state["scene_animation"],state["shapes"]["model"],moment,copy.view());}return nativeSceneSample(state["scene_animation"],state["shapes"]["model"],elapsed,scenePlayer->view());}return nativeSceneSample(state["scene_animation"],state["shapes"]["model"],moment);}if(action=="ui_scene_context"&&studio())return J::object({{"scene_state",rigClip},{"time_ms",rigTime},{"loop",rigLoop}});
    if(action=="ui_scene_context")return scenePlayer?scenePlayer->view():J();if(action=="ui_metrics")return metrics();if(action=="ui_controls")return controls();if(action=="ui_close"){
        if(!IsWindowEnabled(hwnd))throw std::runtime_error("Close or cancel the active editor before closing the workbench");
        if(fetching)return J::object({{"error","Workbench is refreshing its snapshot"},{"code","VIEW_SYNC_PENDING"}});
        if(!loaded||!canWrite())throw std::runtime_error("Frontend busy; wait for synchronization");
        // A save can change dirty/path without a document revision. Check the
        // live project before deciding whether the user needs a save prompt.
        auto current=httpCall(runtime,payload("status"));
        if(!current["dirty"].isBool()||request["expected_document_id"]!=current["document_id"]||
           request["expected_revision"]!=current["revision"]||current["document_id"]!=state["document_id"]||
           current["revision"]!=state["revision"])throw std::runtime_error("Document/revision conflict; reread state before closing");
        state["dirty"]=current["dirty"];state["project_path"]=current["project_path"];
        if(state["dirty"].boolean())PostMessageW(hwnd,WM_CLOSE,0,0);
        else close();
        return J::object({{"closing",true}});
    }if(action=="ui_capture"){if(!loaded)throw std::runtime_error("Frontend has no document snapshot yet");auto path=fs::path(wide(request["path"].str()));if(!path.is_absolute())throw std::runtime_error("Capture path must be absolute");capture(path,request["overwrite"].boolean());return J::object({{"path",pathText(path)},{"document_id",state["document_id"]},{"revision",state["revision"]},{"purpose","discussion screenshot of own application"}});}
    if(action!="ui_set")throw std::runtime_error("Unknown frontend action; read ui_help");if(!loaded||!canWrite())return J::object({{"error","Frontend is syncing or a manual stroke is active"},{"code","BUSY"}});const J& options=request["settings"];if(!options.isObject())throw std::runtime_error("ui_set requires settings object");auto allowed=uiHelp()["ui_set"];for(auto& [key,value]:options.obj())if(!allowed.contains(key))throw std::runtime_error("Unknown UI setting: "+key);
    auto enumIndex=[&](std::string name,std::initializer_list<std::string> values)->int{if(!options.contains(name))return -1;auto value=options[name].str();int i=0;for(auto& item:values){if(value==item)return i;++i;}throw std::runtime_error("Invalid "+name);};
    int nextPanel=enumIndex("panel",{"pixels","shapes"}),nextTool=enumIndex("tool",{"pen","eraser","fill","picker","line","rect","ellipse","hand","select","move"}),nextInspector=enumIndex("inspector_tab",{"colors","navigation","uv"});
    for(auto name:{"fill","mirror_x","mirror_y","grid","tile","onion","uv_guides","fit","playing","show_model","inspector","timeline","scene_demo","scene_repeat"})if(options.contains(name)&&!options[name].isBool())throw std::runtime_error(std::string(name)+" must be boolean");
    for(auto [name,range]:{std::pair<const char*,std::pair<double,double>>{"brush_size",{1,double(brushLimit())}},{"opacity",{0,100}},{"zoom",{.01,64}},{"scene_zoom",{.1,8}},{"yaw",{-180,180}},{"pitch",{-89,90}}})if(options.contains(name)){auto& value=options[name];if(!value.isNumber()||value.number()<range.first||value.number()>range.second||(std::string(name)=="brush_size"&&value.number()!=std::floor(value.number())))throw std::runtime_error(std::string("Invalid ")+name);}
    double targetDuration=sceneDuration();if(!studio()&&(options.contains("scene_state")||options.contains("scene_event")||options.contains("scene_demo")||options.contains("scene_repeat"))){if(!scenePlayer)throw std::runtime_error("Current scene has no named states");if((options.contains("scene_state")&&options.contains("scene_event"))||((options.contains("scene_state")||options.contains("scene_event"))&&options.contains("scene_demo")))throw std::runtime_error("Choose a state, event or process preview in one update");std::string target=options.contains("scene_state")?options["scene_state"].str():options.contains("scene_event")?scenePlayer->route(options["scene_event"].str()):scenePlayer->state;if(!scenePlayer->hasState(target))throw std::runtime_error("Unknown state or unavailable event");if(options.contains("scene_demo")&&options["scene_demo"].boolean())targetDuration=state["scene_animation"]["duration_ms"].number();else if(options.contains("scene_state")||options.contains("scene_event")||options.contains("scene_demo"))for(auto& clip:state["scene_animation"]["states"].arr())if(clip["id"].str()==target)targetDuration=clip["duration_ms"].number();}
    if(studio()&&options.contains("scene_state")){
        auto named=options["scene_state"].str();bool found=false;for(const auto& a:playerRig()["clips"].arr())if(a["name"].str()==named){targetDuration=pf::max(1.,a["duration_ms"].number());found=true;break;}
        if(!found)throw std::runtime_error("找不到动作："+named);
    }
    if(options.contains("time_ms")&&(!options["time_ms"].isNumber()||(!studio()&&state["scene_animation"].null())||options["time_ms"].number()<0||options["time_ms"].number()>targetDuration))throw std::runtime_error("time_ms outside scene timeline");
    if(options.contains("time_ms")&&options.contains("step"))throw std::runtime_error("Choose time_ms or texture step in a single UI update");
    if(options.contains("step")&&(!options["step"].isNumber()||options["step"].number()!=std::floor(options["step"].number())||options["step"].integer()<0||options["step"].integer()>=int(state["animation"]["steps"].size())))throw std::runtime_error("Step out of range");
    Pixel nextColor=options.contains("color")?color(options["color"].str()):ink;for(auto name:{"pan","window_size"})if(options.contains(name)){auto a=options[name];if(!a.isArray()||a.size()!=2||!a[0].isNumber()||!a[1].isNumber()||std::abs(a[0].number())>100000||std::abs(a[1].number())>100000)throw std::runtime_error(std::string("Invalid ")+name);}if(options.contains("window_size")){auto a=options["window_size"];if(a[0].number()!=std::floor(a[0].number())||a[1].number()!=std::floor(a[1].number())||a[0].integer()<D(680)||a[1].integer()<D(420)||a[0].integer()>8192||a[1].integer()>8192)throw std::runtime_error("Unsupported window size");}
    std::string nextBone=options["rig_bone"].str(rigBone),nextCube=options["rig_cube"].str(options.contains("rig_bone")?"":rigCube);
    if(options.contains("rig_bone")||options.contains("rig_cube")){
        bool found=false,foundCube=nextCube.empty();
        const auto& bones=playerRig()["bones"];
        if(bones.isArray())for(const auto& b:bones.arr())if(b["name"].str()==nextBone){
            found=true;for(const auto& c:b["cubes"].arr())if(c["name"].str()==nextCube||c["uuid"].str()==nextCube)foundCube=true;
        }
        if(!found||!foundCube)throw std::runtime_error("未找到指定骨骼或其方块");
    }
    auto nextSkin=hiddenSkin;
    if(options.contains("hidden_skin_overlays")){
        const auto& hidden=options["hidden_skin_overlays"];nextSkin.fill(false);
        if(!hidden.isArray()||(!hidden.empty()&&!playerSkin()))throw std::runtime_error("服装开关用于玩家皮肤；请传入服装名数组");
        for(const auto& value:hidden.arr()){
            auto it=std::find(SKIN_SWITCHES.begin(),SKIN_SWITCHES.end(),value.str());
            if(it==SKIN_SWITCHES.end())throw std::runtime_error("未知玩家外层："+value.str());
            nextSkin[size_t(it-SKIN_SWITCHES.begin())]=true;
        }
    }
    bool nextOverlays[3]={overlays[0],overlays[1],overlays[2]};if(options.contains("overlays")){if(!options["overlays"].isArray())throw std::runtime_error("Overlays must be an array");std::fill(std::begin(nextOverlays),std::end(nextOverlays),false);for(auto& v:options["overlays"].arr()){auto s=v.str();if(s=="base")nextOverlays[0]=true;else if(s=="collision")nextOverlays[1]=true;else if(s=="selection")nextOverlays[2]=true;else throw std::runtime_error("Unknown shape overlay");}}
    if(options.contains("uv_pixel")){auto target=options.contains("step")?rectJson(state["animation"]["rectangles"][state["animation"]["steps"][options["step"].integer()]["frame"].integer()]):currentRect();auto p=options["uv_pixel"];if(!p.isArray()||p.size()!=2||!p[0].isNumber()||!p[1].isNumber()||p[0].number()!=std::floor(p[0].number())||p[1].number()!=std::floor(p[1].number())||!target.contains(p[0].integer(),p[1].integer()))throw std::runtime_error("uv_pixel must be an atlas pixel within the current frame");}
    if(options.contains("uv_region")&&!options["uv_region"].null()){bool found=false;for(auto& g:modelUv["regions"].arr())if(g["id"]==options["uv_region"])found=true;if(!found)throw std::runtime_error("Unknown UV region");}
    if(scenePlayer){if(options.contains("scene_state"))scenePlayer->select(options["scene_state"].str());if(options.contains("scene_event")){scenePlayer->event(options["scene_event"].str());playing=true;}if(options.contains("scene_demo")){if(options["scene_demo"].boolean()){scenePlayer->beginSequence();playing=true;}else scenePlayer->sequenceMode=false;}if(options.contains("scene_repeat"))scenePlayer->repeat=options["scene_repeat"].boolean();elapsed=scenePlayer->clock();programTextureStep();playStart=milliseconds();}
    if(studio()){
        if(options.contains("scene_state")&&rigClip!=options["scene_state"].str())changeRigClip(options["scene_state"].str());
        if(options.contains("rig_texture")){rigTexture=-1;int i=0;for(const auto& t:playerRig()["textures"].arr()){if(t["uuid"]==options["rig_texture"]||t["name"]==options["rig_texture"])rigTexture=i;++i;}
            if(!options["rig_texture"].null()&&rigTexture<0)throw std::runtime_error("找不到所选贴图");comboSet(rigTextureCombo,rigTexture+1);}
        if(options.contains("rig_axis")){auto it=std::string("xyz").find(options["rig_axis"].str());if(it>2)throw std::runtime_error("选择 x、y 或 z");rigAxis=int(it);comboSet(rigAxisCombo,rigAxis);}
        if(options.contains("rig_channel")){int idx=enumIndex("rig_channel",{"rotation","position","scale"});rigChannel=options["rig_channel"].str();comboSet(rigChannelCombo,idx);}
        if(options.contains("rig_curve"))rigCurve=options["rig_curve"].boolean();
    }
    if(options.contains("rig_bone")||options.contains("rig_cube")){rigBone=nextBone;rigCube=nextCube;rigCubeId=nextCube;rigPicked=true;refreshRigTree();rigFocusedKey();}
    if(studio()){
        if(options.contains("rig_mode"))changePartMode(enumIndex("rig_mode",{"pose","model"})==1);
        if(options.contains("rig_cubes")){
            const auto& ids=options["rig_cubes"];if(!ids.isArray())throw std::runtime_error("rig_cubes 使用方块 UUID 数组");
            for(const auto& id:ids.arr())if(!partCube(id.str()).isObject())throw std::runtime_error("找不到方块："+id.str());
            changePartMode(true);chooseParts(ids);
        }
        if(options.contains("rig_transform")){partTool=enumIndex("rig_transform",{"scale","rotate","pivot"});setPartAxis();}
        if(options.contains("rig_transform_axis")){partAxis=enumIndex("rig_transform_axis",{"x","y","z","all"});setPartAxis();}
        if(options.contains("rig_anchor"))partAnchor=enumIndex("rig_anchor",{"selection","individual"});
        if(options.contains("rig_uv_editor"))toggleFaces(options["rig_uv_editor"].boolean());
        if(options.contains("rig_face")){int fi=enumIndex("rig_face",{"north","south","east","west","up","down"});activeFace=sourceSides[fi];uvFocus.clear();}
        if(options.contains("rig_link_faces"))linkFaces=options["rig_link_faces"].boolean();
    }
    hiddenSkin=nextSkin;
    if(nextPanel>=0){panel=nextPanel;if(startPage.visible)startPage.hide();}if(nextTool>=0){tool=nextTool;if(tool==HAND)clearSelection();if(nextPanel<0)panel=0;}if(nextInspector>=0)inspectorTab=nextInspector;if(ink!=nextColor)setColor(nextColor);
    auto boolean=[&](const char* name,bool& field){if(options.contains(name))field=options[name].boolean();};boolean("fill",solid);boolean("mirror_x",mirrorX);boolean("mirror_y",mirrorY);boolean("grid",grid);boolean("tile",tiled);boolean("onion",onion);boolean("uv_guides",uvGuides);boolean("show_model",showModel);boolean("inspector",inspectorVisible);boolean("timeline",timelineVisible);for(int i=0;i<3;++i)overlays[i]=nextOverlays[i];if(options.contains("brush_size")){brushSize=options["brush_size"].integer();numberField::set(sizeField,brushSize);}if(options.contains("opacity")){brushOpacity=options["opacity"].number();numberField::set(opacityField,brushOpacity);}if(options.contains("scene_zoom"))sceneZoom=options["scene_zoom"].number();if(options.contains("yaw"))yaw=options["yaw"].number();if(options.contains("pitch"))pitch=options["pitch"].number();if(options.contains("step"))seek(options["step"].integer());if(options.contains("time_ms"))seekTime(options["time_ms"].number());if(options.contains("playing")){playing=options["playing"].boolean()&&!(studio()&&partMode);playStart=milliseconds();if(!studio()&&state["scene_animation"].null()){elapsed=0;for(int i=0;i<step;++i)elapsed+=state["animation"]["steps"][i]["duration_ms"].number();}}
    if(options.contains("window_size")){auto a=options["window_size"];RECT r{0,0,a[0].integer(),a[1].integer()};AdjustWindowRectExForDpi(&r,DWORD(GetWindowLongPtrW(hwnd,GWL_STYLE)),FALSE,0,dpi);SetWindowPos(hwnd,nullptr,0,0,r.right-r.left,r.bottom-r.top,SWP_NOMOVE|SWP_NOZORDER);}
    if(options.contains("uv_region")){clearUvPin();if(!options["uv_region"].null()){uvGuides=uvPinned=true;uvRegion=options["uv_region"].str();for(int i=0;i<int(modelUv["regions"].size());++i)if(modelUv["regions"][i]["id"].str()==uvRegion)uvHits={i};}}
    if(options.contains("uv_pixel")){uvGuides=true;clearUvPin();inspectUvPixel(options["uv_pixel"][0].integer(),options["uv_pixel"][1].integer(),true);}
    syncStateControls();layout();syncPlayback();if(options.contains("zoom"))setZoom(options["zoom"].number());if(options.contains("pan")){pixelAutoFit=false;panX=options["pan"][0].number();panY=options["pan"][1].number();}if(options["fit"].boolean())fit();frameDirty=true;canvasView->redraw();details->redraw();requestRender();updateCanvasCursor();return uiStatus();
}
void App::capture(const fs::path& path,bool overwrite){if(IsIconic(hwnd)){ShowWindow(hwnd,SW_RESTORE);UpdateWindow(hwnd);}auto ext=path.extension().wstring();std::transform(ext.begin(),ext.end(),ext.begin(),::towlower);if(ext!=L".png")throw std::runtime_error("Discussion capture requires .png");if(fs::exists(path)&&!overwrite)throw std::runtime_error("Capture already exists; choose a new path or explicit overwrite");
    checkCaptureSource(path,state);
    captureWindowPng(hwnd,path);
}
bool App::key(MSG& msg){
    if(startPage.visible)return startPage.key(msg);
    if((msg.wParam==VK_SPACE||msg.wParam==VK_MENU)&&
       (msg.message==WM_KEYDOWN||msg.message==WM_KEYUP||msg.message==WM_SYSKEYDOWN||msg.message==WM_SYSKEYUP)){
        updateCanvasCursor();
        // Alt belongs to the eyedropper on the canvas; don't enter the system menu on release.
        if(msg.wParam==VK_MENU&&panel==0&&GetFocus()==canvasView->hwnd)return true;
    }
    if(msg.message!=WM_KEYDOWN&&msg.message!=WM_SYSKEYDOWN)return false;bool ctrl=(GetKeyState(VK_CONTROL)&0x8000)!=0,shift=(GetKeyState(VK_SHIFT)&0x8000)!=0,alt=(GetKeyState(VK_MENU)&0x8000)!=0;HWND focus=GetFocus();std::wstring cls=Form::className(focus);bool typing=cls==L"Edit"||cls==L"ComboBox"||cls==L"ComboLBox";if((GetParent(focus)==sizeField||GetParent(focus)==opacityField)&&ctrl)return false;
    if(msg.wParam==VK_TAB||(cls==L"Button"&&(msg.wParam==VK_SPACE||msg.wParam==VK_RETURN)))keyboardFocusMode(hwnd,true);
    if(msg.wParam==VK_ESCAPE&&(dragging||strokePending)){endStroke(true);movingSelection=false;ReleaseCapture();return true;}
    if(ctrl){
        if(!typing&&adjusting()&&(tool==8||tool==9)){
            std::string action=msg.wParam=='A'?"all":msg.wParam=='C'?"copy":msg.wParam=='X'?"cut":msg.wParam=='V'?"paste":msg.wParam=='D'?"none":"";
            if(!action.empty()){selectionAction(action);return true;}
        }
        switch(msg.wParam){
            case 'N':if(!typing)userAction([this]{startPage.show(true);});return !typing;
            case 'O':openProject();return true;case 'S':saveProject(shift);return true;case 'Q':close();return true;case 'E':exportPng();return true;
            case 'Z':case 'Y':if(!typing){mutate(msg.wParam=='Y'||shift?"redo":"undo");return true;}break;
            case '0':fit();return true;case '1':if(panel==0){panX=panY=0;setZoom(1);}else fit();return true;
            case VK_OEM_7:if(!typing&&panel==0){grid=!grid;canvasView->redraw();syncButtons();return true;}break;
        }return false;
    }
    if(typing)return false;if(msg.wParam==VK_ESCAPE&&(selecting||selection.w)){selecting=false;clearSelection();ReleaseCapture();return true;}if(adjusting()&&selection.w&&msg.wParam==VK_DELETE){selectionAction("delete");return true;}if(panel==0&&tool==9&&focus==canvasView->hwnd&&selection.w&&msg.wParam>=VK_LEFT&&msg.wParam<=VK_DOWN&&canWrite()){selectionStart=selection;selectionX=selectionY=0;stroke.before=canvas.layers[canvas.active].image;movingSelection=true;int d=shift?10:1;updateSelection(msg.wParam==VK_LEFT?-d:msg.wParam==VK_RIGHT?d:0,msg.wParam==VK_UP?-d:msg.wParam==VK_DOWN?d:0);movingSelection=false;auto next=canvas.layers[canvas.active].image;canvas.layers[canvas.active].image=stroke.before;editPixels(std::move(next),currentRect());return true;}if(alt&&msg.wParam=='O'&&panel==0&&state["animation"]["steps"].size()>1){onion=!onion;frameDirty=true;canvasView->redraw();syncButtons();return true;}if(alt)return false;
    if(msg.wParam==VK_ESCAPE&&adjusting()){selectTool(HAND);return true;}
    if(panel==0&&canWrite()){
        std::string keys="BEGILUOHMV";auto found=keys.find(char(msg.wParam));if(found!=std::string::npos){selectTool(int(found));return true;}
    }
    if(panel==0&&msg.wParam=='T'){tiled=!tiled;fit();syncButtons();return true;}return false;
}
void App::close(){if(closing)return;if(selecting||dragging||strokePending||strokeCommitting){message=L"请先结束当前笔画，或按 Esc 取消后关闭。";statusBar->redraw();return;}if(fetching||mutationPending){message=L"正在保存或同步，完成后可关闭窗口。";statusBar->redraw();return;}saveBefore([this]{closing=true;KillTimer(hwnd,1);KillTimer(hwnd,2);DestroyWindow(hwnd);});}
LRESULT App::procedure(UINT msg,WPARAM wp,LPARAM lp){
    if(msg==WM_APP+71){userAction([this]{openSceneEditor(*this);});return 0;}
    if(msg==WM_APP+73){userAction([this]{openMinecraftPreview(*this);});return 0;}
    if(msg==WM_APP+75){userAction([this]{openMaterialEditor(*this);});return 0;}
    if(msg==WM_APP+74){userAction([this]{openMinecraftWorkbench(*this);});return 0;}
    if(msg==WM_APP+72){userAction([this]{openMinecraftEditor(*this);});return 0;}
    switch(msg){
    case WM_SIZE:if(statusBar&&wp!=SIZE_MINIMIZED)layout();return 0;
    case WM_GETMINMAXINFO:{auto info=reinterpret_cast<MINMAXINFO*>(lp);info->ptMinTrackSize={D(696),D(460)};return 0;}
    case WM_DPICHANGED:{placements.clear();dpi=HIWORD(wp);updateWindowIcons(hwnd);updateFont();if(loaded)syncLayers();auto r=reinterpret_cast<RECT*>(lp);SetWindowPos(hwnd,nullptr,r->left,r->top,r->right-r->left,r->bottom-r->top,SWP_NOZORDER|SWP_NOACTIVATE);layout();updateCanvasCursor();return 0;}
    case WM_ERASEBKGND:return 1; // paintChrome presents the background and captions together.
    case WM_PAINT:{PAINTSTRUCT ps;HDC dc=BeginPaint(hwnd,&ps);paintChrome(dc,ps.rcPaint);EndPaint(hwnd,&ps);return 0;}
    case WM_PRINTCLIENT:{RECT r;GetClientRect(hwnd,&r);paintChrome(HDC(wp),r);return 0;}
    case WM_CTLCOLOREDIT:case WM_CTLCOLORLISTBOX:case WM_CTLCOLORSTATIC:{static HBRUSH brush=CreateSolidBrush(RGB(32,36,44));SetTextColor(HDC(wp),RGB(230,233,241));SetBkColor(HDC(wp),RGB(32,36,44));return LRESULT(brush);}
    case WM_HSCROLL:{
        auto sender=HWND(lp);if(sender!=yawSlider&&sender!=pitchSlider)break;
        int val=int(SendMessageW(sender,TBM_GETPOS,0,0));if(sender==yawSlider)yaw=val;else pitch=val;
        syncCamera();requestRender();return 0;
    }
    case WM_DRAWITEM:bufferedItem(*reinterpret_cast<DRAWITEMSTRUCT*>(lp),[this](auto& item){drawButton(item);});return TRUE;
    case WM_COMMAND:command(LOWORD(wp),HIWORD(wp));return 0;
    case WM_TIMER:if(wp==1)poll();else if(wp==2)playback();return 0;
    case WM_RPC:rpc->complete(reinterpret_cast<RpcResult*>(lp));return 0;
    case WM_RENDER:renderComplete(reinterpret_cast<RenderReady*>(lp));return 0;
    case WM_FRONTEND:{std::unique_ptr<std::shared_ptr<FrontendRequest>> holder(reinterpret_cast<std::shared_ptr<FrontendRequest>*>(lp));auto request=*holder;if(request->cancelled)return 0;try{request->promise.set_value(uiCommand(request->payload));}catch(std::exception& e){request->promise.set_value(J::object({{"error",e.what()},{"code","INVALID_ARGUMENT"}}));}return 0;}
    case WM_CLOSE:close();return 0;
    case WM_DESTROY:gpu.reset();PostQuitMessage(0);return 0;
    }
    return DefWindowProcW(hwnd,msg,wp,lp);
}
LRESULT CALLBACK App::proc(HWND window,UINT msg,WPARAM wp,LPARAM lp){auto self=reinterpret_cast<App*>(GetWindowLongPtrW(window,GWLP_USERDATA));if(msg==WM_NCCREATE){self=static_cast<App*>(reinterpret_cast<CREATESTRUCTW*>(lp)->lpCreateParams);self->hwnd=window;SetWindowLongPtrW(window,GWLP_USERDATA,LONG_PTR(self));}if(!self)return DefWindowProcW(window,msg,wp,lp);try{return self->procedure(msg,wp,lp);}catch(std::exception& e){if(self->statusBar){self->message=wide(e.what());self->statusBar->redraw();}else OutputDebugStringW(wide(e.what()).c_str());return 0;}}
}
