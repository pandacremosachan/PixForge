#include "widgets.hpp"

namespace pf::choice {
namespace {
constexpr COLORREF chrome=RGB(35,38,46),field=RGB(43,46,54),panel=RGB(42,45,53),
    hover=RGB(54,57,65),down=RGB(62,65,74),edge=RGB(69,73,84),
    ink=RGB(234,236,241),subtle=RGB(163,169,182),disabled=RGB(112,118,130),accent=RGB(192,184,248);
constexpr wchar_t hotProp[]=L"PixForgeChoiceHover", openProp[]=L"PixForgeChoiceOpen",
                  pressProp[]=L"PixForgeChoicePressed";
constexpr int listId=1;

void box(HDC dc,RECT rect,COLORREF color,int radius,COLORREF outline=CLR_INVALID){
    auto brush=CreateSolidBrush(color);
    auto pen=outline==CLR_INVALID?HPEN(GetStockObject(NULL_PEN)):CreatePen(PS_SOLID,1,outline);
    auto oldBrush=SelectObject(dc,brush),oldPen=SelectObject(dc,pen);
    RoundRect(dc,rect.left,rect.top,rect.right,rect.bottom,radius*2,radius*2);
    SelectObject(dc,oldPen);SelectObject(dc,oldBrush);
    if(outline!=CLR_INVALID)DeleteObject(pen);
    DeleteObject(brush);
}
int scale(HWND window,int value){return MulDiv(value,GetDpiForWindow(window),96);}

struct Popup {
    const std::vector<Row>& rows;
    HWND anchor,window=nullptr,list=nullptr;
    HFONT font;
    std::vector<int> offsets{0};
    int width=0,height=0,viewport=0,initial=-1,pressed=-1,result=0,dragOffset=-1;
    bool done=false,scrollable=false;
    std::wstring search;
    ULONGLONG lastType=0;
    int D(int value)const{return scale(anchor,value);}
    int pad()const{return D(5);}
    int rowHeight(int index)const{
        switch(rows[index].kind){case Kind::line:return D(9);case Kind::heading:return D(25);default:return D(28);}
    }
    int count()const{return int(rows.size());}
    bool selectable(int i)const{return i>=0&&i<count()&&rows[i].kind==Kind::item&&rows[i].enabled;}
    int current()const{return int(SendMessageW(list,LB_GETCURSEL,0,0));}
    void choose(int index){if(selectable(index)){result=rows[index].id;done=true;}}
    void highlight(int index){
        if(selectable(index)&&current()!=index){SendMessageW(list,LB_SETCURSEL,index,0);InvalidateRect(window,nullptr,FALSE);}
    }
    void jump(int start,int direction){
        for(int i=pf::clamp(start,0,count()-1);i>=0&&i<count();i+=direction)if(selectable(i)){highlight(i);return;}
    }
    int rowAt(LPARAM point)const{
        RECT r;GetClientRect(list,&r);POINT p{GET_X_LPARAM(point),GET_Y_LPARAM(point)};
        if(!PtInRect(&r,p))return -1;
        auto hit=SendMessageW(list,LB_ITEMFROMPOINT,0,point);int i=LOWORD(hit);
        if(HIWORD(hit)||i>=count())return -1;
        RECT row;SendMessageW(list,LB_GETITEMRECT,i,LPARAM(&row));return PtInRect(&row,p)?i:-1;
    }
    RECT thumb()const{
        int total=offsets.back(),top=int(SendMessageW(list,LB_GETTOPINDEX,0,0));
        int size=pf::max(D(22),MulDiv(viewport,viewport,total));
        int y=pad()+MulDiv(pf::min(offsets[top],total-viewport),viewport-size,total-viewport);
        return {width-pad()-D(4),y,width-pad(),y+size};
    }
    void scroll(int top){SendMessageW(list,LB_SETTOPINDEX,pf::clamp(top,0,count()-1),0);InvalidateRect(window,nullptr,FALSE);}
    void draw(const DRAWITEMSTRUCT& d)const{
        if(d.itemID>=rows.size())return;
        const auto& row=rows[d.itemID];RECT r=d.rcItem;auto dc=d.hDC;
        fill(dc,r,panel);
        if(row.kind==Kind::line){int mid=(r.top+r.bottom)/2;line(dc,r.left+D(8),mid,r.right-D(8),mid,edge);return;}
        bool hot=(d.itemState&ODS_SELECTED)&&selectable(d.itemID);
        if(hot){RECT bg=r;InflateRect(&bg,0,-D(1));box(dc,bg,hover,D(4));}
        SelectObject(dc,font);
        RECT label=r;label.left+=D(10);label.right-=D(12);
        if(!row.shortcut.empty()){
            SIZE sz;GetTextExtentPoint32W(dc,row.shortcut.c_str(),int(row.shortcut.size()),&sz);
            text(dc,row.shortcut,label,subtle,DT_RIGHT|DT_SINGLELINE|DT_VCENTER|DT_NOPREFIX);
            label.right-=sz.cx+D(16);
        }
        if(row.checked){
            int x=r.right-D(14),y=(r.top+r.bottom)/2;
            box(dc,{x-D(2),y-D(2),x+D(3),y+D(3)},accent,D(3));label.right-=D(12);
        }
        auto color=row.kind==Kind::heading?subtle:!row.enabled?disabled:row.checked?accent:ink;
        text(dc,row.label,label,color,DT_LEFT|DT_SINGLELINE|DT_VCENTER|DT_END_ELLIPSIS|DT_NOPREFIX);
    }
    void type(wchar_t c){
        if(c<32)return;auto now=GetTickCount64();
        if(now-lastType>950)search.clear();lastType=now;search+=c;
        auto find=[&]{for(int i=0;i<count();++i){
            auto pos=rows[i].label.find_first_not_of(L" ");
            if(selectable(i)&&pos!=std::wstring::npos&&_wcsnicmp(rows[i].label.c_str()+pos,search.c_str(),search.size())==0){highlight(i);return true;}
        }return false;};
        if(!find()&&search.size()>1){search.assign(1,c);find();}
    }
    static LRESULT CALLBACK listProc(HWND h,UINT m,WPARAM w,LPARAM l,UINT_PTR id,DWORD_PTR data){
        auto& p=*reinterpret_cast<Popup*>(data);
        switch(m){
        case WM_MOUSEMOVE:{int i=p.rowAt(l);if(p.selectable(i))p.highlight(i);return 0;}
        case WM_LBUTTONDOWN:case WM_LBUTTONDBLCLK:p.pressed=p.rowAt(l);p.highlight(p.pressed);SetCapture(h);return 0;
        case WM_LBUTTONUP:{int i=p.rowAt(l);if(GetCapture()==h)ReleaseCapture();if(i==p.pressed)p.choose(i);p.pressed=-1;return 0;}
        case WM_MOUSEWHEEL:if(p.scrollable)p.scroll(int(SendMessageW(h,LB_GETTOPINDEX,0,0))-3*GET_WHEEL_DELTA_WPARAM(w)/WHEEL_DELTA);return 0;
        case WM_CHAR:p.type(wchar_t(w));return 0;
        case WM_KEYDOWN:case WM_SYSKEYDOWN:{
            int i=p.current(),page=pf::max(1,p.viewport/p.D(28)-1);
            switch(w){
            case VK_ESCAPE:case VK_F4:p.done=true;return 0;
            case VK_RETURN:case VK_SPACE:p.choose(i);return 0;
            case VK_TAB:p.done=true;PostMessageW(GetAncestor(p.anchor,GA_ROOT),WM_NEXTDLGCTL,GetKeyState(VK_SHIFT)<0,0);return 0;
            case VK_HOME:p.jump(0,1);return 0;case VK_END:p.jump(p.count()-1,-1);return 0;
            case VK_UP:if(m==WM_SYSKEYDOWN){p.done=true;return 0;}p.jump(i<0?p.count()-1:i-1,-1);return 0;
            case VK_DOWN:p.jump(i+1,1);return 0;
            case VK_PRIOR:p.jump(i-page,-1);return 0;case VK_NEXT:p.jump(i+page,1);return 0;
            }break;
        }
        case WM_SETFOCUS:case WM_KILLFOCUS:InvalidateRect(h,nullptr,FALSE);break;
        case WM_NCDESTROY:RemoveWindowSubclass(h,listProc,id);break;
        }
        return DefSubclassProc(h,m,w,l);
    }
    static LRESULT CALLBACK proc(HWND h,UINT m,WPARAM w,LPARAM l){
        auto p=reinterpret_cast<Popup*>(GetWindowLongPtrW(h,GWLP_USERDATA));
        if(m==WM_NCCREATE){p=static_cast<Popup*>(reinterpret_cast<CREATESTRUCTW*>(l)->lpCreateParams);SetWindowLongPtrW(h,GWLP_USERDATA,LONG_PTR(p));}
        if(!p)return DefWindowProcW(h,m,w,l);
        switch(m){
        case WM_CLOSE:case WM_CANCELMODE:case WM_DESTROY:p->done=true;return 0;
        case WM_ACTIVATE:if(LOWORD(w)==WA_INACTIVE)p->done=true;return 0;
        case WM_ERASEBKGND:return 1;
        case WM_PAINT:{
            PAINTSTRUCT ps;auto dc=BeginPaint(h,&ps);RECT r;GetClientRect(h,&r);
            box(dc,r,panel,p->D(6),edge);
            if(p->scrollable&&p->list)box(dc,p->thumb(),RGB(100,104,116),p->D(2));
            EndPaint(h,&ps);return 0;
        }
        case WM_CTLCOLORLISTBOX:SetBkColor(HDC(w),panel);SetDCBrushColor(HDC(w),panel);return LRESULT(GetStockObject(DC_BRUSH));
        case WM_MEASUREITEM:{auto item=reinterpret_cast<MEASUREITEMSTRUCT*>(l);item->itemHeight=item->itemID<p->rows.size()?p->rowHeight(item->itemID):p->D(28);return TRUE;}
        case WM_DRAWITEM:p->draw(*reinterpret_cast<DRAWITEMSTRUCT*>(l));return TRUE;
        case WM_LBUTTONDOWN:
            if(p->scrollable&&GET_X_LPARAM(l)>=p->width-p->pad()-p->D(10)){
                auto t=p->thumb();int y=GET_Y_LPARAM(l);
                if(y>=t.top&&y<t.bottom){p->dragOffset=y-t.top;SetCapture(h);}
                else p->scroll(int(SendMessageW(p->list,LB_GETTOPINDEX,0,0))+(y<t.top?-1:1)*pf::max(1,p->viewport/p->D(28)-1));
            }return 0;
        case WM_MOUSEMOVE:
            if(p->dragOffset>=0){auto t=p->thumb();int travel=p->viewport-(t.bottom-t.top);
                int offset=MulDiv(pf::clamp(GET_Y_LPARAM(l)-p->pad()-p->dragOffset,0,travel),p->offsets.back()-p->viewport,travel);
                p->scroll(int(std::upper_bound(p->offsets.begin(),p->offsets.end(),offset)-p->offsets.begin())-1);}
            return 0;
        case WM_LBUTTONUP:if(p->dragOffset>=0){p->dragOffset=-1;ReleaseCapture();}return 0;
        case WM_CAPTURECHANGED:p->dragOffset=-1;return 0;
        }
        return DefWindowProcW(h,m,w,l);
    }
    int run(bool above,int maxHeight){
        if(!count())return 0;
        static const auto atom=[]{
            WNDCLASSEXW wc{sizeof wc};wc.lpfnWndProc=proc;wc.style=CS_DROPSHADOW;
            wc.hInstance=GetModuleHandleW(nullptr);wc.lpszClassName=L"PixForgeChoicePopup";wc.hCursor=LoadCursorW(nullptr,IDC_ARROW);
            return RegisterClassExW(&wc);
        }();
        auto owner=GetAncestor(anchor,GA_ROOT);RECT a;GetWindowRect(anchor,&a);
        MONITORINFO mon{sizeof mon};GetMonitorInfoW(MonitorFromRect(&a,MONITOR_DEFAULTTONEAREST),&mon);auto area=mon.rcWork;
        HDC dc=GetDC(anchor);auto old=SelectObject(dc,font);width=pf::max(D(154),a.right-a.left);
        for(int i=0;i<count();++i){
            const auto& row=rows[i];SIZE label{},hint{};
            GetTextExtentPoint32W(dc,row.label.c_str(),int(row.label.size()),&label);
            if(!row.shortcut.empty())GetTextExtentPoint32W(dc,row.shortcut.c_str(),int(row.shortcut.size()),&hint);
            width=pf::max(width,label.cx+hint.cx+D(52)+(hint.cx?D(16):0));
            offsets.push_back(offsets.back()+rowHeight(i));if(row.checked)initial=i;
        }
        SelectObject(dc,old);ReleaseDC(anchor,dc);
        int gap=D(3),want=pf::min(offsets.back()+2*pad(),D(maxHeight));
        int below=area.bottom-a.bottom-gap,over=a.top-area.top-gap;
        bool up=above?(over>=want||over>=below):(below<want&&over>below);
        height=pf::min(want,pf::max(D(40),up?over:below));viewport=height-2*pad();
        scrollable=offsets.back()>viewport;
        if(scrollable&&std::all_of(rows.begin(),rows.end(),[](const Row& row){return row.kind==Kind::item;})){
            viewport-=viewport%D(28);height=viewport+2*pad();
        }
        width=pf::min(width+(scrollable?D(8):0),pf::min(D(470),area.right-area.left));
        int x=pf::clamp(a.left,area.left,area.right-width),y=pf::clamp(up?a.top-gap-height:a.bottom+gap,area.top,area.bottom-height);
        auto prior=GetFocus();
        window=CreateWindowExW(WS_EX_TOOLWINDOW,MAKEINTATOM(atom),L"选项",WS_POPUP|WS_CLIPCHILDREN,x,y,width,height,owner,nullptr,GetModuleHandleW(nullptr),this);
        if(!window)return 0;
        SetWindowRgn(window,CreateRoundRectRgn(0,0,width+1,height+1,D(12),D(12)),FALSE);
        list=CreateWindowExW(0,L"LISTBOX",nullptr,WS_CHILD|WS_VISIBLE|WS_TABSTOP|LBS_HASSTRINGS|LBS_OWNERDRAWVARIABLE|LBS_NOINTEGRALHEIGHT,
            pad(),pad(),width-2*pad()-(scrollable?D(9):0),viewport,window,reinterpret_cast<HMENU>(INT_PTR(listId)),GetModuleHandleW(nullptr),nullptr);
        SendMessageW(list,WM_SETFONT,WPARAM(font),FALSE);
        for(const auto& row:rows)SendMessageW(list,LB_ADDSTRING,0,LPARAM(row.label.c_str()));
        SetWindowSubclass(list,listProc,1,DWORD_PTR(this));
        if(initial>=0){highlight(initial);if(scrollable)scroll(initial-viewport/D(28)/2);}
        else if(GetPropW(owner,L"PixForgeKeyboardFocus"))jump(0,1);
        SetPropW(anchor,openProp,window);InvalidateRect(anchor,nullptr,FALSE);
        ShowWindow(window,SW_SHOW);SetFocus(list);UpdateWindow(window);
        MSG msg{};
        while(!done){
            int got=GetMessageW(&msg,nullptr,0,0);
            if(got<=0){if(!got)PostQuitMessage(int(msg.wParam));break;}
            bool outside=msg.hwnd!=window&&!IsChild(window,msg.hwnd);
            if(outside&&(msg.message==WM_LBUTTONDOWN||msg.message==WM_RBUTTONDOWN||msg.message==WM_MBUTTONDOWN||msg.message==WM_NCLBUTTONDOWN)){
                done=true;
                if(msg.hwnd!=anchor){ShowWindow(window,SW_HIDE);DispatchMessageW(&msg);}
                break;
            }
            TranslateMessage(&msg);DispatchMessageW(&msg);
        }
        if(GetActiveWindow()==window&&IsWindow(owner)){SetActiveWindow(owner);if(IsWindow(prior))SetFocus(prior);}
        if(IsWindow(window))DestroyWindow(window);
        if(IsWindow(anchor)){RemovePropW(anchor,openProp);InvalidateRect(anchor,nullptr,FALSE);}
        return result;
    }
};

void pick(HWND h){
    if(GetPropW(h,openProp)||!IsWindowEnabled(h))return;
    Menu menu;int index=int(SendMessageW(h,CB_GETCURSEL,0,0)),count=int(SendMessageW(h,CB_GETCOUNT,0,0));
    for(int i=0;i<count;++i){
        int n=int(SendMessageW(h,CB_GETLBTEXTLEN,i,0));std::wstring value(size_t(n)+1,0);
        SendMessageW(h,CB_GETLBTEXT,i,LPARAM(value.data()));value.resize(n);menu.item(i+1,std::move(value),i==index);
    }
    int chosen=menu.open(h,false,300);
    if(chosen&&IsWindow(h)&&chosen-1!=index&&SendMessageW(h,CB_SETCURSEL,chosen-1,0)!=CB_ERR)
        SendMessageW(GetParent(h),WM_COMMAND,MAKEWPARAM(GetDlgCtrlID(h),CBN_SELCHANGE),LPARAM(h));
}
LRESULT CALLBACK selectProc(HWND h,UINT m,WPARAM w,LPARAM l,UINT_PTR id,DWORD_PTR){
    trackHover(h,m);
    switch(m){
    case WM_NCPAINT:case WM_ERASEBKGND:return 1;
    case WM_PRINT:case WM_PRINTCLIENT:case WM_PAINT:{
        PAINTSTRUCT ps{};auto dc=m==WM_PAINT?BeginPaint(h,&ps):HDC(w);RECT r;GetClientRect(h,&r);
        bufferedPaint(dc,r,[&](HDC out){paintTrigger(out,r,h,windowText(h),Trigger::field,GetPropW(h,pressProp)!=nullptr);});
        if(m==WM_PAINT)EndPaint(h,&ps);return 0;
    }
    case WM_LBUTTONDOWN:case WM_LBUTTONDBLCLK:
        keyboardFocusMode(h,false);SetFocus(h);SetCapture(h);SetPropW(h,pressProp,HANDLE(1));InvalidateRect(h,nullptr,FALSE);return 0;
    case WM_LBUTTONUP:if(GetPropW(h,pressProp)){RECT r;GetClientRect(h,&r);POINT p{GET_X_LPARAM(l),GET_Y_LPARAM(l)};
        RemovePropW(h,pressProp);ReleaseCapture();InvalidateRect(h,nullptr,FALSE);if(PtInRect(&r,p))pick(h);}return 0;
    case WM_CAPTURECHANGED:RemovePropW(h,pressProp);InvalidateRect(h,nullptr,FALSE);return 0;
    case CB_SHOWDROPDOWN:if(w)pick(h);else if(auto popup=GetPropW(h,openProp);popup&&IsWindow(HWND(popup)))PostMessageW(HWND(popup),WM_CLOSE,0,0);return TRUE;
    case CB_GETDROPPEDSTATE:return GetPropW(h,openProp)!=nullptr;
    case WM_GETDLGCODE:{
        auto msg=reinterpret_cast<MSG*>(l);auto code=DefSubclassProc(h,m,w,l);
        if(msg&&(msg->wParam==VK_RETURN||msg->wParam==VK_SPACE||msg->wParam==VK_F4))code|=DLGC_WANTMESSAGE;
        return code;
    }
    case WM_KEYDOWN:case WM_SYSKEYDOWN:
        if(w==VK_RETURN||w==VK_SPACE||w==VK_F4||(m==WM_SYSKEYDOWN&&(w==VK_DOWN||w==VK_UP))){
            keyboardFocusMode(h,true);pick(h);return 0;
        }break;
    case WM_CHAR:if(w==L' '||w==L'\r')return 0;break;
    case WM_SETFOCUS:SendMessageW(GetParent(h),WM_APP+90,WPARAM(h),0);break;
    case WM_NCDESTROY:RemovePropW(h,hotProp);RemovePropW(h,pressProp);RemoveWindowSubclass(h,selectProc,id);break;
    }
    auto ret=DefSubclassProc(h,m,w,l);
    if(m==CB_SETCURSEL||m==WM_SETFOCUS||m==WM_KILLFOCUS||m==WM_ENABLE||m==WM_KEYDOWN||m==WM_CHAR)InvalidateRect(h,nullptr,FALSE);
    return ret;
}
}

void Menu::item(int id,std::wstring value,bool checked,bool enabled){
    auto tab=value.find(L'\t');std::wstring hint;
    if(tab!=std::wstring::npos){hint=value.substr(tab+1);value.resize(tab);}
    rows.push_back({Kind::item,id,std::move(value),std::move(hint),checked,enabled});
}
void Menu::heading(std::wstring value){rows.push_back({Kind::heading,0,std::move(value),{},false,false});}
void Menu::separator(){rows.push_back({Kind::line,0,{},{},false,false});}
int Menu::open(HWND trigger,bool above,int maxHeight)const{
    auto font=HFONT(SendMessageW(trigger,WM_GETFONT,0,0));
    Popup popup{rows,trigger,nullptr,nullptr,font};return popup.run(above,maxHeight);
}
void trackHover(HWND h,UINT m){
    if(m==WM_MOUSEMOVE&&!GetPropW(h,hotProp)){SetPropW(h,hotProp,HANDLE(1));TRACKMOUSEEVENT t{sizeof t,TME_LEAVE,h,0};TrackMouseEvent(&t);InvalidateRect(h,nullptr,FALSE);}
    else if(m==WM_MOUSELEAVE&&RemovePropW(h,hotProp))InvalidateRect(h,nullptr,FALSE);
}
bool hovered(HWND h){return GetPropW(h,hotProp)!=nullptr;}
void paintTrigger(HDC dc,RECT r,HWND h,const std::wstring& value,Trigger style,bool pressed){
    bool enabled=IsWindowEnabled(h)!=FALSE,active=GetPropW(h,openProp)!=nullptr;
    auto base=style==Trigger::field?field:chrome;
    COLORREF bg=enabled&&(pressed||active)?down:enabled&&hovered(h)?hover:base;
    fill(dc,r,chrome);
    RECT face=r;if(style==Trigger::footer){line(dc,r.left,r.top,r.right,r.top,RGB(60,65,77));InflateRect(&face,-scale(h,3),-scale(h,2));}
    box(dc,face,bg,scale(h,5));
    SelectObject(dc,HFONT(SendMessageW(h,WM_GETFONT,0,0)));
    RECT label=r;int pad=scale(h,style==Trigger::footer?16:8);
    bool arrow=style==Trigger::field&&r.right-r.left>=scale(h,92);
    label.left+=pad;label.right-=arrow?scale(h,25):style==Trigger::command?pad:scale(h,3);
    text(dc,value,label,!enabled?disabled:style==Trigger::footer?subtle:ink,(style==Trigger::command?DT_CENTER:DT_LEFT)|DT_SINGLELINE|DT_VCENTER|DT_END_ELLIPSIS|DT_NOPREFIX);
    if(arrow){
        int x=r.right-scale(h,13),y=(r.top+r.bottom)/2,k=scale(h,4);auto color=enabled?subtle:disabled;
        line(dc,x-k,y-k/2,x,y+k/2,color);line(dc,x,y+k/2,x+k,y-k/2,color);
    }
    drawButtonFocus(dc,face,h,GetFocus()==h?ODS_FOCUS:0);
}
void styleSelect(HWND h){SetWindowSubclass(h,selectProc,11,0);}
}
