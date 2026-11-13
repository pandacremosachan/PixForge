#pragma once
#include "platform.hpp"

namespace pf {
inline Image decodePreviewPng(const std::string& encoded){
    auto bytes=unbase64(encoded);
    auto memory=GlobalAlloc(GMEM_MOVEABLE,bytes.size());
    if(!memory)throw std::runtime_error("PNG allocation failed");
    auto data=GlobalLock(memory);std::memcpy(data,bytes.data(),bytes.size());GlobalUnlock(memory);
    IStream* stream=nullptr;
    if(CreateStreamOnHGlobal(memory,TRUE,&stream)!=S_OK){GlobalFree(memory);throw std::runtime_error("PNG stream failed");}
    Image result;
    {
        Gdiplus::Bitmap bitmap(stream);
        if(bitmap.GetLastStatus()==Gdiplus::Ok&&bitmap.GetWidth()<=4096&&bitmap.GetHeight()<=4096){
            result=Image(int(bitmap.GetWidth()),int(bitmap.GetHeight()));
            Gdiplus::Rect rect(0,0,result.w,result.h);Gdiplus::BitmapData locked{};
            if(bitmap.LockBits(&rect,Gdiplus::ImageLockModeRead,PixelFormat32bppARGB,&locked)==Gdiplus::Ok){
                for(int y=0;y<result.h;++y){
                    auto row=static_cast<const uint8_t*>(locked.Scan0)+ptrdiff_t(y)*locked.Stride;
                    for(int x=0;x<result.w;++x){auto p=row+4*x;result.set(x,y,{p[2],p[1],p[0],p[3]});}
                }
                bitmap.UnlockBits(&locked);
            }
        }
    }
    stream->Release();
    if(!result.w)throw std::runtime_error("PNG decoding failed");
    return result;
}

inline void checkCaptureSource(const fs::path& path,const J& state){
    auto absolute=fs::weakly_canonical(path);
    for(auto key:{"project_path","source_path"})
        if(state[key].isString()&&absolute==fs::weakly_canonical(fs::path(wide(state[key].str()))))
            throw std::runtime_error("Capture cannot replace an artwork source");
}

// PrintWindow supplies the controls. GPU views can draw their canvas into the same bitmap.
inline void captureWindowPng(HWND window,const fs::path& path,const std::function<void(HDC)>& paintCanvas={}){
    RECT r;GetClientRect(window,&r);Image image(r.right,r.bottom);
    HDC dc=GetDC(window),mem=CreateCompatibleDC(dc);
    BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);
    info.bmiHeader.biWidth=image.w;info.bmiHeader.biHeight=-image.h;
    info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;
    void* bits=nullptr;auto bitmap=CreateDIBSection(dc,&info,DIB_RGB_COLORS,&bits,nullptr,0);
    ReleaseDC(window,dc);
    if(!bitmap){DeleteDC(mem);throw std::runtime_error("Capture allocation failed");}
    auto old=SelectObject(mem,bitmap);
    auto ok=PrintWindow(window,mem,PW_CLIENTONLY);
    if(paintCanvas)paintCanvas(mem);
    auto raw=static_cast<const uint8_t*>(bits);
    for(size_t i=0;i<image.bytes.size();i+=4){
        image.bytes[i]=raw[i+2];image.bytes[i+1]=raw[i+1];image.bytes[i+2]=raw[i];image.bytes[i+3]=255;
    }
    SelectObject(mem,old);DeleteObject(bitmap);DeleteDC(mem);
    if(!ok||!savePng(image,path))throw std::runtime_error("Capture failed");
}
}
