#pragma once
#include "platform.hpp"

namespace pf {
inline bool openPixelClipboard(HWND owner){for(int attempt=0;attempt<40;++attempt){if(OpenClipboard(owner))return true;Sleep(5);}return false;}
// Exact RGBA is shared by PixForge instances; DIBV5 permits normal Windows
// image applications to receive the same straight-alpha pixels.
inline void copyPixels(HWND owner,const Image& image){
    UINT format=RegisterClipboardFormatW(L"PixForge.RGBA.v1");
    size_t count=image.bytes.size();HGLOBAL exact=GlobalAlloc(GMEM_MOVEABLE,8+count),dib=GlobalAlloc(GMEM_MOVEABLE,sizeof(BITMAPV5HEADER)+count);
    if(!exact||!dib){if(exact)GlobalFree(exact);if(dib)GlobalFree(dib);throw std::runtime_error("Clipboard allocation failed");}
    auto raw=static_cast<uint8_t*>(GlobalLock(exact));uint32_t dimensions[2]={uint32_t(image.w),uint32_t(image.h)};std::memcpy(raw,dimensions,8);std::memcpy(raw+8,image.bytes.data(),count);GlobalUnlock(exact);
    auto header=static_cast<BITMAPV5HEADER*>(GlobalLock(dib));std::memset(header,0,sizeof(*header));header->bV5Size=sizeof(*header);header->bV5Width=image.w;header->bV5Height=-image.h;header->bV5Planes=1;header->bV5BitCount=32;header->bV5Compression=BI_BITFIELDS;header->bV5RedMask=0x00ff0000;header->bV5GreenMask=0x0000ff00;header->bV5BlueMask=0x000000ff;header->bV5AlphaMask=0xff000000;header->bV5CSType=LCS_sRGB;header->bV5SizeImage=DWORD(count);auto bgra=reinterpret_cast<uint8_t*>(header+1);for(size_t i=0;i<count;i+=4){bgra[i]=image.bytes[i+2];bgra[i+1]=image.bytes[i+1];bgra[i+2]=image.bytes[i];bgra[i+3]=image.bytes[i+3];}GlobalUnlock(dib);
    if(!openPixelClipboard(owner)){GlobalFree(exact);GlobalFree(dib);throw std::runtime_error("剪贴板暂时被其他程序占用，请重试");}
    EmptyClipboard();bool ok=SetClipboardData(format,exact)!=nullptr;if(!ok)GlobalFree(exact);if(!SetClipboardData(CF_DIBV5,dib))GlobalFree(dib);CloseClipboard();if(!ok)throw std::runtime_error("Could not publish clipboard pixels");
}
inline Image pastePixels(HWND owner){
    if(!openPixelClipboard(owner))throw std::runtime_error("剪贴板暂时被其他程序占用，请重试");
    struct Close{~Close(){CloseClipboard();}} close;
    auto decodeExact=[&]()->Image{auto data=GetClipboardData(RegisterClipboardFormatW(L"PixForge.RGBA.v1"));if(!data)return{};size_t size=GlobalSize(data);if(size<8)return{};auto raw=static_cast<uint8_t*>(GlobalLock(data));if(!raw)return{};uint32_t dims[2];std::memcpy(dims,raw,8);Image result;if(dims[0]>=1&&dims[1]>=1&&dims[0]<=4096&&dims[1]<=4096&&uint64_t(dims[0])*dims[1]*4<=size-8){result=Image(int(dims[0]),int(dims[1]));std::memcpy(result.bytes.data(),raw+8,result.bytes.size());}GlobalUnlock(data);return result;};
    auto result=decodeExact();if(result.w)return result;
    // External PNG clipboard images retain alpha. GDI+ owns the decoding only.
    if(auto data=GetClipboardData(RegisterClipboardFormatW(L"PNG"))){IStream* stream=nullptr;if(CreateStreamOnHGlobal(data,FALSE,&stream)==S_OK){Gdiplus::Bitmap bitmap(stream);if(bitmap.GetLastStatus()==Gdiplus::Ok&&bitmap.GetWidth()<=4096&&bitmap.GetHeight()<=4096&&bitmap.GetWidth()&&bitmap.GetHeight()){result=Image(int(bitmap.GetWidth()),int(bitmap.GetHeight()));Gdiplus::Rect bounds(0,0,result.w,result.h);Gdiplus::BitmapData bits{};if(bitmap.LockBits(&bounds,Gdiplus::ImageLockModeRead,PixelFormat32bppARGB,&bits)==Gdiplus::Ok){for(int y=0;y<result.h;++y){auto row=static_cast<uint8_t*>(bits.Scan0)+ptrdiff_t(y)*bits.Stride;for(int x=0;x<result.w;++x)result.set(x,y,{row[x*4+2],row[x*4+1],row[x*4],row[x*4+3]});}bitmap.UnlockBits(&bits);}else result={};}stream->Release();}if(result.w)return result;}
    for(UINT format:{UINT(CF_DIBV5),UINT(CF_DIB)}){auto data=GetClipboardData(format);if(!data)continue;size_t size=GlobalSize(data);auto raw=static_cast<uint8_t*>(GlobalLock(data));if(!raw)continue;BITMAPINFOHEADER h{};if(size>=sizeof h)std::memcpy(&h,raw,sizeof h);bool valid=h.biSize>=sizeof h&&h.biSize<=size&&h.biWidth>0&&h.biWidth<=4096&&h.biHeight!=0&&h.biHeight>=-4096&&h.biHeight<=4096&&h.biPlanes==1&&(h.biBitCount==24||h.biBitCount==32)&&(h.biCompression==BI_RGB||h.biCompression==BI_BITFIELDS);size_t offset=h.biSize;bool alpha=false;
        if(valid&&h.biCompression==BI_BITFIELDS){uint32_t masks[4]{};if(h.biSize>=108){std::memcpy(masks,raw+40,16);alpha=masks[3]==0xff000000;}else{if(size-offset<12)valid=false;else{std::memcpy(masks,raw+offset,12);offset+=12;}}valid=valid&&masks[0]==0xff0000&&masks[1]==0xff00&&masks[2]==0xff;}
        if(valid){size_t stride=(size_t(h.biWidth)*h.biBitCount+31)/32*4;int height=std::abs(h.biHeight);valid=stride*height<=size-offset;if(valid){result=Image(h.biWidth,height);for(int y=0;y<height;++y){auto row=raw+offset+size_t(h.biHeight<0?y:height-1-y)*stride;for(int x=0;x<h.biWidth;++x){auto p=row+size_t(x)*(h.biBitCount/8);result.set(x,y,{p[2],p[1],p[0],alpha?p[3]:uint8_t(255)});}}}}
        GlobalUnlock(data);if(result.w)return result;
    }
    throw std::runtime_error("剪贴板没有可粘贴的图像（支持 PNG、24/32 位 DIB 和 PixForge RGBA）");
}
}
