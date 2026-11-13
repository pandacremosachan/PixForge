#pragma once
#include "tool_glyphs.hpp"

namespace pf {
inline constexpr int GRABBING=TOOL_COUNT;
inline bool precisionTool(int slot){return slot==LINE||slot==RECTANGLE||slot==ELLIPSE||slot==SELECT;}

// The two hand poses share a hotspot, so beginning a pan never shifts the grab point.
inline void drawPanCursor(Gdiplus::Graphics& g,bool closed){
    Gdiplus::GraphicsPath hand;
    auto line=[&](float a,float b,float c,float d){hand.AddLine(a,b,c,d);};
    if(!closed){line(10,18,10,8);hand.AddBezier(10.f,8.f,10.f,5.f,13.2f,5.f,13.2f,8.f);line(13.2f,8,13.2f,15);line(13.2f,15,13.2f,4.8f);hand.AddBezier(13.2f,4.8f,13.2f,2.f,16.5f,2.f,16.5f,4.8f);line(16.5f,4.8f,16.5f,15);line(16.5f,15,16.5f,6);hand.AddBezier(16.5f,6.f,16.5f,3.3f,19.8f,3.3f,19.8f,6.f);line(19.8f,6,19.8f,16);line(19.8f,16,19.8f,10);hand.AddBezier(19.8f,10.f,19.8f,7.4f,23.f,7.4f,23.f,10.f);line(23,10,23,22);}
    else{line(9,17,9,13);hand.AddBezier(9.f,13.f,9.f,10.f,12.f,10.f,12.f,13.f);line(12,13,12,11);hand.AddBezier(12.f,11.f,12.f,8.f,15.3f,8.f,15.3f,11.f);line(15.3f,11,15.3f,10);hand.AddBezier(15.3f,10.f,15.3f,7.3f,18.6f,7.3f,18.6f,10.f);line(18.6f,10,18.6f,12);hand.AddBezier(18.6f,12.f,18.6f,9.4f,22.f,9.4f,22.f,12.f);line(22,12,23,17);line(23,17,23,22);}
    hand.AddBezier(23.f,22.f,23.f,24.4f,21.7f,26.5f,20.f,28.f);line(20,28,12.5f,28);hand.AddBezier(12.5f,28.f,10.5f,26.7f,9.f,25.f,7.8f,23.f);line(7.8f,23,3.6f,17.5f);hand.AddBezier(3.6f,17.5f,2.6f,15.8f,4.6f,13.8f,6.1f,15.1f);line(6.1f,15.1f,10,18);hand.CloseFigure();
    Gdiplus::SolidBrush fill(Gdiplus::Color(255,250,251,254));Gdiplus::Pen outline(Gdiplus::Color(255,30,34,43),1.35f);outline.SetLineJoin(Gdiplus::LineJoinRound);g.FillPath(&fill,&hand);g.DrawPath(&outline,&hand);if(closed){g.DrawLine(&outline,11.f,16.f,19.f,16.f);g.DrawLine(&outline,13.f,19.f,19.f,19.f);}
}

inline POINT cursorHotspot(int slot){
    switch(slot){
    case PEN:case PICKER:return {7,24};       // tip
    case ERASER:return {12,24};              // leading corner of the erasing edge
    case FILL:return {23,26};                // end of the drop
    case MOVE:return {16,16};                // intersection of the four arrows
    case HAND:case GRABBING:return {15,16};
    default:return {8,8};                    // precision crosshair, clear in the middle
    }
}
inline void drawEditCursor(Gdiplus::Graphics& g,int slot){
    const bool precision=precisionTool(slot);
    auto pass=[&](Gdiplus::Color color,float width){
        Gdiplus::Pen pen(color,width);
        pen.SetStartCap(Gdiplus::LineCapRound);pen.SetEndCap(Gdiplus::LineCapRound);
        auto state=g.Save();
        if(precision){
            g.DrawLine(&pen,2.f,8.f,6.f,8.f);g.DrawLine(&pen,10.f,8.f,14.f,8.f);
            g.DrawLine(&pen,8.f,2.f,8.f,6.f);g.DrawLine(&pen,8.f,10.f,8.f,14.f);
            g.TranslateTransform(13.f,13.f);g.ScaleTransform(.76f,.76f);
        }else{
            float offset=slot==MOVE?4.f:3.f;g.TranslateTransform(offset,offset);
        }
        drawToolGlyph(g,ToolId(slot),pen);
        g.Restore(state);
    };
    pass(Gdiplus::Color(255,29,33,42),3.8f);
    pass(Gdiplus::Color(255,251,251,254),1.65f);
}

inline HCURSOR makeCanvasCursor(int slot,int dpi){
    const int size=pf::clamp(GetSystemMetricsForDpi(SM_CXCURSOR,UINT(dpi)),32,96);
    BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);
    info.bmiHeader.biWidth=size;info.bmiHeader.biHeight=-size;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;
    void* pixels=nullptr;auto color=CreateDIBSection(nullptr,&info,DIB_RGB_COLORS,&pixels,nullptr,0);
    if(!color)return nullptr;
    std::memset(pixels,0,size_t(size)*size*4);
    {
        Gdiplus::Bitmap bitmap(size,size,size*4,PixelFormat32bppPARGB,static_cast<BYTE*>(pixels));
        Gdiplus::Graphics g(&bitmap);g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);g.ScaleTransform(size/32.f,size/32.f);
        if(slot==HAND||slot==GRABBING)drawPanCursor(g,slot==GRABBING);else drawEditCursor(g,slot);
        g.Flush(Gdiplus::FlushIntentionSync);
    }
    std::vector<uint8_t> maskBits(size_t((size+15)/16)*2*size,0);
    auto mask=CreateBitmap(size,size,1,1,maskBits.data());if(!mask){DeleteObject(color);return nullptr;}
    auto hot=cursorHotspot(slot);ICONINFO ic{};
    ic.xHotspot=UINT(MulDiv(hot.x,size,32));ic.yHotspot=UINT(MulDiv(hot.y,size,32));ic.hbmColor=color;ic.hbmMask=mask;
    auto cursor=static_cast<HCURSOR>(CreateIconIndirect(&ic));DeleteObject(mask);DeleteObject(color);return cursor;
}

class CanvasCursors {
    std::array<HCURSOR,TOOL_COUNT+1> handles{};
    int density=0;
    void clear(){
        auto active=GetCursor();
        for(auto& h:handles)if(h){
            if(h==active)SetCursor(LoadCursorW(nullptr,IDC_ARROW));
            DestroyCursor(h);h=nullptr;
        }
    }
public:
    CanvasCursors()=default;
    CanvasCursors(const CanvasCursors&)=delete;
    CanvasCursors& operator=(const CanvasCursors&)=delete;
    ~CanvasCursors(){clear();}
    HCURSOR get(int slot,int dpi){
        if(density!=dpi){clear();density=dpi;}
        auto& h=handles[slot];if(!h)h=makeCanvasCursor(slot,dpi);
        return h?h:LoadCursorW(nullptr,(slot==HAND||slot==GRABBING)?IDC_HAND:IDC_CROSS);
    }
};
}
