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
    std::array<int,256> table;table.fill(-1);std::string chars="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";for(int i=0;i<64;++i)table[uint8_t(chars[i])]=i;
    std::vector<uint8_t> out;out.reserve(s.size()/4*3);
    for(size_t i=0;i<s.size();i+=4){int a=table[uint8_t(s[i])],b=table[uint8_t(s[i+1])],c=s[i+2]=='='?0:table[uint8_t(s[i+2])],d=s[i+3]=='='?0:table[uint8_t(s[i+3])];if(a<0||b<0||c<0||d<0||(s[i+2]=='='&&s[i+3]!='=')||((s[i+2]=='='||s[i+3]=='=')&&i+4!=s.size()))throw std::runtime_error("Invalid RGBA base64");unsigned n=(a<<18)|(b<<12)|(c<<6)|d;out.push_back(uint8_t(n>>16));if(s[i+2]!='=')out.push_back(uint8_t(n>>8));if(s[i+3]!='=')out.push_back(uint8_t(n));}
    return out;
}
struct Rect {int x=0,y=0,w=0,h=0;bool contains(int a,int b) const{return a>=x&&b>=y&&a<x+w&&b<y+h;}J json()const{return J::array({x,y,w,h});}};
struct Image {
    int w=0,h=0;std::vector<uint8_t> bytes;
    Image()=default;
    Image(int width,int height,Pixel p={0,0,0,0}):w(width),h(height){if(w<1||h<1||w>4096||h>4096)throw std::runtime_error("Invalid image dimensions");bytes.resize(size_t(w)*h*4);fill(p);}
    void fill(Pixel p){for(size_t i=0;i<bytes.size();i+=4)std::memcpy(bytes.data()+i,p.data(),4);}
    Pixel get(int x,int y)const{if(x<0||y<0||x>=w||y>=h)return {0,0,0,0};Pixel out;std::memcpy(out.data(),bytes.data()+(size_t(y)*w+x)*4,4);return out;}
    void set(int x,int y,Pixel p){if(x>=0&&y>=0&&x<w&&y<h)std::memcpy(bytes.data()+(size_t(y)*w+x)*4,p.data(),4);}
    Image crop(Rect r)const{Image out(r.w,r.h);for(int y=0;y<r.h;++y)for(int x=0;x<r.w;++x)out.set(x,y,get(x+r.x,y+r.y));return out;}
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
    static Canvas decode(const J& data){Canvas c;c.w=data["w"].integer();c.h=data["h"].integer();if(c.w<1||c.h<1||c.w>4096||c.h>4096)throw std::runtime_error("Invalid canvas dimensions");c.palette=data["palette"];c.mirror=data["mirror"].boolean();if(!data["layers"].isArray()||data["layers"].size()<1||data["layers"].size()>16)throw std::runtime_error("Invalid layer count");for(auto& v:data["layers"].arr()){Layer l;l.name=v["name"].str();l.visible=v["visible"].boolean(true);l.image=Image(c.w,c.h);l.image.bytes=unbase64(v["data"].str());if(l.image.bytes.size()!=size_t(c.w)*c.h*4)throw std::runtime_error("RGBA byte count mismatch");if(l.name==data["active"].str())c.active=int(c.layers.size());c.layers.push_back(std::move(l));}c.composite();return c;}
    J encode()const{J a=J::array();for(auto& l:layers)a.arr().push_back(J::object({{"name",l.name},{"visible",l.visible},{"data",base64(l.image.bytes)}}));return J::object({{"w",w},{"h",h},{"active",layers.at(active).name},{"mirror",mirror},{"palette",palette},{"layers",a}});}
    void composite(Rect r={}){if(composed.w!=w||composed.h!=h)composed=Image(w,h);if(r.w==0)r={0,0,w,h};int xmax=pf::min(w,r.x+r.w),ymax=pf::min(h,r.y+r.h);for(int y=pf::max(0,r.y);y<ymax;++y){for(int x=pf::max(0,r.x);x<xmax;++x){Pixel p={0,0,0,0};for(auto& l:layers)if(l.visible)p=over(p,l.image.get(x,y));composed.set(x,y,p);}}}
};
inline Pixel color(std::string text){if(text.size()!=7&&text.size()!=9)throw std::runtime_error("RGBA uses #RRGGBB or #RRGGBBAA");if(text[0]!='#')throw std::runtime_error("Color must begin with #");Pixel out={0,0,0,255};for(size_t i=0;i<(text.size()-1)/2;++i){auto t=text.substr(1+i*2,2);char* end=nullptr;long n=std::strtol(t.c_str(),&end,16);if(*end||n<0||n>255)throw std::runtime_error("Invalid color");out[i]=uint8_t(n);}return out;}
inline std::string hexColor(Pixel c){char b[16];std::snprintf(b,sizeof b,"#%02x%02x%02x%02x",c[0],c[1],c[2],c[3]);return b;}
struct Stroke {
    std::string tool="pen";Pixel ink={217,162,106,255};int size=1;double opacity=1;bool mx=false,my=false,solid=false;
    Rect frame,clip;Image before;int sx=0,sy=0,lx=0,ly=0;bool lastValid=true;
    void begin(const Image& image,Rect area,int x,int y){before=image;frame=area;sx=lx=x;sy=ly=y;lastValid=true;}
    Rect draw(Image& image,int px,int py){
        px=pf::clamp(px,frame.x,frame.x+frame.w-1);py=pf::clamp(py,frame.y,frame.y+frame.h-1);
        bool shape=tool=="line"||tool=="rect"||tool=="ellipse";
        if(shape)image=before;
        std::vector<std::pair<int,int>> points;
        auto point=[&](int x,int y){if(frame.contains(x,y))points.emplace_back(x,y);};
        auto stamp=[&](int x,int y){int half=(size-1)/2;for(int b=0;b<size;++b)for(int a=0;a<size;++a)point(x-half+a,y-half+b);};
        auto line=[&](int x0,int y0,int x1,int y1){int d=pf::max({std::abs(x1-x0),std::abs(y1-y0),1});for(int n=0;n<=d;++n)stamp(rounded(x0+(x1-x0)*double(n)/d),rounded(y0+(y1-y0)*double(n)/d));};
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
        Rect dirty={px,py,1,1};int left=frame.x+frame.w,top=frame.y+frame.h,right=frame.x,bottom=frame.y;
        Pixel write=ink;write[3]=uint8_t(rounded(ink[3]*opacity));
        for(auto [x,y]:points)for(int m=0;m<(mx?2:1);++m)for(int n=0;n<(my?2:1);++n){int xx=m?2*frame.x+frame.w-1-x:x,yy=n?2*frame.y+frame.h-1-y:y;if(clip.w&&!clip.contains(xx,yy))continue;Pixel p=write;if(tool=="eraser"){p=opacity>=1?Pixel{0,0,0,0}:before.get(xx,yy);p[3]=uint8_t(rounded(p[3]*(1-opacity)));}image.set(xx,yy,p);left=pf::min(left,xx);top=pf::min(top,yy);right=pf::max(right,xx);bottom=pf::max(bottom,yy);}
        lx=px;ly=py;lastValid=true;if(shape||right<left)return frame;return {left,top,right-left+1,bottom-top+1};
    }
};
}
