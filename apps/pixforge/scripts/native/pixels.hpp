#pragma once
#include "json.hpp"
#include <array>
#include <cstdint>
#include <cstring>
#include <deque>
#include <limits>

namespace pf {
using Pixel = std::array<uint8_t,4>;
inline int rounded(double n){return int(std::nearbyint(n));}
inline std::string base64(const std::vector<uint8_t>& data){
    static const char* chars="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string out;out.reserve((data.size()+2)/3*4);
    for(size_t i=0;i<data.size();i+=3){unsigned n=unsigned(data[i])<<16;if(i+1<data.size())n|=unsigned(data[i+1])<<8;if(i+2<data.size())n|=data[i+2];out+=chars[n>>18];out+=chars[(n>>12)&63];out+=i+1<data.size()?chars[(n>>6)&63]:'=';out+=i+2<data.size()?chars[n&63]:'=';}
    return out;
}
inline std::vector<uint8_t> unbase64(const std::string& s){
    if(s.size()%4)throw std::runtime_error("Invalid RGBA base64 length");
    static constexpr auto table=[] {std::array<int,256> t;t.fill(-1);constexpr char chars[]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";for(int i=0;i<64;++i)t[uint8_t(chars[i])]=i;return t;}();
    std::vector<uint8_t> out;out.reserve(s.size()/4*3);
    for(size_t i=0;i<s.size();i+=4){int a=table[uint8_t(s[i])],b=table[uint8_t(s[i+1])],c=s[i+2]=='='?0:table[uint8_t(s[i+2])],d=s[i+3]=='='?0:table[uint8_t(s[i+3])];if(a<0||b<0||c<0||d<0||(s[i+2]=='='&&s[i+3]!='=')||((s[i+2]=='='||s[i+3]=='=')&&i+4!=s.size()))throw std::runtime_error("Invalid RGBA base64");unsigned n=(a<<18)|(b<<12)|(c<<6)|d;out.push_back(uint8_t(n>>16));if(s[i+2]!='=')out.push_back(uint8_t(n>>8));if(s[i+3]!='=')out.push_back(uint8_t(n));}
    return out;
}
struct Rect {int x=0,y=0,w=0,h=0;bool contains(int a,int b) const{return a>=x&&b>=y&&a<x+w&&b<y+h;}J json()const{return J::array({x,y,w,h});}};
inline Rect intersect(Rect a,Rect b){
    int x=pf::max(a.x,b.x),y=pf::max(a.y,b.y);
    return {x,y,pf::max(0,pf::min(a.x+a.w,b.x+b.w)-x),pf::max(0,pf::min(a.y+a.h,b.y+b.h)-y)};
}
inline Rect unite(Rect a,Rect b){
    if(!a.w||!a.h)return b;if(!b.w||!b.h)return a;
    int x=pf::min(a.x,b.x),y=pf::min(a.y,b.y);
    return {x,y,pf::max(a.x+a.w,b.x+b.w)-x,pf::max(a.y+a.h,b.y+b.h)-y};
}
struct Image {
    int w=0,h=0;std::vector<uint8_t> bytes;
    Image()=default;
    static size_t byteCount(int w,int h){if(w<1||h<1||w>4096||h>4096)throw std::runtime_error("Invalid image dimensions");return size_t(w)*h*4;}
    Image(int width,int height,Pixel p={0,0,0,0}):w(width),h(height),bytes(byteCount(w,h)){if(p!=Pixel{})fill(p);}
    static Image decode(int width,int height,const std::string& rgba){
        auto count=byteCount(width,height);Image out;out.w=width;out.h=height;out.bytes=unbase64(rgba);
        if(out.bytes.size()!=count)throw std::runtime_error("RGBA byte count mismatch");return out;
    }
    void fill(Pixel p){for(size_t i=0;i<bytes.size();i+=4)std::memcpy(bytes.data()+i,p.data(),4);}
    Pixel get(int x,int y)const{if(x<0||y<0||x>=w||y>=h)return {0,0,0,0};Pixel out;std::memcpy(out.data(),bytes.data()+(size_t(y)*w+x)*4,4);return out;}
    void set(int x,int y,Pixel p){if(x>=0&&y>=0&&x<w&&y<h)std::memcpy(bytes.data()+(size_t(y)*w+x)*4,p.data(),4);}
    Image crop(Rect r)const{
        Image out(r.w,r.h);auto box=intersect(r,{0,0,w,h});
        if(box.w)for(int y=box.y;y<box.y+box.h;++y)std::memcpy(out.bytes.data()+4*(size_t(y-r.y)*r.w+box.x-r.x),bytes.data()+4*(size_t(y)*w+box.x),4*size_t(box.w));
        return out;
    }
    void restore(const Image& source,Rect r){
        for(int y=r.y;y<r.y+r.h;++y){size_t offset=4*(size_t(y)*w+r.x);std::memcpy(bytes.data()+offset,source.bytes.data()+offset,size_t(r.w)*4);}
    }
    bool operator==(const Image& other)const{return w==other.w&&h==other.h&&bytes==other.bytes;}
};
inline Pixel over(Pixel d,Pixel s){
    if(!s[3])return d;if(s[3]==255||!d[3])return s;
    // Pillow's integer straight-alpha compositor, with seven extra coefficient bits.
    unsigned blend=d[3]*(255-s[3]);unsigned oa=s[3]*255+blend;
    unsigned c1=unsigned(s[3])*255*255*128/oa,c2=255*128-c1;
    Pixel p;for(int i=0;i<3;++i){unsigned t=s[i]*c1+d[i]*c2+(0x80<<7);p[i]=uint8_t(((t>>8)+t)>>8>>7);}unsigned roundedAlpha=oa+128;p[3]=uint8_t((roundedAlpha+(roundedAlpha>>8))>>8);return p;
}
struct Layer {std::string name;bool visible=true;Image image;};
struct Canvas {
    int w=0,h=0,active=0;bool mirror=false;J palette=J::object();std::vector<Layer> layers;Image composed;
    static Canvas decode(const J& data){Canvas c;c.w=data["w"].integer();c.h=data["h"].integer();if(c.w<1||c.h<1||c.w>4096||c.h>4096)throw std::runtime_error("Invalid canvas dimensions");c.palette=data["palette"];c.mirror=data["mirror"].boolean();if(!data["layers"].isArray()||data["layers"].size()<1||data["layers"].size()>16)throw std::runtime_error("Invalid layer count");for(auto& v:data["layers"].arr()){Layer l;l.name=v["name"].str();l.visible=v["visible"].boolean(true);l.image=Image::decode(c.w,c.h,v["data"].stringRef());if(l.name==data["active"].str())c.active=int(c.layers.size());c.layers.push_back(std::move(l));}c.composite();return c;}
    J encode()const{J a=J::array();for(auto& l:layers)a.arr().push_back(J::object({{"name",l.name},{"visible",l.visible},{"data",base64(l.image.bytes)}}));return J::object({{"w",w},{"h",h},{"active",layers.at(active).name},{"mirror",mirror},{"palette",palette},{"layers",a}});}
    void composite(Rect r={}){
        if(composed.w!=w||composed.h!=h)composed=Image(w,h);
        r=r.w?intersect(r,{0,0,w,h}):Rect{0,0,w,h};if(!r.w)return;
        for(int y=r.y;y<r.y+r.h;++y){
            size_t offset=(size_t(y)*w+r.x)*4;auto dst=composed.bytes.data()+offset;
            std::memset(dst,0,size_t(r.w)*4);
            for(const auto& layer:layers)if(layer.visible){
                auto src=layer.image.bytes.data()+offset;
                for(int i=0;i<r.w*4;i+=4){if(!src[i+3])continue;
                    if(src[i+3]==255||!dst[i+3]){std::memcpy(dst+i,src+i,4);continue;}
                    Pixel a,b;std::memcpy(a.data(),dst+i,4);std::memcpy(b.data(),src+i,4);auto p=over(a,b);std::memcpy(dst+i,p.data(),4);
                }
            }
        }
    }
};
inline Pixel color(std::string text){if(text.size()!=7&&text.size()!=9)throw std::runtime_error("RGBA uses #RRGGBB or #RRGGBBAA");if(text[0]!='#')throw std::runtime_error("Color must begin with #");Pixel out={0,0,0,255};for(size_t i=0;i<(text.size()-1)/2;++i){auto t=text.substr(1+i*2,2);char* end=nullptr;long n=std::strtol(t.c_str(),&end,16);if(*end||n<0||n>255)throw std::runtime_error("Invalid color");out[i]=uint8_t(n);}return out;}
inline std::string hexColor(Pixel c){char b[16];std::snprintf(b,sizeof b,"#%02x%02x%02x%02x",c[0],c[1],c[2],c[3]);return b;}
struct Stroke {
    std::string tool="pen";Pixel ink={217,162,106,255};int size=1;double opacity=1;bool mx=false,my=false,solid=false;
    Rect frame,clip,previousShape;Image before;int sx=0,sy=0,lx=0,ly=0;bool lastValid=true;
    void begin(const Image& image,Rect area,int x,int y){before=image;frame=area;sx=lx=x;sy=ly=y;lastValid=true;}
    Rect draw(Image& image,int px,int py){
        px=pf::clamp(px,frame.x,frame.x+frame.w-1);py=pf::clamp(py,frame.y,frame.y+frame.h-1);
        bool shape=tool=="line"||tool=="rect"||tool=="ellipse";
        if(shape)image.restore(before,previousShape);
        int left=frame.x+frame.w,top=frame.y+frame.h,right=frame.x-1,bottom=frame.y-1;
        Pixel write=ink;write[3]=uint8_t(rounded(ink[3]*opacity));
        auto point=[&](int x,int y){
            if(!frame.contains(x,y))return;
            for(int m=0;m<(mx?2:1);++m)for(int n=0;n<(my?2:1);++n){
                int xx=m?2*frame.x+frame.w-1-x:x,yy=n?2*frame.y+frame.h-1-y:y;if(clip.w&&!clip.contains(xx,yy))continue;
                Pixel p=write;if(tool=="eraser"){p=opacity>=1?Pixel{}:before.get(xx,yy);p[3]=uint8_t(rounded(p[3]*(1-opacity)));}
                image.set(xx,yy,p);left=pf::min(left,xx);top=pf::min(top,yy);right=pf::max(right,xx);bottom=pf::max(bottom,yy);
            }
        };
        auto line=[&](int x0,int y0,int x1,int y1){
            int dx=x1-x0,dy=y1-y0,d=pf::max(std::abs(dx),std::abs(dy));
            int half=(size-1)/2,previousX=0,previousY=0;
            for(int n=0;n<=d;++n){
                int cx=d?rounded(x0+dx*double(n)/d):x0,cy=d?rounded(y0+dy*double(n)/d):y0;
                int x=cx-half,y=cy-half;
                auto row=[&](int a,int b,int yy){if(yy>=frame.y&&yy<frame.y+frame.h)
                    for(int xx=pf::max(a,frame.x);xx<pf::min(b,frame.x+frame.w);++xx)point(xx,yy);};
                // Consecutive square stamps overlap. Paint just the newly exposed strips.
                if(!n){for(int yy=pf::max(y,frame.y);yy<pf::min(y+size,frame.y+frame.h);++yy)row(x,x+size,yy);}
                else{
                    if(y!=previousY)row(x,x+size,y>previousY?y+size-1:y);
                    if(x!=previousX){
                        int xx=x>previousX?x+size-1:x;
                        for(int yy=pf::max(y,previousY);yy<pf::min(y+size,previousY+size);++yy)point(xx,yy);
                    }
                }
                previousX=x;previousY=y;
            }
        };
        if(tool=="fill"){
            Pixel inkFill=ink;inkFill[3]=uint8_t(rounded(ink[3]*opacity));
            for(int m=0;m<(mx?2:1);++m)for(int n=0;n<(my?2:1);++n){int x=m?2*frame.x+frame.w-1-px:px,y=n?2*frame.y+frame.h-1-py:py;if(clip.w&&!clip.contains(x,y))continue;Pixel target=image.get(x,y);if(target==inkFill)continue;std::deque<std::pair<int,int>> queue;queue.emplace_back(x,y);image.set(x,y,inkFill);while(!queue.empty()){auto [a,b]=queue.front();queue.pop_front();for(auto [dx,dy]:{std::pair<int,int>{1,0},{-1,0},{0,1},{0,-1}}){int xx=a+dx,yy=b+dy;if(frame.contains(xx,yy)&&(!clip.w||clip.contains(xx,yy))&&image.get(xx,yy)==target){image.set(xx,yy,inkFill);queue.emplace_back(xx,yy);}}}}return frame;
        }
        if(tool=="pen"||tool=="eraser")line(lastValid?lx:px,lastValid?ly:py,px,py);
        else if(tool=="line")line(sx,sy,px,py);
        else{
            int x0=pf::min(sx,px),x1=pf::max(sx,px),y0=pf::min(sy,py),y1=pf::max(sy,py);
            if(tool=="rect"){for(int y=y0;y<=y1;++y)for(int x=x0;x<=x1;++x)if(solid||x-x0<size||x1-x<size||y-y0<size||y1-y<size)point(x,y);}
            else {double cx=(x0+x1)*.5,cy=(y0+y1)*.5,rx=(x1-x0+1)*.5,ry=(y1-y0+1)*.5;for(int y=y0;y<=y1;++y)for(int x=x0;x<=x1;++x){double a=(x-cx)/rx,b=(y-cy)/ry;double inrx=pf::max(0.,rx-size),inry=pf::max(0.,ry-size);bool inner=inrx>0&&inry>0&&((x-cx)*(x-cx)/(inrx*inrx)+(y-cy)*(y-cy)/(inry*inry)<1);if(a*a+b*b<=1&&(solid||!inner))point(x,y);}}
        }
        lx=px;ly=py;lastValid=true;
        Rect painted=right<left?Rect{}:Rect{left,top,right-left+1,bottom-top+1};
        if(shape){auto dirty=unite(previousShape,painted);previousShape=painted;return dirty;}return painted;
    }
};
}
