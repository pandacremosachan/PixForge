#pragma once
#include "pixels.hpp"
#include <numeric>

namespace pf {
constexpr double PI=3.14159265358979323846;
struct Vec {double x=0,y=0,z=0;Vec operator+(Vec b)const{return{x+b.x,y+b.y,z+b.z};}Vec operator-(Vec b)const{return{x-b.x,y-b.y,z-b.z};}Vec operator*(double a)const{return{x*a,y*a,z*a};}double dot(Vec b)const{return x*b.x+y*b.y+z*b.z;}double& at(int i){return i==0?x:i==1?y:z;}};
inline Vec vec(const J& a){return {a[0].number(),a[1].number(),a[2].number()};}
inline double length(Vec a){return std::sqrt(a.dot(a));}
inline std::array<Vec,8> vertices(Vec a,Vec b){return {{{a.x,a.y,a.z},{b.x,a.y,a.z},{b.x,b.y,a.z},{a.x,b.y,a.z},{a.x,a.y,b.z},{b.x,a.y,b.z},{b.x,b.y,b.z},{a.x,b.y,b.z}}};}
struct Face {std::array<Vec,4> points;std::array<std::array<double,2>,4> uv;Vec normal;double shade=1;int element=-1;};
inline Vec normal(const std::string& s){if(s=="north")return {0,0,-1};if(s=="south")return{0,0,1};if(s=="west")return{-1,0,0};if(s=="east")return{1,0,0};if(s=="up")return{0,1,0};return{0,-1,0};}
inline double shade(const std::string& s){return s=="up"?1:s=="down"?.5:(s=="north"||s=="south")?.82:.66;}
inline Vec rotate(Vec p,const J& r,bool isNormal=false){if(r.null())return p;Vec origin=isNormal?Vec{}:vec(r["origin"]);p=p-origin;int axis=r["axis"].str()=="x"?0:r["axis"].str()=="y"?1:2;double a=r["angle"].number()*PI/180,c=std::cos(a),s=std::sin(a);if(r["rescale"].boolean()&&!isNormal)for(int i=0;i<3;++i)if(i!=axis)p.at(i)/=c;int x=(axis+1)%3,y=(axis+2)%3;double xx=p.at(x),yy=p.at(y);p.at(x)=c*xx-s*yy;p.at(y)=s*xx+c*yy;return p+origin;}
inline std::vector<Face> modelMesh(const J& model){
    std::vector<Face> out;if(model.null())return out;
    int element=0;for(auto& e:model["elements"].arr()){
        auto a=vec(e["from"]),b=vec(e["to"]);double x=a.x,y=a.y,z=a.z,X=b.x,Y=b.y,Z=b.z;
        std::map<std::string,std::array<Vec,4>> quads={
            {"north",{{{X,Y,z},{X,y,z},{x,y,z},{x,Y,z}}}},{"south",{{{x,Y,Z},{x,y,Z},{X,y,Z},{X,Y,Z}}}},
            {"west",{{{x,Y,z},{x,y,z},{x,y,Z},{x,Y,Z}}}},{"east",{{{X,Y,Z},{X,y,Z},{X,y,z},{X,Y,z}}}},
            {"up",{{{x,Y,z},{x,Y,Z},{X,Y,Z},{X,Y,z}}}},{"down",{{{x,y,Z},{x,y,z},{X,y,z},{X,y,Z}}}}};
        std::map<std::string,std::array<double,4>> defaults={{"down",{x,16-Z,X,16-z}},{"up",{x,z,X,Z}},{"north",{16-X,16-Y,16-x,16-y}},{"south",{x,16-Y,X,16-y}},{"west",{z,16-Y,Z,16-y}},{"east",{16-Z,16-Y,16-z,16-y}}};
        for(auto& [name,data]:e["faces"].obj()){
            auto u=defaults[name];if(data["uv"].isArray())for(int i=0;i<4;++i)u[i]=data["uv"][i].number();
            Face f;f.element=element;f.points=quads[name];f.uv={{{u[0]/16,u[1]/16},{u[0]/16,u[3]/16},{u[2]/16,u[3]/16},{u[2]/16,u[1]/16}}};
            int shift=data["rotation"].integer()/90;std::rotate(f.uv.begin(),f.uv.begin()+shift,f.uv.end());for(auto& p:f.points)p=rotate(p,e["rotation"]);f.normal=rotate(normal(name),e["rotation"],true);f.shade=e["shade"].boolean(true)?shade(name):1;out.push_back(std::move(f));
        }++element;
    }return out;
}
// The array is owned by shapes. Returning a value here leaves range-for users
// of effective(...).arr() with a dangling reference under our C++20 build.
inline const J& effective(const J& shapes,const std::string& target){return shapes[target].null()?shapes["base"]:shapes[target];}
inline bool hasVisiblePixels(const Image& image){for(size_t i=3;i<image.bytes.size();i+=4)if(image.bytes[i])return true;return false;}
struct Camera {
    Vec center,right,up,depth;double scale=1;int size=400;
    Camera(Vec mid,double radius,int pixels,double yaw,double pitch,double margin,double zoom=1):center(mid),size(pixels){yaw*=PI/180;pitch*=PI/180;right={std::cos(yaw),0,-std::sin(yaw)};up={-std::sin(pitch)*std::sin(yaw),std::cos(pitch),-std::sin(pitch)*std::cos(yaw)};depth={std::cos(pitch)*std::sin(yaw),std::sin(pitch),std::cos(pitch)*std::cos(yaw)};scale=(size-margin)/(2*radius)*zoom;}
    Vec project(Vec p)const{auto v=p-center;return {size/2.+v.dot(right)*scale,size/2.-v.dot(up)*scale,v.dot(depth)};}
};
inline std::pair<Vec,double> shapeBounds(const J& shapes,const std::vector<Face>& mesh){
    std::vector<Vec> points;for(auto& target:{"base","collision","selection"})for(auto& b:effective(shapes,target).arr()){auto vv=vertices(vec(b["from"]),vec(b["to"]));points.insert(points.end(),vv.begin(),vv.end());}for(auto& f:mesh)for(auto p:f.points)points.push_back(p);if(points.empty()){auto vv=vertices({0,0,0},{16,16,16});points.insert(points.end(),vv.begin(),vv.end());}
    Vec lo=points[0],hi=points[0];for(auto p:points)for(int i=0;i<3;++i){lo.at(i)=pf::min(lo.at(i),p.at(i));hi.at(i)=pf::max(hi.at(i),p.at(i));}return{(lo+hi)*.5,pf::max(length(hi-lo)*.5,1.)};
}
#include "scene_math.hpp"
inline Pixel lit(Pixel src,Pixel dst,double s){double a=src[3]/255.;for(int c=0;c<3;++c)dst[c]=uint8_t(rounded(rounded(src[c]*s)*a+dst[c]*(1-a)));dst[3]=255;return dst;}
struct RenderResult {Image image;std::vector<std::array<Vec,2>> lines;std::vector<Pixel> lineColors;};
inline Pixel backgroundPixel(int mode,int x=0,int y=0){return mode==1?Pixel{226,226,226,255}:mode==2?Pixel{25,25,25,255}:mode==0?((x/8+y/8)%2?Pixel{65,70,80,255}:Pixel{55,59,68,255}):Pixel{20,27,37,255};}
inline Image backgroundImage(int width,int height,int mode){Image image(width,height,backgroundPixel(mode));if(mode==0)for(int y=0;y<height;++y)for(int x=0;x<width;++x)image.set(x,y,backgroundPixel(mode,x,y));return image;}
inline RenderResult renderShapes(const J& shapes,const Image& texture,int size,double yaw,double pitch,const std::vector<std::string>& overlays,bool showModel=true,int background=-1,const J& scene=J(),double time=0,double zoom=1,const J& sceneView=J()){
    auto base=modelMesh(shapes["model"]);auto faces=poseMesh(base,scene,time,sceneView);auto [center,radius]=sceneBounds(shapes,base,scene);Camera cam(center,radius,size,yaw,pitch,50,zoom);RenderResult result{backgroundImage(size,size,background)};std::vector<double> depths(size_t(size)*size,-std::numeric_limits<double>::infinity());
    bool emptyTexture=!hasVisiblePixels(texture);if(showModel&&emptyTexture)for(auto& f:faces){if(f.normal.dot(cam.depth)<=1e-9)continue;for(int i=0;i<4;++i){result.lines.push_back({cam.project(f.points[i]),cam.project(f.points[(i+1)%4])});result.lineColors.push_back({153,176,205,255});}}
    if(showModel&&!emptyTexture)for(auto& f:faces){if(f.normal.dot(cam.depth)<=1e-9)continue;std::array<Vec,4> p;for(int i=0;i<4;++i)p[i]=cam.project(f.points[i]);for(auto triangle:{std::array<int,3>{0,1,2},{0,2,3}}){Vec a=p[triangle[0]],b=p[triangle[1]],c=p[triangle[2]];auto ta=f.uv[triangle[0]],tb=f.uv[triangle[1]],tc=f.uv[triangle[2]];double den=(b.y-c.y)*(a.x-c.x)+(c.x-b.x)*(a.y-c.y);if(std::abs(den)<1e-9)continue;
        for(int y=pf::max(0,int(std::floor(pf::min({a.y,b.y,c.y}))));y<pf::min(size,int(std::ceil(pf::max({a.y,b.y,c.y}))));++y)for(int x=pf::max(0,int(std::floor(pf::min({a.x,b.x,c.x}))));x<pf::min(size,int(std::ceil(pf::max({a.x,b.x,c.x}))));++x){double u=((b.y-c.y)*(x+.5-c.x)+(c.x-b.x)*(y+.5-c.y))/den,v=((c.y-a.y)*(x+.5-c.x)+(a.x-c.x)*(y+.5-c.y))/den,w=1-u-v;if(pf::min({u,v,w})<-1e-8)continue;double z=u*a.z+v*b.z+w*c.z;auto index=size_t(y)*size+x;if(z<depths[index]-1e-8)continue;int tx=int(std::floor((u*ta[0]+v*tb[0]+w*tc[0])*texture.w)),ty=int(std::floor((u*ta[1]+v*tb[1]+w*tc[1])*texture.h));tx=(tx%texture.w+texture.w)%texture.w;ty=(ty%texture.h+texture.h)%texture.h;auto rgba=texture.get(tx,ty);if(!rgba[3])continue;result.image.set(x,y,lit(rgba,result.image.get(x,y),f.shade));depths[index]=z;}
    }}
    auto particles=sceneParticles(scene,time,sceneView);std::stable_sort(particles.begin(),particles.end(),[&](auto& a,auto& b){return a.position.dot(cam.depth)<b.position.dot(cam.depth);});
    for(auto& particle:particles){auto p=cam.project(particle.position);double half=particle.size*cam.scale*.5;if(half<=0||particle.color[3]<=0)continue;double alpha=particle.color[3]/255.;
        for(int y=pf::max(0,int(std::ceil(p.y-half-.5)));y<pf::min(size,int(std::ceil(p.y+half-.5)));++y)for(int x=pf::max(0,int(std::ceil(p.x-half-.5)));x<pf::min(size,int(std::ceil(p.x+half-.5)));++x){if(p.z<depths[size_t(y)*size+x]-1e-8)continue;auto pixel=result.image.get(x,y);for(int c=0;c<3;++c)pixel[c]=uint8_t(pf::clamp(rounded(particle.color[c]*alpha+pixel[c]*(particle.additive?1.:1-alpha)),0,255));result.image.set(x,y,pixel);}
    }
    static constexpr int edges[][2]={{0,1},{1,2},{2,3},{3,0},{4,5},{5,6},{6,7},{7,4},{0,4},{1,5},{2,6},{3,7}};
    for(auto& target:overlays)for(auto& box:effective(shapes,target).arr()){auto vv=vertices(vec(box["from"]),vec(box["to"]));for(auto edge:edges){result.lines.push_back({cam.project(vv[edge[0]]),cam.project(vv[edge[1]])});result.lineColors.push_back(target=="base"?Pixel{255,202,104,255}:target=="collision"?Pixel{255,103,139,255}:Pixel{98,229,255,255});}}
    return result;
}
}
