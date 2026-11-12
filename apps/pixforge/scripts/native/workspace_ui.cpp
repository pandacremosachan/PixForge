#include "app.hpp"

namespace pf {
namespace {
const COLORREF chrome=RGB(35,38,46), surfaceColor=RGB(44,48,58), border=RGB(60,65,77);
const COLORREF foreground=RGB(234,236,243), muted=RGB(166,173,188), accent=RGB(174,166,248);
std::wstring filename(const J& state) {
    auto path=state["project_path"].str(state["source_path"].str());
    return path.empty()?L"未命名材质":fs::path(wide(path)).filename().wstring();
}
}

void App::create(){
    documentBar=surface(hwnd,10,[this](HDC dc,RECT r){
        fill(dc,r,chrome);
        auto name=loaded?filename(state):L"PixForge";
        if(state["dirty"].boolean())name+=L"  •";
        text(dc,name,r,foreground,DT_LEFT|DT_VCENTER|DT_SINGLELINE|DT_END_ELLIPSIS|DT_NOPREFIX);
    });
    button(hwnd,"file",L"文件 ▾",[this]{fileMenu();});
    button(hwnd,"pixels",L"材质",[this]{switchPanel(0);},[this]{return panel==0;});
    button(hwnd,"shapes",L"模型",[this]{switchPanel(1);},[this]{return panel==1;});
    button(hwnd,"fit",L"适应",[this]{fit();});
    button(hwnd,"side",L"侧栏",[this]{inspectorVisible=!inspectorVisible;layout();},[this]{return inspectorVisible;});
    button(hwnd,"transport",L"播放条",[this]{timelineVisible=!timelineVisible;layout();},[this]{return showTransport();});

    canvasView=surface(hwnd,15,[this](HDC dc,RECT r){paintCanvas(dc,r);});
    canvasView->event=[this](UINT m,WPARAM w,LPARAM l){return canvasEvent(m,w,l);};
    sceneView=surface(hwnd,16,[this](HDC dc,RECT r){paintScene(dc,r);});
    sceneView->event=[this](UINT m,WPARAM w,LPARAM l)->LRESULT{
        int x=GET_X_LPARAM(l),y=GET_Y_LPARAM(l);
        if(m==WM_LBUTTONDOWN){SetFocus(sceneView->hwnd);lastMouseX=x;lastMouseY=y;panning=true;SetCapture(sceneView->hwnd);return 0;}
        if(m==WM_MOUSEMOVE&&panning){
            yaw=std::remainder(yaw-(x-lastMouseX)*.6,360.);pitch=pf::clamp(pitch+(y-lastMouseY)*.6,-89.,90.);
            lastMouseX=x;lastMouseY=y;syncCamera();requestRender();return 0;
        }
        if(m==WM_LBUTTONUP&&panning){panning=false;ReleaseCapture();renderKey.clear();requestRender();return 0;}
        if(m==WM_CAPTURECHANGED){panning=false;return 0;}
        if(m==WM_MOUSEWHEEL){sceneZoom=pf::clamp(sceneZoom*std::pow(1.25,GET_WHEEL_DELTA_WPARAM(w)/double(WHEEL_DELTA)),.1,8.);requestRender();statusBar->redraw();return 0;}
        return UNHANDLED;
    };
    gpu=std::make_unique<GpuScene>(sceneView->hwnd);
    if(gpu->available)sceneView->directPaint=[this]{RECT r;GetClientRect(sceneView->hwnd,&r);return gpu&&gpu->draw(r.right,r.bottom);};

    createPanels();
    button(hwnd,"undo",L"撤销",[this]{mutate("undo");});button(hwnd,"redo",L"重做",[this]{mutate("redo");});

    details=surface(hwnd,26,[this](HDC dc,RECT r){paintDetails(dc,r);});
    details->event=[this](UINT m,WPARAM w,LPARAM l)->LRESULT{
        if(inspectorTab!=2)return UNHANDLED;
        if(m==WM_MOUSEWHEEL){RECT r;GetClientRect(details->hwnd,&r);uvScroll=pf::clamp(uvScroll-GET_WHEEL_DELTA_WPARAM(w)/WHEEL_DELTA*D(60),0,pf::max(0,uvContentHeight-r.bottom+D(136)));details->redraw();return 0;}
        if(m==WM_LBUTTONDOWN){int y=GET_Y_LPARAM(l);
            if(y>=D(57)&&y<D(81)){clearUvPin();return 0;}
            if(uvHits.empty()&&uvX<0&&y>=D(140)){int i=(y-D(140)+uvScroll)/D(79);if(i<int(modelUv["regions"].size())){uvHits={i};uvRegion=modelUv["regions"][i]["id"].str();uvPinned=true;uvScroll=0;canvasView->redraw();details->redraw();}}
            return 0;
        }
        return UNHANDLED;
    };
    timeline=surface(hwnd,22,[this](HDC dc,RECT r){paintTimeline(dc,r);});
    timeline->event=[this](UINT m,WPARAM,LPARAM l)->LRESULT{
        if(m==WM_LBUTTONDOWN||(m==WM_MOUSEMOVE&&sceneScrubbing)){
            RECT r;GetClientRect(timeline->hwnd,&r);
            double fraction=pf::clamp((GET_X_LPARAM(l)-D(10))/double(pf::max(1,r.right-D(110))),0.,1.);
            if(m==WM_LBUTTONDOWN){sceneScrubbing=true;SetCapture(timeline->hwnd);}
            if(state["scene_animation"].null())seek(rounded(fraction*(state["animation"]["steps"].size()-1)));
            else seekTime(fraction*sceneDuration());
            return 0;
        }
        if(m==WM_LBUTTONUP&&sceneScrubbing){sceneScrubbing=false;ReleaseCapture();return 0;}
        if(m==WM_CAPTURECHANGED){sceneScrubbing=false;return 0;}return UNHANDLED;
    };
    button(hwnd,"previous",L"上一帧",[this]{seek(step-1);});
    button(hwnd,"play",L"播放",[this]{togglePlayback();});
    button(hwnd,"next",L"下一帧",[this]{seek(step+1);});
    sceneStateCombo=combo(hwnd,"state_select",{});
    statusBar=surface(hwnd,23,[this](HDC dc,RECT r){paintStatus(dc,r);});
    tooltips();
}

void App::placeControl(HWND control,int x,int y,int w,int h,bool visible){
    placements[control].place(control,x,y,w,h,visible);
}

void App::layout(){
    RECT client;GetClientRect(hwnd,&client);int w=client.right,h=client.bottom;
    bool pixels=panel==0,model=panel==1,hasUv=!modelUv["regions"].empty(),frames=state["animation"]["steps"].size()>1;
    bool tabs=model||!state["shapes"]["model"].null(),side=inspectorVisible,colors=pixels&&side&&inspectorTab==0;
    const int head=D(46),top=head+(pixels?D(39):0),footer=D(27),bottom=h-footer-(showTransport()?D(40):0),body=bottom-top;
    bool shortPanel=body<D(415);
    int rail=pixels?(w<D(860)?D(128):D(150)):0;
    int right=side?pf::clamp(w/5,D(188),D(278)):0,rx=w-right,gap=D(5);
    std::vector<Caption> nextCaptions;
    auto label=[&](std::wstring title,int x,int y,int width,int height,bool strong=false){nextCaptions.push_back({{x,y,x+width,y+height},std::move(title),strong});};
    auto box=[&](const std::string& key,int x,int y,int width,int height,bool visible){placeControl(handles.at(key),x,y,width,height,visible);};
    auto tab=[&](const char* key,int x,int y,int ww,bool show=true){box(key,x,y,D(ww),D(28),show);};
    auto row=[&](const std::vector<std::string>& keys,int x,int y,int width,int height,bool visible){
        for(int i=0;i<int(keys.size());++i){int a=i*(width+gap)/int(keys.size()),b=(i+1)*(width+gap)/int(keys.size());box(keys[i],x+a,y,b-a-gap,height,visible);}
    };

    int hx=w-D(72);tab("side",hx,D(9),60);hx-=D(100);tab("undo",hx,D(9),46);tab("redo",hx+D(48),D(9),46);
    if(animated())hx-=D(66);tab("transport",hx,D(9),60,animated());
    int tx=pf::min(w/2-D(65),hx-D(138));
    tab("file",D(12),D(9),62);tab("pixels",tx,D(9),62,tabs);tab("shapes",tx+D(64),D(9),62,tabs);
    placeControl(documentBar->hwnd,D(87),D(7),(tabs?tx:hx)-D(96),D(32));

    int x=D(12),y=head+D(4);
    if(pixels)label(L"画板",x,y,D(44),D(29),true);x+=D(48);
    if(pixels)tab("fit",x,y,52);x+=D(56);
    tab("native_size",x,y,60,pixels);x+=D(74);
    tab("grid",x,y,53,pixels);x+=D(57);tab("tile",x,y,53,pixels);x+=D(57);
    tab("uv_guides",x,y,73,pixels&&hasUv);if(hasUv)x+=D(77);
    tab("onion",x,y,64,pixels&&frames);

    int ix=D(9),iw=rail-2*ix; y=top+D(5);
    if(pixels)label(L"工具",ix,y,iw,D(22),true);y+=D(25);
    int toolH=pf::clamp((body-D(137))/5-D(3),D(22),D(43));
    for(auto pair:{std::pair<int,int>{7,0},{1,3},{2,4},{5,6},{8,9}}){
        row({"tool_"+TOOLS[pair.first],"tool_"+TOOLS[pair.second]},ix,y,iw,toolH,pixels);y+=toolH+D(3);
    }
    y+=shortPanel?D(3):D(14);int fieldH=shortPanel?D(23):D(30),fieldX=ix+D(49);
    if(pixels)label(L"笔宽",ix,y,D(48),fieldH);placeControl(sizeCombo,fieldX,y,rail-ix-fieldX,D(180),pixels);y+=fieldH+D(2);
    if(pixels)label(L"不透明度",ix,y,D(52),fieldH);placeControl(opacityCombo,fieldX+D(5),y,rail-ix-fieldX-D(5),D(180),pixels);y+=fieldH+D(3);
    int optionH=shortPanel?D(23):D(29);
    row({"mirror_x","mirror_y"},ix,y,iw,optionH,pixels);y+=optionH+D(3);
    box("solid",ix,y,iw,optionH,pixels);

    placeControl(canvasView->hwnd,rail,top,w-rail-right,body,pixels);
    placeControl(sceneView->hwnd,0,top,w-right,body,model);

    int sx=rx+D(12),sw=right-D(24);y=top+D(6);
    row(hasUv?std::vector<std::string>{"inspect_colors","inspect_navigation","inspect_uv"}:std::vector<std::string>{"inspect_colors","inspect_navigation"},
        sx,y,sw,D(27),pixels&&side);
    if(!hasUv)placeControl(handles.at("inspect_uv"),0,0,0,0,false);
    int tabBottom=y+D(33),sh=pf::clamp(body/5,D(42),D(146));
    placeControl(colorField->hwnd,sx,tabBottom,sw,sh,colors);
    y=tabBottom+sh+D(4);box("color_chip",sx,y,sw,D(25),colors);y+=D(27);
    if(colors)label((canvas.palette.empty()?L"常用色":L"工程色")+std::wstring(L"  ·  ")+std::to_wstring(paletteColors.size()),sx,y,sw,D(23),true);
    y+=D(23);int swatchRows=pf::clamp((bottom-D(72)-y)/D(21),1,pf::max(1,(int(paletteColors.size())+7)/8));
    placeControl(swatches->hwnd,sx,y,sw,swatchRows*D(21),colors);y+=swatchRows*D(21)+D(7);
    int ly=colors?y:pf::max(tabBottom+D(60),bottom-pf::clamp(body/3,D(72),D(188)));
    placeControl(details->hwnd,sx,tabBottom,sw,ly-tabBottom-D(4),pixels&&side&&!colors);
    if(pixels&&side)label(L"图层",sx,ly,sw-D(75),D(25),true);
    box("layer_visible",sx+sw-D(73),ly,D(73),D(25),pixels&&side);ly+=D(28);
    int rowHeight=shortPanel?D(25):D(32);
    if(SendMessageW(layerList,LB_GETITEMHEIGHT,0,0)!=rowHeight)SendMessageW(layerList,LB_SETITEMHEIGHT,0,rowHeight);
    placeControl(layerList,sx,ly,sw,bottom-ly-D(7),pixels&&side);

    // The model has its own permanent display and camera controls.
    bool show=model&&side;int lineH=shortPanel?D(24):D(31);y=top+(shortPanel?D(5):D(12));
    if(show)label(L"模型显示",sx,y,sw,D(23),true);y+=D(25);
    for(auto key:{"show_model","base","collision","selection"}){box(key,sx,y,sw,lineH,show);y+=lineH+D(1);}
    y+=shortPanel?D(3):D(14);if(show)label(L"视角",sx,y,sw,D(23),true);y+=D(24);
    row({"camera_iso","camera_front","camera_back"},sx,y,sw,lineH,show);y+=lineH+D(4);
    row({"camera_left","camera_right","camera_top"},sx,y,sw,lineH,show);y+=lineH+D(6);
    for(auto [key,name]:{std::pair<const char*,const wchar_t*>{"yaw",L"水平"},{"pitch",L"俯仰"}}){
        if(show)label(name,sx,y,D(82),D(24));box(key,sx+D(78),y,sw-D(78),D(24),show);y+=D(26);
    }
    y+=shortPanel?D(1):D(13);
    box("zoom_out",sx,y,(sw-2*gap)/3,lineH,show);box("zoom_in",sx+2*(sw+gap)/3,y,(sw-2*gap)/3,lineH,show);
    if(model){if(side)box("fit",sx+(sw+gap)/3,y,(sw-2*gap)/3,lineH,true);else tab("fit",hx-D(59),D(9),52);}
    EnableWindow(handles.at("solid"),tool==5||tool==6);
    bool widthTool=tool==0||tool==1||tool==4||tool==5||tool==6;
    auto enable=[](HWND control,bool value){if((IsWindowEnabled(control)!=FALSE)!=value)EnableWindow(control,value);};
    enable(sizeCombo,widthTool||tool==HAND);enable(opacityCombo,tool!=3&&tool!=8&&tool!=9);

    int transportY=bottom+D(6);x=D(12);
    tab("play",x,transportY,58,showTransport());x+=D(65);
    tab("previous",x,transportY,55,showTransport()&&frames);tab("next",x+D(58),transportY,55,showTransport()&&frames);if(frames)x+=D(120);
    placeControl(sceneStateCombo,x,transportY,D(134),D(200),showTransport()&&scenePlayer!=nullptr);if(scenePlayer)x+=D(142);
    placeControl(timeline->hwnd,x,bottom,w-x-D(12),D(40),showTransport());
    placeControl(statusBar->hwnd,0,h-footer,w,footer);
    if(loaded&&pixels&&pixelAutoFit)fit();
    if(nextCaptions!=captions){captions=std::move(nextCaptions);InvalidateRect(hwnd,nullptr,FALSE);}
    if(model)syncCamera();else syncButtons();
    documentBar->redraw();statusBar->redraw();requestRender();
}

void App::paintChrome(HDC target,RECT r){
    bufferedPaint(target,r,[&](HDC dc){
    fill(dc,r,chrome);
    for(const auto& c:captions){auto title=c.label;
        if(title==L"水平"||title==L"俯仰")title+=L"  "+std::to_wstring(rounded(title==L"水平"?yaw:pitch))+L"°";
        SelectObject(dc,c.heading?boldFont:font);text(dc,title,c.area,c.heading?foreground:muted);
    }
    RECT client;GetClientRect(hwnd,&client);line(dc,0,D(45),client.right,D(45),border);
    });
}
void App::switchPanel(int value){
    panel=value;message.clear();layout();
    SetFocus(panel==0?canvasView->hwnd:sceneView->hwnd);
}
void App::selectTool(int index){
    if(dragging||strokePending||strokeCommitting){pendingTool=index;return;}
    if(selecting){selecting=false;ReleaseCapture();}
    if(index==HAND)clearSelection();
    tool=index;panel=0;message.clear();layout();SetFocus(canvasView->hwnd);updateCanvasCursor();
}
void App::chooseInk(){
    CHOOSECOLORW cc{sizeof cc};static COLORREF custom[16]{};
    cc.hwndOwner=hwnd;cc.rgbResult=rgb(ink);cc.lpCustColors=custom;cc.Flags=CC_FULLOPEN|CC_RGBINIT;
    if(ChooseColorW(&cc))setColor({GetRValue(cc.rgbResult),GetGValue(cc.rgbResult),GetBValue(cc.rgbResult),255});
}

void App::paintStatus(HDC dc,RECT r){
    fill(dc,r,chrome);line(dc,0,0,r.right,0,border);
    if(!loaded){text(dc,message,{D(16),0,r.right,r.bottom},muted);return;}
    auto f=currentRect();auto scale=panel==0?zoom:sceneZoom;
    text(dc,std::to_wstring(f.w)+L" × "+std::to_wstring(f.h)+L" px",{D(16),0,D(150),r.bottom},muted);
    text(dc,message,{D(152),0,r.right-D(85),r.bottom},foreground,DT_LEFT|DT_VCENTER|DT_SINGLELINE|DT_END_ELLIPSIS|DT_NOPREFIX);
    text(dc,std::to_wstring(rounded(scale*100))+L"%",{r.right-D(84),0,r.right-D(16),r.bottom},muted,DT_RIGHT|DT_VCENTER|DT_SINGLELINE);
}
void App::paintDetails(HDC dc,RECT r){
    if(inspectorTab==2){paintUvInspector(dc,r);return;}
    fill(dc,r,surfaceColor);if(!loaded)return;
    text(dc,L"原尺寸",{D(8),D(4),r.right,D(30)},muted);
    frameCacheUpdate();int w=frameImage.w,h=frameImage.h;
    int x=(r.right-w)/2,y=(r.bottom+D(30)-h)/2;
    imageToDC(dc,frameImage,{x,y,x+w,y+h});
}
void App::paintTimeline(HDC dc,RECT r){
    fill(dc,r,chrome);bool scene=!state["scene_animation"].null();int total=int(state["animation"]["steps"].size());
    double t=scene?sceneClock()/pf::max(1.,sceneDuration()):step/double(pf::max(1,total-1));
    int left=D(10),right=r.right-D(100),y=r.bottom/2,thumb=left+rounded((right-left)*pf::clamp(t,0.,1.));
    fill(dc,{left,y-D(2),right,y+D(2)},border);fill(dc,{left,y-D(2),thumb,y+D(2)},accent);
    fill(dc,{thumb-D(3),y-D(6),thumb+D(3),y+D(6)},foreground);
    wchar_t label[48];if(scene)std::swprintf(label,48,L"%.1f / %.1f s",sceneClock()/1000.,sceneDuration()/1000.);
    else std::swprintf(label,48,L"%d / %d 帧",step+1,total);
    text(dc,label,{right+D(6),0,r.right,r.bottom},muted,DT_RIGHT|DT_VCENTER|DT_SINGLELINE);
}
void App::syncPlayback(){
    if(!timeline)return;
    auto& b=buttons.at(GetDlgCtrlID(handles.at("play")));
    auto title=playing?L"暂停":L"播放";if(b.title!=title){b.title=title;SetWindowTextW(b.hwnd,title);InvalidateRect(b.hwnd,nullptr,FALSE);}
    EnableWindow(handles.at("previous"),step>0);EnableWindow(handles.at("next"),step+1<int(state["animation"]["steps"].size()));
    if(showTransport())timeline->redraw();
}
void App::togglePlayback(){
    playing=!playing;playStart=milliseconds();
    if(playing&&scenePlayer&&scenePlayer->finished){scenePlayer->seek(0);elapsed=sceneClock();programTextureStep();}
    else if(state["scene_animation"].null()){
        if(playing&&step+1==int(state["animation"]["steps"].size()))seek(0,false);
        elapsed=0;for(int i=0;i<step;++i)elapsed+=state["animation"]["steps"][i]["duration_ms"].number();
    }else if(playing&&!scenePlayer&&!state["scene_animation"]["loop"].boolean()&&elapsed>=sceneDuration())seekTime(0,false);
    syncPlayback();
}

void App::fileMenu(){
    HMENU popup=CreatePopupMenu();std::vector<std::function<void()>> items;
    auto add=[&](const wchar_t* label,std::function<void()> fn){items.push_back(std::move(fn));AppendMenuW(popup,MF_STRING,items.size(),label);};
    auto separator=[&]{AppendMenuW(popup,MF_SEPARATOR,0,nullptr);};
        add(L"打开…\tCtrl+O",[this]{openProject();});add(L"保存工程\tCtrl+S",[this]{saveProject();});
        add(L"工程另存为…\tCtrl+Shift+S",[this]{saveProject(true);});
        separator();add(L"导出 PNG…\tCtrl+E",[this]{exportPng();});
    RECT anchor;GetWindowRect(handles.at("file"),&anchor);
    int selected=TrackPopupMenu(popup,TPM_RETURNCMD|TPM_LEFTALIGN,anchor.left,anchor.bottom,0,hwnd,nullptr);
    DestroyMenu(popup);if(selected)items.at(selected-1)();
}
void App::command(int id,int notification){
    if(loading)return;auto b=buttons.find(id);
    if(b!=buttons.end()&&notification==BN_CLICKED){userAction([this,click=b->second.click]{click();syncButtons();});return;}
    HWND h=GetDlgItem(hwnd,id);
    if(h==layerList&&notification==LBN_SELCHANGE){
        int row=int(SendMessageW(layerList,LB_GETCURSEL,0,0));auto name=canvas.layers[canvas.layers.size()-1-row].name;
        userAction([this,name]{mutate("layer_select",J::object({{"name",name}}));});return;
    }
    if(notification!=CBN_SELCHANGE)return;int i=comboIndex(h);
    if(h==sizeCombo){brushSize=i+1;SetFocus(canvasView->hwnd);}
    else if(h==opacityCombo){brushOpacity=i+1;SetFocus(canvasView->hwnd);}
    else if(h==sceneStateCombo&&scenePlayer){
        auto& states=state["scene_animation"]["states"];if(i==int(states.size()))stateAction("demo");else if(i>=0)stateAction("preview",states[i]["id"].str());
    }
}
void App::drawButton(const DRAWITEMSTRUCT& item){
    if(item.CtlType==ODT_LISTBOX){drawLayer(item);return;}
    auto b=buttons.find(int(item.CtlID));if(b==buttons.end())return;
    auto& button=b->second;bool checked=button.checked&&button.checked(),disabled=(item.itemState&ODS_DISABLED)!=0;
    auto dc=item.hDC;auto r=item.rcItem;fill(dc,r,chrome);
    bool swatch=button.hwnd==handles.at("color_chip");
    COLORREF bg=checked?RGB(69,65,96):surfaceColor;
    if(item.itemState&ODS_SELECTED)bg=RGB(77,81,96);
    if(button.toggle){
        drawViewSwitch(dc,r,button.title,checked,!disabled,dpi,chrome);
        drawButtonFocus(dc,item.rcItem,button.hwnd,item.itemState);return;
    }
    auto brush=CreateSolidBrush(bg);auto oldBrush=SelectObject(dc,brush);
    auto oldPen=SelectObject(dc,GetStockObject(NULL_PEN));RoundRect(dc,r.left,r.top,r.right,r.bottom,D(9),D(9));
    SelectObject(dc,oldPen);SelectObject(dc,oldBrush);DeleteObject(brush);
    if(swatch){RECT chip{D(7),D(5),D(37),r.bottom-D(5)};fill(dc,chip,rgb(ink));r.left=D(47);SelectObject(dc,font);text(dc,L"前景色  "+wide(hexColor(ink)),r,foreground);}
    else if(button.icon>=0){int k=pf::min(D(18),r.bottom-D(4));COLORREF c=checked?accent:foreground;
        toolIcon(dc,button.icon,D(5),(r.bottom-k)/2,k,c);r.left=k+D(7);SelectObject(dc,font);text(dc,button.title,r,c);}
    else{SelectObject(dc,font);text(dc,button.title,r,disabled?RGB(112,118,131):checked?accent:foreground,DT_CENTER|DT_VCENTER|DT_SINGLELINE|DT_NOPREFIX);}
    drawButtonFocus(dc,item.rcItem,button.hwnd,item.itemState);
}
void App::tooltips(){
    tooltipWindow=CreateWindowExW(WS_EX_TOPMOST,TOOLTIPS_CLASSW,nullptr,WS_POPUP|TTS_ALWAYSTIP|TTS_NOPREFIX,CW_USEDEFAULT,CW_USEDEFAULT,CW_USEDEFAULT,CW_USEDEFAULT,hwnd,nullptr,GetModuleHandleW(nullptr),nullptr);
    for(auto [key,hint]:{std::pair<const char*,const wchar_t*>{"side",L"显示或收起侧栏"},{"fit",L"适应窗口  Ctrl+0"},{"grid",L"像素网格"},{"tile",L"3 × 3 平铺"},{"solid",L"填充矩形或椭圆内部"},
        {"tool_hand",L"平移 H · 滚轮缩放"},{"tool_pen",L"画笔 B · 右键取色"},{"tool_eraser",L"橡皮 E"},{"tool_fill",L"填充相邻同色像素 G"},{"tool_picker",L"取色 I"},{"tool_line",L"直线 L"},{"tool_rect",L"矩形 U"},{"tool_ellipse",L"椭圆 O"},{"tool_select",L"选区 M"},{"tool_move",L"移动选区 V"},
        {"brush_size",L"画笔宽度"},{"color_chip",L"选择前景色"},{"color_field",L"上方调整饱和度和明度，下方选色相"},{"palette",L"点击色块取色，滚轮浏览工程色"},{"layer_select",L"当前绘制图层"},
        {"undo",L"撤销  Ctrl+Z"},{"redo",L"重做  Ctrl+Y"},{"state_select",L"选择播放状态"}})tooltipText[handles.at(key)]=hint;
    for(auto& [control,label]:tooltipText){TOOLINFOW info{TTTOOLINFOW_V2_SIZE};info.uFlags=TTF_IDISHWND|TTF_SUBCLASS;info.hwnd=GetParent(control);info.uId=UINT_PTR(control);info.lpszText=label.data();SendMessageW(tooltipWindow,TTM_ADDTOOLW,0,LPARAM(&info));}
}
}
