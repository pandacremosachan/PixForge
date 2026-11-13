#include "app.hpp"

namespace pf {
namespace {
constexpr COLORREF paper=RGB(29,32,40),pane=RGB(40,44,54),card=RGB(48,52,64),
    ink=RGB(240,241,246),muted=RGB(173,179,195),rule=RGB(64,69,82),lilac=RGB(191,182,255);
constexpr std::array<const wchar_t*,3> names={L"方块",L"物品贴图",L"角色建模"};
constexpr std::array<const wchar_t*,3> captions={L"在同一工程中绘制贴图、搭建方块部件。",L"为物品栏图标和手持物绘制透明贴图。",L"从玩家骨架开始，编辑角色外形、姿势和动作。"};
constexpr std::array<const wchar_t*,3> verbs={L"创建方块",L"创建物品贴图",L"创建角色"};
constexpr int sizes[]={16,32,64,128};
void roundBox(HDC dc,RECT r,int radius,COLORREF bg,COLORREF edge){
    auto b=CreateSolidBrush(bg);auto p=CreatePen(PS_SOLID,1,edge);
    auto oldB=SelectObject(dc,b),oldP=SelectObject(dc,p);
    RoundRect(dc,r.left,r.top,r.right,r.bottom,radius,radius);
    SelectObject(dc,oldB);SelectObject(dc,oldP);DeleteObject(b);DeleteObject(p);
}
HFONT pageFont(int dpi,int height,int weight){
    return CreateFontW(-MulDiv(height,dpi,96),0,0,0,weight,FALSE,FALSE,FALSE,DEFAULT_CHARSET,
        OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Microsoft YaHei UI");
}
void diagram(HDC dc,int x,int y,int side,int type){
    // Block, item and character share a 16-unit icon grid.
    auto point=[&](int u,int v){return POINT{x+MulDiv(u,side,16),y+MulDiv(v,side,16)};};
    auto poly=[&](std::initializer_list<POINT> pts,COLORREF color){
        auto b=CreateSolidBrush(color);auto old=SelectObject(dc,b),p=SelectObject(dc,GetStockObject(NULL_PEN));
        Polygon(dc,pts.begin(),int(pts.size()));SelectObject(dc,p);SelectObject(dc,old);DeleteObject(b);
    };
    const COLORREF top=RGB(188,181,248),left=RGB(125,116,192),right=RGB(150,140,213);
    auto tile=[&](int a,int b,int c,int d,COLORREF col){auto p=point(a,b),q=point(c,d);fill(dc,{p.x,p.y,q.x,q.y},col);};
    if(type==1){
        tile(5,2,11,4,top);tile(3,4,13,7,top);tile(2,6,14,9,right);
        tile(4,9,12,11,right);tile(6,11,10,13,left);tile(7,13,9,15,left);
        tile(5,4,7,7,RGB(225,223,255));return;
    }
    if(type==0){
        poly({point(8,1),point(15,5),point(8,9),point(1,5)},top);
        poly({point(1,5),point(8,9),point(8,16),point(1,12)},left);
        poly({point(8,9),point(15,5),point(15,12),point(8,16)},right);return;
    }
    tile(5,0,11,5,top);tile(5,6,11,11,right);
    tile(2,6,4,11,left);tile(12,6,14,11,left);
    tile(5,11,7,16,top);tile(9,11,11,16,top);
}
}

StartPage::~StartPage(){if(heading)DeleteObject(heading);if(title)DeleteObject(title);}
const char* StartPage::taskName()const{return std::array<const char*,3>{"block","item","model"}[int(task)];}
bool StartPage::canResume()const{
    const auto& s=app->state;
    return app->loaded&&(fromEditor||!s["events"].empty()||s["project_path"].isString()||s["source_path"].isString()||s["dirty"].boolean());
}
void StartPage::create(App& owner){
    app=&owner;
    page=app->surface(app->hwnd,54,[this](HDC dc,RECT r){paint(dc,r);});
    HWND h=page->hwnd;
    SetWindowLongPtrW(h,GWL_STYLE,(GetWindowLongPtrW(h,GWL_STYLE)&~WS_TABSTOP)|WS_CLIPCHILDREN);
    SetWindowLongPtrW(h,GWL_EXSTYLE,GetWindowLongPtrW(h,GWL_EXSTYLE)|WS_EX_CONTROLPARENT);
    SetWindowTextW(h,L"开始 · 选择创作任务");
    page->event=[this](UINT m,WPARAM w,LPARAM l)->LRESULT{
        if(m==WM_DRAWITEM){bufferedItem(*reinterpret_cast<DRAWITEMSTRUCT*>(l),[this](auto& item){app->drawButton(item);});return TRUE;}
        if(m==WM_COMMAND){
            if(HIWORD(w)==CBN_SELCHANGE){page->redraw();return 0;}
            if(HIWORD(w)==BN_CLICKED&&(HWND(l)==cards[0]||HWND(l)==cards[1]||HWND(l)==cards[2])){
                app->buttons.at(LOWORD(w)).click();return 0;
            }
            app->command(LOWORD(w),HIWORD(w));return 0;
        }
        return UNHANDLED;
    };
    auto put=[&](const char* id,const wchar_t* label,std::function<void()> click){return app->button(h,id,label,std::move(click));};
    auto ids=std::array<const char*,3>{"start_block","start_item","start_model"};
    for(int i=0;i<3;++i)cards[i]=app->button(h,ids[i],names[i],[this,i]{select(Task(i));},[this,i]{return int(task)==i;});
    mapping=app->combo(h,"start_mapping",{L"六面共用一张贴图",L"六面分别绘制"});
    resolution=app->combo(h,"start_size",{L"16 × 16 px",L"32 × 32 px",L"64 × 64 px",L"128 × 128 px"});
    begin=put("start_create",verbs[0],[this]{launch();});
    open=put("start_open",L"打开已有文件…",[this]{app->openProject();});
    resume=put("start_resume",L"继续当前工程",[this]{hide();});
    ShowWindow(h,SW_HIDE);
}
void StartPage::show(bool fromWorkbench){
    fromEditor=fromWorkbench;visible=true;app->playing=false;app->message.clear();
    auto h=page->hwnd;
    for(HWND child=GetWindow(app->hwnd,GW_CHILD);child;child=GetWindow(child,GW_HWNDNEXT))
        if(child!=h)ShowWindow(child,SW_HIDE);
    SetWindowPos(h,HWND_TOP,0,0,0,0,SWP_NOSIZE|SWP_NOMOVE|SWP_NOACTIVATE);
    layout();SetFocus(cards[int(task)]);
}
void StartPage::hide(){
    if(!visible)return;
    visible=false;ShowWindow(page->hwnd,SW_HIDE);app->message.clear();
    InvalidateRect(app->hwnd,nullptr,FALSE);app->switchPanel(app->panel);
    if(app->firstFit){app->firstFit=false;app->fit();}
}
void StartPage::select(Task selected){
    task=selected;app->message.clear();
    SetWindowTextW(begin,verbs[int(task)]);layout();SetFocus(cards[int(task)]);
}
void StartPage::launch(){
    Task selected=task;bool separate=selected==Task::block&&comboIndex(mapping)==1;
    int size=sizes[comboIndex(resolution)];
    J project=J::object();
    if(selected==Task::block)project=J::object({{"preset",separate?"cube_faces":"cube_shared"},{"face_size",size}});
    if(selected==Task::item)project=J::object({{"preset","pixels"},{"width",size},{"height",size}});
    if(selected==Task::model)project["preset"]="player_rig";
    app->saveBefore([this,project,selected,separate]{
        app->mutate("create_project",J::object({{"settings",project}}),[this,selected,separate](const J&){
            app->afterFetch=[this,selected,separate]{
                if(selected!=Task::model){app->panel=0;app->tool=0;app->uvGuides=separate;}
                hide();if(selected==Task::model)app->changePartMode(true);
            };
        });
        layout();
    });
}
void StartPage::layout(){
    const auto D=[this](int n){return app->D(n);};
    RECT r;GetClientRect(app->hwnd,&r);
    if(fontDpi!=app->dpi){
        if(heading)DeleteObject(heading);if(title)DeleteObject(title);fontDpi=app->dpi;
        heading=pageFont(fontDpi,26,FW_SEMIBOLD);title=pageFont(fontDpi,20,FW_SEMIBOLD);
    }
    app->placeControl(page->hwnd,0,0,r.right,r.bottom);
    int w=pf::min(int(r.right)-D(48),D(860)),x=(r.right-w)/2;
    int h=pf::clamp(int(r.bottom)-D(30),D(375),D(520)),y=pf::max(D(10),(r.bottom-h)/2);
    bool compact=h<D(460);
    int railW=pf::clamp(w*34/100,D(192),D(280));
    content={x,y,x+w,y+h};
    int top=y+D(compact?78:98),bottom=y+h-D(43),gap=D(compact?16:24);
    rail={x,top,x+railW,bottom};settings={rail.right+gap,top,content.right,bottom};
    int padding=D(compact?16:22);fieldsTop=settings.top+D(compact?79:100);rowHeight=D(compact?52:64);
    auto place=[&](HWND c,int xx,int yy,int ww,int hh,bool shown=true){app->placeControl(c,xx,yy,ww,hh,shown);};
    int labelH=D(25),cardH=D(compact?42:54),sGap=D(compact?5:7);
    place(cards[0],x,rail.top+labelH,railW,cardH);place(cards[1],x,rail.top+labelH+cardH+sGap,railW,cardH);
    place(cards[2],x,rail.top+2*labelH+2*cardH+2*sGap+D(12),railW,cardH);
    int fx=settings.left+padding,fw=settings.right-padding-fx;
    int drop=fieldsTop+D(20),sizeAt=drop+(task==Task::block?rowHeight:0);
    place(mapping,fx,drop,fw,D(130),task==Task::block);
    place(resolution,fx,sizeAt,fw,D(190),task!=Task::model);
    place(begin,fx,settings.bottom-D(48),fw,D(34));
    int bx=x+D(130),fy=content.bottom-D(31);
    place(open,x,fy,D(122),D(30));place(resume,bx,fy,D(120),D(30),canResume());
    EnableWindow(page->hwnd,!app->mutationPending);
    EnableWindow(begin,app->loaded);EnableWindow(open,app->loaded);
    page->redraw();
    for(auto c:cards)InvalidateRect(c,nullptr,FALSE);InvalidateRect(begin,nullptr,FALSE);
}
void StartPage::paint(HDC dc,RECT r){
    auto D=[this](int n){return app->D(n);};fill(dc,r,paper);
    auto label=[&](std::wstring s,int x,int y,int right,int height,COLORREF color,HFONT f,UINT align=DT_LEFT){
        SelectObject(dc,f);text(dc,std::move(s),{x,y,right,y+height},color,DT_SINGLELINE|DT_VCENTER|DT_NOPREFIX|DT_END_ELLIPSIS|align);
    };
    const int x=content.left,y=content.top,w=content.right;bool compact=content.bottom-y<D(460);
    auto icon=reinterpret_cast<HICON>(GetClassLongPtrW(app->hwnd,GCLP_HICONSM));
    DrawIconEx(dc,x,y+D(2),icon,D(21),D(21),0,nullptr,DI_NORMAL);
    label(L"PixForge",x+D(29),y,w,D(24),lilac,app->boldFont);
    label(L"选择创作任务",x,y+D(compact?27:35),w,D(37),ink,heading);
    label(L"方块与物品",x,rail.top,rail.right,D(23),muted,app->boldFont);
    RECT third;GetWindowRect(cards[2],&third);MapWindowPoints(nullptr,page->hwnd,reinterpret_cast<POINT*>(&third),2);
    label(L"三维建模",x,third.top-D(25),rail.right,D(23),muted,app->boldFont);
    roundBox(dc,settings,D(12),pane,rule);
    const int pad=D(compact?16:22),a=settings.left+pad,b=settings.right-pad;
    label(names[int(task)],a,settings.top+D(compact?9:17),b,D(34),ink,title);
    label(captions[int(task)],a,settings.top+D(compact?42:54),b,D(22),muted,app->font);
    const bool block=task==Task::block,model=task==Task::model;
    label(model?L"起始模型":block?L"面贴图方式":L"画布尺寸",a,fieldsTop,b,D(20),muted,app->font);
    if(block)label(L"每面尺寸",a,fieldsTop+rowHeight,b,D(20),muted,app->font);
    if(model)label(L"玩家骨架",a,fieldsTop+D(22),b,D(26),ink,app->boldFont);
    int size=sizes[comboIndex(resolution)];
    bool atlas=block&&comboIndex(mapping)==1;
    auto detail=model?std::wstring(L"头部、身体和四肢  ·  128 × 128 px 图集"):
        (atlas?L"1 个可编辑方块  ·  六面图集  ":block?L"1 个可编辑方块  ·  共用贴图  ":L"透明画布  ·  ")+
        std::to_wstring(size*(atlas?3:1))+L" × "+std::to_wstring(size*(atlas?2:1))+L" px";
    label(detail,a,fieldsTop+(block?2:1)*rowHeight,b,D(22),lilac,app->font);
    line(dc,x,content.bottom-D(38),w,content.bottom-D(38),rule);
    std::wstring note;
    if(!app->message.empty())note=app->message;
    else if(canResume()){
        const auto& s=app->state;auto path=s["project_path"].str(s["source_path"].str());
        note=path.empty()?L"未命名工程":fs::path(wide(path)).filename().wstring();
        if(s["dirty"].boolean())note+=L"  ·  未保存";
    }
    if(!note.empty())label(note,x+D(canResume()?260:130),content.bottom-D(31),w,D(30),muted,app->font,DT_RIGHT);
}
bool StartPage::drawButton(const DRAWITEMSTRUCT& item)const{
    if(!visible||!page||GetParent(item.hwndItem)!=page->hwnd||item.CtlType!=ODT_BUTTON)return false;
    HWND h=item.hwndItem;auto dc=item.hDC;RECT r=item.rcItem;
    bool pressed=(item.itemState&ODS_SELECTED)!=0,hover=choice::hovered(h),primary=h==begin;
    bool disabled=(item.itemState&ODS_DISABLED)!=0;auto D=[this](int n){return app->D(n);};
    bool tile=false,chosen=false;int kind=0;for(int i=0;i<3;++i)if(h==cards[i]){tile=true;kind=i;chosen=int(task)==i;break;}
    fill(dc,r,primary?pane:paper);
    COLORREF bg=primary?(disabled?rule:pressed?RGB(150,140,208):hover?RGB(209,202,255):lilac):
        chosen?(hover?RGB(73,67,99):RGB(65,60,88)):pressed||hover?RGB(59,64,77):tile?card:paper;
    roundBox(dc,r,D(9),bg,chosen?lilac:primary?bg:rule);
    if(tile){
        diagram(dc,D(14),(r.bottom-D(23))/2,D(23),kind);
        SelectObject(dc,app->boldFont);text(dc,names[kind],{D(52),0,r.right-D(15),r.bottom},ink);
        if(chosen){int x=r.right-D(21),y=r.bottom/2;line(dc,x-D(3),y,x,y+D(3),lilac,D(2));line(dc,x,y+D(3),x+D(6),y-D(4),lilac,D(2));}
    }else{
        SelectObject(dc,primary?app->boldFont:app->font);
        text(dc,windowText(h),r,primary&&!disabled?paper:ink,DT_SINGLELINE|DT_VCENTER|DT_CENTER|DT_NOPREFIX);
    }
    drawButtonFocus(dc,r,h,item.itemState);return true;
}
bool StartPage::key(MSG& msg){
    if(msg.message!=WM_KEYDOWN)return false;
    auto k=msg.wParam;auto focus=GetFocus();
    if(k==VK_TAB||k==VK_RETURN||k==VK_SPACE)keyboardFocusMode(page->hwnd,true);
    if((GetKeyState(VK_CONTROL)&0x8000)&&k=='O'){app->userAction([this]{app->openProject();});return true;}
    if(k==VK_ESCAPE&&canResume()){hide();return true;}
    for(int i=0;i<3;++i)if(focus==cards[i]&&(k==VK_UP||k==VK_DOWN)){
        keyboardFocusMode(page->hwnd,true);select(Task((i+(k==VK_UP?2:1))%3));return true;
    }
    if(k==VK_RETURN&&Form::className(focus)==L"Button"){SendMessageW(focus,BM_CLICK,0,0);return true;}
    return false;
}
}
