#pragma once
#include "platform.hpp"

namespace pf {
// Independently drawn palm cursors: consistent hotspots and per-monitor scale.
inline HCURSOR makePanCursor(int dpi,bool closed){
    int size=pf::clamp(GetSystemMetricsForDpi(SM_CXCURSOR,UINT(dpi)),32,96);BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=size;info.bmiHeader.biHeight=-size;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;void* pixels=nullptr;
    HBITMAP color=CreateDIBSection(nullptr,&info,DIB_RGB_COLORS,&pixels,nullptr,0);if(!color)return nullptr;std::memset(pixels,0,size_t(size)*size*4);
    {Gdiplus::Bitmap bitmap(size,size,size*4,PixelFormat32bppPARGB,static_cast<BYTE*>(pixels));Gdiplus::Graphics g(&bitmap);g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);g.ScaleTransform(size/32.f,size/32.f);Gdiplus::GraphicsPath hand;
        auto line=[&](float a,float b,float c,float d){hand.AddLine(a,b,c,d);};
        if(!closed){line(10,18,10,8);hand.AddBezier(10.f,8.f,10.f,5.f,13.2f,5.f,13.2f,8.f);line(13.2f,8,13.2f,15);line(13.2f,15,13.2f,4.8f);hand.AddBezier(13.2f,4.8f,13.2f,2.f,16.5f,2.f,16.5f,4.8f);line(16.5f,4.8f,16.5f,15);line(16.5f,15,16.5f,6);hand.AddBezier(16.5f,6.f,16.5f,3.3f,19.8f,3.3f,19.8f,6.f);line(19.8f,6,19.8f,16);line(19.8f,16,19.8f,10);hand.AddBezier(19.8f,10.f,19.8f,7.4f,23.f,7.4f,23.f,10.f);line(23,10,23,22);}
        else{line(9,17,9,13);hand.AddBezier(9.f,13.f,9.f,10.f,12.f,10.f,12.f,13.f);line(12,13,12,11);hand.AddBezier(12.f,11.f,12.f,8.f,15.3f,8.f,15.3f,11.f);line(15.3f,11,15.3f,10);hand.AddBezier(15.3f,10.f,15.3f,7.3f,18.6f,7.3f,18.6f,10.f);line(18.6f,10,18.6f,12);hand.AddBezier(18.6f,12.f,18.6f,9.4f,22.f,9.4f,22.f,12.f);line(22,12,23,17);line(23,17,23,22);}
        hand.AddBezier(23.f,22.f,23.f,24.4f,21.7f,26.5f,20.f,28.f);line(20,28,12.5f,28);hand.AddBezier(12.5f,28.f,10.5f,26.7f,9.f,25.f,7.8f,23.f);line(7.8f,23,3.6f,17.5f);hand.AddBezier(3.6f,17.5f,2.6f,15.8f,4.6f,13.8f,6.1f,15.1f);line(6.1f,15.1f,10,18);hand.CloseFigure();
        Gdiplus::SolidBrush fill(Gdiplus::Color(255,250,251,254));Gdiplus::Pen outline(Gdiplus::Color(255,30,34,43),1.35f);outline.SetLineJoin(Gdiplus::LineJoinRound);g.FillPath(&fill,&hand);g.DrawPath(&outline,&hand);if(closed){g.DrawLine(&outline,11.f,16.f,19.f,16.f);g.DrawLine(&outline,13.f,19.f,19.f,19.f);}g.Flush(Gdiplus::FlushIntentionSync);
    }
    std::vector<uint8_t> maskBits(size_t((size+15)/16)*2*size,0);HBITMAP mask=CreateBitmap(size,size,1,1,maskBits.data());if(!mask){DeleteObject(color);return nullptr;}ICONINFO cursor{};cursor.fIcon=FALSE;cursor.xHotspot=UINT(size*15/32);cursor.yHotspot=UINT(size*16/32);cursor.hbmMask=mask;cursor.hbmColor=color;HCURSOR result=static_cast<HCURSOR>(CreateIconIndirect(&cursor));DeleteObject(mask);DeleteObject(color);return result;
}
}
