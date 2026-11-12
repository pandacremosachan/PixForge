#include "app.hpp"

namespace pf {
namespace {
constexpr int columns=8;
constexpr std::array<const wchar_t*,10> toolNames={L"画笔",L"橡皮",L"填充",L"取色",L"直线",L"矩形",L"椭圆",L"平移",L"选区",L"移动"};
constexpr std::array<const char*,6> cameras={"iso","front","back","left","right","top"};
constexpr std::array<const wchar_t*,6> cameraNames={L"立体",L"正面",L"背面",L"左侧",L"右侧",L"顶面"};
constexpr std::array<std::pair<int,int>,6> angles={{{25,20},{0,0},{180,0},{-90,0},{90,0},{0,90}}};
constexpr std::array<const char*,3> overlayNames={"base","collision","selection"};
constexpr std::array<const wchar_t*,3> overlayLabels={L"基础形状",L"碰撞框",L"选中框"};
}

void App::createPanels(){
    for(int i=0;i<int(TOOLS.size());++i){
        HWND b=button(hwnd,"tool_"+TOOLS[i],toolNames[i],[this,i]{selectTool(i);},[this,i]{return tool==i;});
        buttons.at(GetDlgCtrlID(b)).icon=i;
    }
    sizeCombo=combo(hwnd,"brush_size",{});opacityCombo=combo(hwnd,"opacity",{});
    for(int i=1;i<=32;++i){auto label=std::to_wstring(i)+L" px";SendMessageW(sizeCombo,CB_ADDSTRING,0,LPARAM(label.c_str()));}
    for(int i=1;i<=100;++i){auto label=std::to_wstring(i)+L"%";SendMessageW(opacityCombo,CB_ADDSTRING,0,LPARAM(label.c_str()));}
    comboSet(sizeCombo,brushSize-1);comboSet(opacityCombo,99);
    button(hwnd,"mirror_x",L"镜像 X",[this]{mirrorX=!mirrorX;},[this]{return mirrorX;});
    button(hwnd,"mirror_y",L"镜像 Y",[this]{mirrorY=!mirrorY;},[this]{return mirrorY;});
    button(hwnd,"solid",L"实心形状",[this]{solid=!solid;},[this]{return solid;});
    button(hwnd,"native_size",L"原尺寸",[this]{panX=panY=0;setZoom(1);},[this]{return zoom==1;});
    button(hwnd,"grid",L"网格",[this]{grid=!grid;canvasView->redraw();},[this]{return grid;});
    button(hwnd,"tile",L"平铺",[this]{tiled=!tiled;fit();},[this]{return tiled;});
    button(hwnd,"onion",L"洋葱皮",[this]{onion=!onion;frameDirty=true;canvasView->redraw();},[this]{return onion;});
    button(hwnd,"uv_guides",L"UV 面域",[this]{uvGuides=!uvGuides;clearUvPin();},[this]{return uvGuides;});
    for(auto [key,index,label]:{std::tuple<const char*,int,const wchar_t*>{"colors",0,L"调色板"},{"navigation",1,L"原图"},{"uv",2,L"面域"}}){
        button(hwnd,std::string("inspect_")+key,label,[this,index]{inspectorTab=index;if(index==2)uvGuides=true;layout();details->redraw();canvasView->redraw();},[this,index]{return inspectorTab==index;});
    }
    button(hwnd,"color_chip",L"前景色",[this]{chooseInk();});
    colorHue=toHsv(ink)[0];
    colorField=surface(hwnd,27,[this](HDC dc,RECT r){paintColors(dc,r);});
    colorField->event=[this](UINT m,WPARAM w,LPARAM l){return colorEvent(m,w,l);};
    swatches=surface(hwnd,28,[this](HDC dc,RECT r){paintSwatches(dc,r);});
    swatches->event=[this](UINT m,WPARAM w,LPARAM l){return swatchEvent(m,w,l);};
    handles["color_field"]=colorField->hwnd;handles["palette"]=swatches->hwnd;
    SetWindowTextW(colorField->hwnd,L"色彩选择");SetWindowTextW(swatches->hwnd,L"调色板色块");
    layerList=CreateWindowExW(0,L"LISTBOX",L"",WS_CHILD|WS_VISIBLE|WS_TABSTOP|WS_VSCROLL|LBS_NOTIFY|LBS_OWNERDRAWFIXED|LBS_HASSTRINGS|LBS_NOINTEGRALHEIGHT,
        0,0,1,1,hwnd,reinterpret_cast<HMENU>(INT_PTR(nextButton++)),GetModuleHandleW(nullptr),nullptr);
    handles["layer_select"]=layerList;SendMessageW(layerList,WM_SETFONT,WPARAM(font),TRUE);
    auto addSwitch=[&](const char* name,const wchar_t* label,std::function<void()> change,std::function<bool()> checked){
        auto b=button(hwnd,name,label,std::move(change),std::move(checked));buttons.at(GetDlgCtrlID(b)).toggle=true;
    };
    addSwitch("layer_visible",L"可见",[this]{auto& l=canvas.layers[canvas.active];mutate("layer_visibility",J::object({{"name",l.name},{"visible",!l.visible}}));},[this]{return loaded&&canvas.layers[canvas.active].visible;});
    for(int i=0;i<int(cameras.size());++i){
        button(hwnd,"camera_"+std::string(cameras[i]),cameraNames[i],[this,i]{yaw=angles[i].first;pitch=angles[i].second;syncCamera();requestRender();},
               [this,i]{return std::abs(std::remainder(yaw-angles[i].first,360.))<.1&&std::abs(pitch-angles[i].second)<.1;});
    }
    auto slider=[this](const char* name,const wchar_t* label,int lo,int hi){
        HWND ctl=CreateWindowExW(0,TRACKBAR_CLASSW,label,WS_CHILD|WS_VISIBLE|WS_TABSTOP|TBS_HORZ|TBS_NOTICKS|TBS_TOOLTIPS,0,0,1,1,hwnd,
            reinterpret_cast<HMENU>(INT_PTR(nextButton++)),GetModuleHandleW(nullptr),nullptr);
        handles[name]=ctl;SendMessageW(ctl,TBM_SETRANGE,TRUE,MAKELPARAM(lo,hi));SendMessageW(ctl,TBM_SETPAGESIZE,0,15);return ctl;
    };
    yawSlider=slider("yaw",L"水平角",-180,180);pitchSlider=slider("pitch",L"俯仰角",-89,90);
    addSwitch("show_model",L"材质模型",[this]{showModel=!showModel;requestRender();},[this]{return showModel;});
    for(int i=0;i<3;++i)addSwitch(overlayNames[i],overlayLabels[i],[this,i]{overlays[i]=!overlays[i];requestRender();},[this,i]{return overlays[i];});
    for(auto [key,label,factor]:{std::tuple<const char*,const wchar_t*,double>{"zoom_out",L"缩小",.8},{"zoom_in",L"放大",1.25}})
        button(hwnd,key,label,[this,factor]{sceneZoom=pf::clamp(sceneZoom*factor,.1,8.);requestRender();statusBar->redraw();});
}

void App::syncCamera(){
    auto axis=[&](HWND slider,int value,int& shown,const wchar_t* label){
        if(value==shown)return;
        shown=value;
        if(SendMessageW(slider,TBM_GETPOS,0,0)!=value)SendMessageW(slider,TBM_SETPOS,TRUE,value);
        for(const auto& c:captions)if(c.label==label)InvalidateRect(hwnd,&c.area,FALSE);
    };
    axis(yawSlider,rounded(yaw),shownYaw,L"水平");axis(pitchSlider,rounded(pitch),shownPitch,L"俯仰");
    syncButtons();
}
void App::syncButtons(){
    for(auto& [id,b]:buttons)if(b.checked){
        bool checked=b.checked();
        if(checked!=b.wasChecked){b.wasChecked=checked;InvalidateRect(b.hwnd,nullptr,FALSE);}
    }
}

void App::refreshPalette(){
    std::vector<Pixel> colors;
    for(const auto& [key,rgba]:canvas.palette.obj())colors.push_back({uint8_t(rgba[0].integer()),uint8_t(rgba[1].integer()),uint8_t(rgba[2].integer()),uint8_t(rgba[3].integer())});
    if(colors.empty())for(auto hex:{"#171c2d","#30365b","#535b8c","#858ac1","#b9b6df","#e6dff2","#fff5e8","#c7e5df",
                                   "#31555c","#427e79","#6eb497","#b0d69c","#e6d18b","#d8a167","#ad6957","#743f52",
                                   "#723951","#a44a64","#d46a7c","#efa099","#efc7ad","#7894b6","#48638b","#2c3c61"})colors.push_back(color(hex));
    if(colors!=paletteColors){paletteColors=std::move(colors);paletteOffset=0;swatches->redraw();}
}

void App::paintColors(HDC dc,RECT r){
    int hueH=D(13),svH=r.bottom-hueH-D(5);if(svH<2||r.right<2)return;
    Gdiplus::Graphics g(dc);using C=Gdiplus::Color;auto p=hsvPixel(colorHue,1,1);
    Gdiplus::Rect box(0,0,r.right,svH);
    Gdiplus::LinearGradientBrush sat(box,C(255,255,255,255),C(255,p[0],p[1],p[2]),0.f);
    Gdiplus::LinearGradientBrush val(box,C(0,0,0,0),C(255,0,0,0),90.f);
    g.FillRectangle(&sat,box);g.FillRectangle(&val,box);
    for(int i=0;i<6;++i){int x=i*r.right/6,end=(i+1)*r.right/6;
        auto a=hsvPixel(i/6.,1,1),b=hsvPixel((i+1)/6.,1,1);Gdiplus::Rect strip(x,r.bottom-hueH,end-x,hueH);
        Gdiplus::LinearGradientBrush grad(strip,C(255,a[0],a[1],a[2]),C(255,b[0],b[1],b[2]),0.f);g.FillRectangle(&grad,strip);}
    auto hsv=toHsv(ink);int x=rounded(hsv[1]*(r.right-1)),y=rounded((1-hsv[2])*(svH-1)),k=D(4),hx=rounded(colorHue*(r.right-1));
    g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);Gdiplus::Pen dark(C(255,40,43,50),3.f),light(C(255,255,255,255),1.4f);
    for(auto pen:{&dark,&light}){g.DrawEllipse(pen,x-k,y-k,k*2,k*2);g.DrawRectangle(pen,hx-D(2),int(r.bottom)-hueH,D(4),hueH-1);}
}
LRESULT App::colorEvent(UINT m,WPARAM,LPARAM l){
    RECT r;GetClientRect(colorField->hwnd,&r);int svH=r.bottom-D(13)-D(5),x=GET_X_LPARAM(l),y=GET_Y_LPARAM(l);
    if(m==WM_LBUTTONDOWN){colorDrag=y<svH?1:2;SetCapture(colorField->hwnd);SetFocus(colorField->hwnd);}
    if(colorDrag&&(m==WM_MOUSEMOVE||m==WM_LBUTTONDOWN)){
        auto hsv=toHsv(ink);double fx=pf::clamp(x/double(pf::max(1,r.right-1)),0.,1.);
        if(colorDrag==2)colorHue=fx;else{hsv[1]=fx;hsv[2]=1-pf::clamp(y/double(pf::max(1,svH-1)),0.,1.);}
        auto c=hsvPixel(colorHue,hsv[1],hsv[2]);c[3]=ink[3];setColor(c);return 0;
    }
    if(m==WM_LBUTTONUP){colorDrag=0;ReleaseCapture();return 0;}if(m==WM_CAPTURECHANGED){colorDrag=0;return 0;}return UNHANDLED;
}

void App::paintSwatches(HDC dc,RECT r){
    fill(dc,r,RGB(35,38,46));int cell=D(21),rows=pf::max(1,r.bottom/cell);
    paletteOffset=pf::clamp(paletteOffset,0,pf::max(0,(int(paletteColors.size())+columns-1)/columns-rows));
    for(int i=paletteOffset*columns;i<pf::min(int(paletteColors.size()),(paletteOffset+rows)*columns);++i){
        int col=i%columns,y=(i/columns-paletteOffset)*cell;
        RECT tile{col*r.right/columns+D(1),y+D(1),(col+1)*r.right/columns-D(2),y+cell-D(2)};
        auto c=paletteColors[i];if(c==ink){fill(dc,tile,RGB(240,236,255));InflateRect(&tile,-D(2),-D(2));}
        if(c[3]==255)fill(dc,tile,rgb(c));else{Image one(2,2,c);imageToDC(dc,one,tile);}
    }
}
LRESULT App::swatchEvent(UINT m,WPARAM w,LPARAM l){
    RECT r;GetClientRect(swatches->hwnd,&r);int cell=D(21);
    if(m==WM_MOUSEWHEEL){int rows=pf::max(1,r.bottom/cell);paletteOffset=pf::clamp(paletteOffset-GET_WHEEL_DELTA_WPARAM(w)/WHEEL_DELTA,0,pf::max(0,(int(paletteColors.size())+columns-1)/columns-rows));swatches->redraw();return 0;}
    if(m==WM_LBUTTONDOWN){int row=GET_Y_LPARAM(l)/cell,col=GET_X_LPARAM(l)*columns/pf::max(1,r.right);
        int i=(row+paletteOffset)*columns+col;if(row<r.bottom/cell&&i>=0&&i<int(paletteColors.size()))setColor(paletteColors[i]);return 0;}
    return UNHANDLED;
}
void App::syncLayers(){
    auto f=currentRect();int k=D(23);
    double scale=pf::min(k/double(f.w),k/double(f.h));
    int tw=pf::max(1,rounded(f.w*scale)),th=pf::max(1,rounded(f.h*scale));
    std::vector<LayerRow> rows;rows.reserve(canvas.layers.size());
    for(auto it=canvas.layers.rbegin();it!=canvas.layers.rend();++it){
        Image thumb(k,k);
        for(int y=0;y<th;++y)for(int x=0;x<tw;++x)
            thumb.set((k-tw)/2+x,(k-th)/2+y,it->image.get(f.x+x*f.w/tw,f.y+y*f.h/th));
        rows.push_back({wide(it->name),it->visible,std::move(thumb)});
    }
    int active=int(rows.size())-1-canvas.active;
    bool sameNames=std::equal(rows.begin(),rows.end(),layerRows.begin(),layerRows.end(),
                              [](const auto& a,const auto& b){return a.name==b.name;});
    rows.swap(layerRows); // WM_DRAWITEM can run synchronously during a selection change.
    if(!sameNames){
        int top=int(SendMessageW(layerList,LB_GETTOPINDEX,0,0));
        replaceList(layerList,[&]{
            SendMessageW(layerList,LB_RESETCONTENT,0,0);
            for(const auto& row:layerRows)SendMessageW(layerList,LB_ADDSTRING,0,LPARAM(row.name.c_str()));
            SendMessageW(layerList,LB_SETTOPINDEX,pf::clamp(top,0,int(layerRows.size())-1),0);
            SendMessageW(layerList,LB_SETCURSEL,active,0);
        });
        return;
    }
    if(SendMessageW(layerList,LB_GETCURSEL,0,0)!=active)SendMessageW(layerList,LB_SETCURSEL,active,0);
    for(size_t i=0;i<rows.size();++i)if(rows[i].visible!=layerRows[i].visible||rows[i].thumb!=layerRows[i].thumb){
        RECT area;if(SendMessageW(layerList,LB_GETITEMRECT,i,LPARAM(&area))!=LB_ERR)InvalidateRect(layerList,&area,FALSE);
    }
}
void App::drawLayer(const DRAWITEMSTRUCT& item){
    if(item.itemID>=layerRows.size()){fill(item.hDC,item.rcItem,RGB(32,36,44));return;}
    const auto& row=layerRows[item.itemID];auto r=item.rcItem;bool active=item.itemState&ODS_SELECTED;
    fill(item.hDC,r,active?RGB(64,62,83):RGB(39,43,52));
    int k=pf::min(D(23),r.bottom-r.top-D(4)),y=(r.top+r.bottom-k)/2;
    imageToDC(item.hDC,row.thumb,{D(5),y,D(5)+k,y+k});
    r.left+=k+D(13);r.right-=D(8);SelectObject(item.hDC,font);
    text(item.hDC,row.name+(row.visible?L"":L"  · 隐藏"),r,row.visible?RGB(233,235,245):RGB(145,148,162),
         DT_LEFT|DT_VCENTER|DT_SINGLELINE|DT_END_ELLIPSIS|DT_NOPREFIX);
}
}
