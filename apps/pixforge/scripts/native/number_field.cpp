#include "number_field.hpp"
#include "widgets.hpp"
#include <charconv>
#include <cwctype>

namespace pf::numberField {
namespace {
constexpr COLORREF chrome=RGB(35,38,46),base=RGB(43,46,54),hover=RGB(54,57,65),
    pressed=RGB(62,65,74),edge=RGB(69,73,84),ink=RGB(234,236,241),
    quiet=RGB(164,171,184),unavailable=RGB(101,107,119),accent=RGB(177,168,244);
enum class Part { none, value, up, down };

struct Field {
    std::wstring unit;
    double low,high,value;
    bool integral;
    std::function<void(double)> changed;
    HWND hwnd=nullptr,edit=nullptr;HFONT font=nullptr;
    bool editing=false,scrubbing=false,repeating=false;
    Part hot=Part::none,held=Part::none;
    int startX=0;double startValue=0;
    int D(int n)const{return MulDiv(n,GetDpiForWindow(hwnd),96);}
    RECT area()const{RECT r;GetClientRect(hwnd,&r);return r;}
    int split()const{return area().right-D(20);}
    double bounded(double n)const{return pf::clamp(integral?std::round(n):n,low,high);}
    std::wstring number()const{
        char buf[64];auto end=std::to_chars(buf,buf+sizeof buf,value).ptr;
        return std::wstring(buf,end);
    }
    void title(){auto s=number()+unit;SetWindowTextW(hwnd,s.c_str());}
    void update(double n,bool notify=true){
        n=bounded(n);if(n==value)return;
        value=n;title();InvalidateRect(hwnd,nullptr,FALSE);
        if(notify)changed(n);
    }
    Part hit(int x,int y)const{
        auto r=area();if(x<0||x>=r.right||y<0||y>=r.bottom)return Part::none;
        return x<split()?Part::value:y<r.bottom/2?Part::up:Part::down;
    }
    bool allowed(Part p)const{return p==Part::up?value<high:p==Part::down?value>low:true;}
    void mark(Part p){if(p!=hot){hot=p;InvalidateRect(hwnd,nullptr,FALSE);}}
    void editorLayout(){
        auto r=area();int w=pf::max(1,split()-D(8)),h=pf::max(1,r.bottom-D(4));
        SetWindowPos(edit,nullptr,D(6),D(2),w,h,SWP_NOZORDER|SWP_NOACTIVATE);
        HDC dc=GetDC(edit);auto old=SelectObject(dc,font);TEXTMETRICW tm{};GetTextMetricsW(dc,&tm);
        SelectObject(dc,old);ReleaseDC(edit,dc);
        RECT textBox{0,pf::max(0,(h-tm.tmHeight)/2),w-D(1),h};
        SendMessageW(edit,EM_SETRECTNP,0,LPARAM(&textBox));
    }
    void beginEdit(){
        if(editing)return;
        editing=true;auto s=number();SetWindowTextW(edit,s.c_str());editorLayout();
        ShowWindow(edit,SW_SHOW);SetFocus(edit);SendMessageW(edit,EM_SETSEL,0,-1);InvalidateRect(hwnd,nullptr,FALSE);
    }
    void finishEdit(bool accept){
        if(!editing)return;
        editing=false;
        if(accept){
            auto s=windowText(edit);wchar_t* end=nullptr;double n=std::wcstod(s.c_str(),&end);
            bool parsed=end!=s.c_str();while(std::iswspace(*end))++end;
            if(parsed&&!*end&&std::isfinite(n))update(n);
        }
        ShowWindow(edit,SW_HIDE);InvalidateRect(hwnd,nullptr,FALSE);
    }
    void nudge(Part p){update(value+(p==Part::up?1:-1));}
    void release(){
        KillTimer(hwnd,1);held=Part::none;scrubbing=false;repeating=false;
        InvalidateRect(hwnd,nullptr,FALSE);
    }
    void paint(HDC dc){
        auto r=area();bool enabled=IsWindowEnabled(hwnd)!=FALSE;
        fill(dc,r,chrome);
        HBRUSH brush=CreateSolidBrush(enabled&&(held==Part::value||editing)?pressed:enabled&&hot!=Part::none?hover:base);
        auto oldBrush=SelectObject(dc,brush);auto oldPen=SelectObject(dc,GetStockObject(NULL_PEN));
        RoundRect(dc,0,0,r.right,r.bottom,D(9),D(9));SelectObject(dc,oldBrush);SelectObject(dc,oldPen);DeleteObject(brush);
        int x=split(),mid=r.bottom/2;
        if(!editing){
            auto titleText=number()+unit;RECT label{D(7),0,x-D(2),r.bottom};SelectObject(dc,font);
            text(dc,titleText,label,enabled?ink:unavailable,DT_LEFT|DT_VCENTER|DT_SINGLELINE|DT_END_ELLIPSIS|DT_NOPREFIX);
        }
        line(dc,x,D(4),x,r.bottom-D(4),edge);
        for(auto p:{Part::up,Part::down}){
            auto active=enabled&&allowed(p);int y=p==Part::up?mid/2:(mid+r.bottom)/2;
            RECT target{x+1,p==Part::up?1:mid,r.right-D(2),p==Part::up?mid:r.bottom-1};
            if(active&&hot==p)fill(dc,target,held==p?edge:pressed);
            int center=(x+r.right)/2,dir=p==Part::up?-1:1;
            auto color=active?(p==hot?ink:quiet):unavailable;
            line(dc,center-D(3),y-dir*D(1),center,y+dir*D(2),color);
            line(dc,center,y+dir*D(2),center+D(3),y-dir*D(1),color);
        }
        if(editing)line(dc,D(5),r.bottom-D(1),x-D(4),r.bottom-D(1),accent);
        else drawButtonFocus(dc,r,hwnd,GetFocus()==hwnd?ODS_FOCUS:0);
    }
    static LRESULT CALLBACK editProc(HWND h,UINT m,WPARAM w,LPARAM l,UINT_PTR id,DWORD_PTR ref){
        auto& f=*reinterpret_cast<Field*>(ref);
        if(m==WM_GETDLGCODE){
            auto msg=reinterpret_cast<MSG*>(l);auto code=DefSubclassProc(h,m,w,l);
            // The dialog manager still owns Tab; losing focus commits the value.
            if(msg&&msg->wParam==VK_TAB)return code&~(DLGC_WANTTAB|DLGC_WANTALLKEYS);
            if(msg&&(msg->wParam==VK_RETURN||msg->wParam==VK_ESCAPE||msg->wParam==VK_UP||msg->wParam==VK_DOWN))code|=DLGC_WANTMESSAGE;
            return code;
        }
        if(m==WM_KEYDOWN){
            if(w==VK_RETURN||w==VK_ESCAPE||w==VK_UP||w==VK_DOWN){
                f.finishEdit(w!=VK_ESCAPE);SetFocus(f.hwnd);
                if(w==VK_UP||w==VK_DOWN)f.nudge(w==VK_UP?Part::up:Part::down);
                return 0;
            }
            if(w=='A'&&(GetKeyState(VK_CONTROL)&0x8000)){SendMessageW(h,EM_SETSEL,0,-1);return 0;}
        }
        if(m==WM_CHAR&&(w=='\r'||w=='\n'||w==27))return 0;
        if(m==WM_NCDESTROY)RemoveWindowSubclass(h,editProc,id);
        return DefSubclassProc(h,m,w,l);
    }
    static LRESULT CALLBACK proc(HWND h,UINT m,WPARAM w,LPARAM l){
        auto f=reinterpret_cast<Field*>(GetWindowLongPtrW(h,GWLP_USERDATA));
        if(m==WM_NCCREATE){f=static_cast<Field*>(reinterpret_cast<CREATESTRUCTW*>(l)->lpCreateParams);f->hwnd=h;SetWindowLongPtrW(h,GWLP_USERDATA,LONG_PTR(f));}
        if(!f)return DefWindowProcW(h,m,w,l);
        switch(m){
        case WM_CREATE:
            f->edit=CreateWindowExW(0,L"EDIT",L"",WS_CHILD|ES_MULTILINE|ES_AUTOHSCROLL|ES_NOHIDESEL,0,0,1,1,h,
                reinterpret_cast<HMENU>(INT_PTR(1)),GetModuleHandleW(nullptr),nullptr);
            SetWindowSubclass(f->edit,editProc,1,DWORD_PTR(f));SendMessageW(f->edit,EM_SETLIMITTEXT,40,0);return 0;
        case WM_SETFONT:f->font=HFONT(w);SendMessageW(f->edit,WM_SETFONT,w,FALSE);f->editorLayout();InvalidateRect(h,nullptr,FALSE);return 0;
        case WM_GETFONT:return LRESULT(f->font);
        case WM_SIZE:if(f->edit)f->editorLayout();return 0;
        case WM_ERASEBKGND:return 1;
        case WM_PRINTCLIENT:case WM_PAINT:{
            PAINTSTRUCT ps{};auto dc=m==WM_PAINT?BeginPaint(h,&ps):HDC(w);
            bufferedPaint(dc,f->area(),[&](HDC mem){f->paint(mem);});
            if(m==WM_PAINT)EndPaint(h,&ps);return 0;
        }
        case WM_SETFOCUS:case WM_KILLFOCUS:InvalidateRect(h,nullptr,FALSE);return 0;
        case WM_ENABLE:if(!w){if(GetCapture()==h)ReleaseCapture();f->finishEdit(true);}InvalidateRect(h,nullptr,FALSE);return 0;
        case WM_CTLCOLOREDIT:SetTextColor(HDC(w),ink);SetBkColor(HDC(w),pressed);SetDCBrushColor(HDC(w),pressed);return LRESULT(GetStockObject(DC_BRUSH));
        case WM_COMMAND:if(HWND(l)==f->edit&&HIWORD(w)==EN_KILLFOCUS)f->finishEdit(true);return 0;
        case WM_SETCURSOR:{
            POINT p;GetCursorPos(&p);ScreenToClient(h,&p);
            SetCursor(LoadCursorW(nullptr,p.x<f->split()?IDC_SIZEWE:IDC_ARROW));return TRUE;
        }
        case WM_MOUSELEAVE:f->mark(Part::none);return 0;
        case WM_LBUTTONDOWN:case WM_LBUTTONDBLCLK:{
            f->finishEdit(true);SetFocus(h);keyboardFocusMode(h,false);
            int x=GET_X_LPARAM(l);f->held=f->hit(x,GET_Y_LPARAM(l));f->mark(f->held);
            f->startX=x;f->startValue=f->value;f->scrubbing=false;SetCapture(h);
            if(f->held==Part::up||f->held==Part::down){f->nudge(f->held);SetTimer(h,1,420,nullptr);}
            InvalidateRect(h,nullptr,FALSE);return 0;
        }
        case WM_MOUSEMOVE:{
            int x=GET_X_LPARAM(l);auto part=f->hit(x,GET_Y_LPARAM(l));
            if(f->hot==Part::none){TRACKMOUSEEVENT t{sizeof t,TME_LEAVE,h,0};TrackMouseEvent(&t);}
            f->mark(part);
            if(f->held==Part::value){
                int dx=x-f->startX;
                if(!f->scrubbing&&std::abs(dx)>=GetSystemMetricsForDpi(SM_CXDRAG,GetDpiForWindow(h)))f->scrubbing=true;
                if(f->scrubbing)f->update(f->startValue+std::trunc(double(dx)/pf::max(1,f->D(3))));
            }return 0;
        }
        case WM_TIMER:
            if(w==1&&(f->held==Part::up||f->held==Part::down)){
                if(!f->repeating){f->repeating=true;SetTimer(h,1,75,nullptr);}
                if(f->hot==f->held)f->nudge(f->held);
            }return 0;
        case WM_LBUTTONUP:{
            bool input=f->held==Part::value&&!f->scrubbing&&f->hit(GET_X_LPARAM(l),GET_Y_LPARAM(l))==Part::value;
            f->release();if(GetCapture()==h)ReleaseCapture();if(input)f->beginEdit();return 0;
        }
        case WM_CAPTURECHANGED:f->release();return 0;
        case WM_CANCELMODE:if(GetCapture()==h)ReleaseCapture();return 0;
        case WM_GETDLGCODE:{
            auto msg=reinterpret_cast<MSG*>(l);
            return DLGC_WANTARROWS|DLGC_WANTCHARS|((msg&&(msg->wParam==VK_RETURN||msg->wParam==VK_F2||msg->wParam==VK_SPACE))?DLGC_WANTMESSAGE:0);
        }
        case WM_KEYDOWN:
            if(w==VK_RETURN||w==VK_F2||w==VK_SPACE){f->beginEdit();return 0;}
            if(w==VK_UP||w==VK_DOWN){f->nudge(w==VK_UP?Part::up:Part::down);return 0;}
            break;
        case WM_CHAR:
            if(w>='0'&&w<='9'){f->beginEdit();SendMessageW(f->edit,WM_CHAR,w,l);}return 0;
        case WM_NCDESTROY:SetWindowLongPtrW(h,GWLP_USERDATA,0);delete f;break;
        }
        return DefWindowProcW(h,m,w,l);
    }
};
Field& get(HWND h){return *reinterpret_cast<Field*>(GetWindowLongPtrW(h,GWLP_USERDATA));}
}

HWND create(HWND parent,int id,HFONT font,const wchar_t* unit,double low,double high,double value,bool integral,std::function<void(double)> changed){
    static const auto atom=[]{
        WNDCLASSEXW wc{sizeof wc};wc.lpfnWndProc=Field::proc;wc.hInstance=GetModuleHandleW(nullptr);
        wc.lpszClassName=L"PixForgeNumberField";wc.hCursor=LoadCursorW(nullptr,IDC_ARROW);return RegisterClassExW(&wc);
    }();
    auto f=new Field{unit,low,high,value,integral,std::move(changed)};
    auto h=CreateWindowExW(0,MAKEINTATOM(atom),L"",WS_CHILD|WS_VISIBLE|WS_TABSTOP|WS_CLIPCHILDREN,0,0,1,1,parent,
        reinterpret_cast<HMENU>(INT_PTR(id)),GetModuleHandleW(nullptr),f);
    SendMessageW(h,WM_SETFONT,WPARAM(font),TRUE);f->title();return h;
}
void set(HWND h,double value){
    auto& f=get(h);f.finishEdit(false);f.update(value,false);
}
void range(HWND h,double minimum,double maximum){
    auto& f=get(h);if(minimum==f.low&&maximum==f.high)return;
    f.finishEdit(false);f.low=minimum;f.high=maximum;f.update(f.value);InvalidateRect(h,nullptr,FALSE);
}
}
