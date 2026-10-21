#pragma once
#include "render.hpp"
#include <set>
#include <limits>

namespace pf {
struct McLayer {bool mipmapped=false,blend=false,depthWrite=true,additive=false;double cutoff=0;int pass=0;bool textureAlpha=false;};
struct McTexture {std::string id,hash;std::vector<Image> levels;};
struct McFace {std::array<Vec,4> points;std::array<std::array<double,2>,4> uv;std::array<std::array<double,4>,4> colors;int texture=0;McLayer layer;bool twoSided=false;};
struct McParticle {Vec position;double size=0;std::array<double,4> color;bool additive=false;};
struct McCamera {double yaw=30,pitch=25,distance=64,zoom=1,fov=40;bool perspective=true;};

inline std::vector<Image> mcMipmaps(Image base,int requested){
    static const auto power=[] {std::array<float,256> table{};for(int i=0;i<256;++i)table[i]=float(std::pow(double(float(i)/255.f),2.2));return table;}();
    bool transparent=false;for(size_t i=3;i<base.bytes.size();i+=4)if(base.bytes[i]==0){transparent=true;break;}
    int maximum=0;for(int n=pf::min(base.w,base.h);n>1;n>>=1)++maximum;
    std::vector<Image> levels;levels.push_back(std::move(base));
    for(int level=1;level<=pf::min(requested,maximum);++level){
        const auto& source=levels.back();Image next(pf::max(1,source.w/2),pf::max(1,source.h/2));
        for(int y=0;y<next.h;++y)for(int x=0;x<next.w;++x){
            std::array<Pixel,4> pixels={source.get(x*2,y*2),source.get(x*2+1,y*2),source.get(x*2,y*2+1),source.get(x*2+1,y*2+1)};
            Pixel output{};for(int c=0;c<4;++c){float sum=0;for(auto p:pixels)if(!transparent||p[3])sum+=power[p[c]];
                double decoded=std::pow(double(sum/4.f),1/2.2);if(!transparent)decoded=double(float(decoded));output[c]=uint8_t(pf::clamp(int(decoded*255.),0,255));}
            if(transparent&&output[3]<96)output[3]=0;next.set(x,y,output);
        }levels.push_back(std::move(next));
    }return levels;
}

struct McScene {
    J source,options;std::vector<McTexture> textures;std::vector<McFace> faces;std::vector<McParticle> particles;
    Vec center;bool item=false,sort=true;int requestedMips=4,forcedMip=-1;Pixel background{55,59,68,255};McCamera camera;
    explicit McScene(J bundle):source(std::move(bundle)){
        if(source["schema"].str()!="pixforge.minecraft-scene/v1"||!source["validation"]["passed"].boolean())throw std::runtime_error("Minecraft scene bundle is not valid");
        options=source["options"];item=options["context"].str()!="block";sort=options["sort_translucent"].boolean();requestedMips=options["mipmap_levels"].integer(4);forcedMip=options["mip_level"].integer(-1);background=color(options["background"].str("#373b44"));
        auto c=options["camera"];camera={c["yaw"].number(),c["pitch"].number(),c["distance"].number(64),c["zoom"].number(1),c["fov"].number(40),c["projection"].str()=="perspective"};
        if(!item)center=(vec(source["bounds"][0])+vec(source["bounds"][1]))*.5;
        std::map<std::string,int> indices;size_t pixels=0;
        for(const auto& t:source["textures"].arr()){
            int w=t["width"].integer(),h=t["height"].integer();if(w<1||h<1||w>4096||h>4096)throw std::runtime_error("Minecraft texture dimensions are invalid");
            pixels+=size_t(w)*h;if(pixels>8388608||textures.size()>=256)throw std::runtime_error("Minecraft scene exceeds texture budget");
            auto bytes=unbase64(t["rgba"].str());if(bytes.size()!=size_t(w)*h*4)throw std::runtime_error("Minecraft RGBA byte count differs from dimensions");
            Image image(w,h);image.bytes=std::move(bytes);indices[t["id"].str()]=int(textures.size());textures.push_back({t["id"].str(),t["sha256"].str(),mcMipmaps(std::move(image),requestedMips)});
        }
        for(const auto& f:source["faces"].arr()){
            McFace face;for(int i=0;i<4;++i){face.points[i]=vec(f["points"][i]);for(int n=0;n<2;++n)face.uv[i][n]=f["uv"][i][n].number();for(int n=0;n<4;++n)face.colors[i][n]=f["colors"][i][n].number();}
            auto found=indices.find(f["texture"].str());if(found==indices.end())throw std::runtime_error("Minecraft face texture is absent");face.texture=found->second;face.twoSided=f["double_sided"].boolean();const auto& layer=f["layer"];
            face.layer={layer["mipmapped"].boolean(),layer["blend"].boolean(),layer["depth_write"].boolean(true),false,layer["alpha_cutoff"].number(),!item&&layer["name"].str()=="tripwire"?2:layer["blend"].boolean()?1:0,layer["alpha_test_texture_only"].boolean()};faces.push_back(std::move(face));
        }
        if(faces.size()>16384)throw std::runtime_error("Minecraft scene exceeds face budget");
        for(const auto& p:source["particles"].arr()){McParticle particle;particle.position=vec(p["position"]);particle.size=p["size"].number();for(int i=0;i<4;++i)particle.color[i]=p["color"][i].number();particle.additive=p["blend"].str()=="additive";particles.push_back(particle);}
        if(!particles.empty()){Image white(1,1,{255,255,255,255});textures.push_back({"$particle","white",{white}});}
    }
};

struct McProjection {
    Vec right,up,depth,eye,center;double scale=1,distance=64,halfHeight=8;bool perspective=true;int width=0,height=0;
    McProjection(const McScene& scene,const McCamera& camera,int w,int h):center(scene.center),distance(camera.distance),perspective(camera.perspective),width(w),height(h){
        double yaw=camera.yaw*PI/180,pitch=camera.pitch*PI/180;
        right={std::cos(yaw),0,-std::sin(yaw)};up={-std::sin(pitch)*std::sin(yaw),std::cos(pitch),-std::sin(pitch)*std::cos(yaw)};depth={std::cos(pitch)*std::sin(yaw),std::sin(pitch),std::cos(pitch)*std::cos(yaw)};
        eye=center+depth*distance;halfHeight=(scene.item?8.:distance*std::tan(camera.fov*PI/360))/camera.zoom;
        scale=perspective?h*.5/std::tan(camera.fov*PI/360)*camera.zoom:h*.5/halfHeight;
    }
    Vec view(Vec point)const{auto p=point-center;return{p.dot(right),p.dot(up),distance-p.dot(depth)};}
};

inline Vec mcCross(Vec a,Vec b){return{a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};}
inline std::vector<McFace> mcDrawFaces(const McScene& scene,const McProjection& camera){
    auto faces=scene.faces;
    for(auto& particle:scene.particles){auto p=particle.position,r=camera.right*(particle.size*.5),u=camera.up*(particle.size*.5);McFace face;face.points={p-r+u,p-r-u,p+r-u,p+r+u};face.uv={{{0,0},{0,1},{1,1},{1,0}}};face.colors.fill(particle.color);face.texture=int(scene.textures.size())-1;face.twoSided=true;face.layer={false,true,!particle.additive,particle.additive,.1,3};faces.push_back(face);}
    auto distance=[&](const McFace& f){Vec mid{};for(auto p:f.points)mid=mid+p*.25;auto d=mid-camera.eye;return d.dot(d);};
    std::stable_sort(faces.begin(),faces.end(),[&](const auto& a,const auto& b){if(a.layer.pass!=b.layer.pass)return a.layer.pass<b.layer.pass;if(scene.sort&&(a.layer.pass==1||a.layer.pass==2))return distance(a)>distance(b);return false;});return faces;
}

struct McRenderMetrics {int triangles=0;uint64_t fragments=0;std::set<int> mips;J json()const{J used=J::array();for(int n:mips)used.arr().push_back(n);return J::object({{"triangles",triangles},{"fragments",fragments},{"mipmap_levels_used",used}});}};
struct McVertex {Vec p;std::array<double,2> uv;std::array<double,4> color;};
inline std::vector<McVertex> mcNearClip(const std::vector<McVertex>& vertices){
    std::vector<McVertex> out;for(size_t i=0;i<vertices.size();++i){auto& a=vertices[(i+vertices.size()-1)%vertices.size()];auto& b=vertices[i];if((a.p.z>=.1)!=(b.p.z>=.1)){double t=(.1-a.p.z)/(b.p.z-a.p.z);McVertex v;v.p=a.p+(b.p-a.p)*t;for(int n=0;n<2;++n)v.uv[n]=a.uv[n]+(b.uv[n]-a.uv[n])*t;for(int n=0;n<4;++n)v.color[n]=a.color[n]+(b.color[n]-a.color[n])*t;out.push_back(v);}if(b.p.z>=.1)out.push_back(b);}return out;
}
inline std::array<double,4> mcSample(const McTexture& texture,double u,double v,double lod,int maximum){
    int limit=pf::min(int(texture.levels.size())-1,maximum);lod=pf::clamp(lod,0.,double(limit));int lo=int(lod);double fraction=lod-lo;std::array<Pixel,2> pixels{};
    for(int i=0;i<2;++i){auto& image=texture.levels[pf::min(lo+i,limit)];int x=pf::clamp(int(std::floor(u*image.w)),0,image.w-1),y=pf::clamp(int(std::floor(v*image.h)),0,image.h-1);pixels[i]=image.get(x,y);}
    std::array<double,4> out;for(int i=0;i<4;++i)out[i]=pixels[0][i]+(pixels[1][i]-pixels[0][i])*fraction;return out;
}

inline Image mcRaster(const McScene& scene,const McCamera& camera,int width,int height,McRenderMetrics* metrics=nullptr){
    McRenderMetrics localMetrics;auto& stats=metrics?*metrics:localMetrics;Image out(width,height,scene.background);std::vector<double> depths(size_t(width)*height,std::numeric_limits<double>::infinity());McProjection projection(scene,camera,width,height);
    struct V {double x,y,z,q;std::array<double,2> uv;std::array<double,4> color;};
    auto edge=[](const V& a,const V& b,double x,double y){return(b.x-a.x)*(y-a.y)-(b.y-a.y)*(x-a.x);};
    auto topLeft=[](const V& a,const V& b){double dy=b.y-a.y,dx=b.x-a.x;return dy<0||(std::abs(dy)<1e-10&&dx>0);};
    for(auto& face:mcDrawFaces(scene,projection)){
        Vec normal=mcCross(face.points[1]-face.points[0],face.points[2]-face.points[0]);if(!face.twoSided&&normal.dot(projection.eye-face.points[0])<=1e-9)continue;
        std::vector<McVertex> vertices;for(int i=0;i<4;++i)vertices.push_back({projection.view(face.points[i]),face.uv[i],face.colors[i]});vertices=mcNearClip(vertices);if(vertices.size()<3)continue;
        std::vector<V> points;for(auto& v:vertices){double q=projection.perspective?1/v.p.z:1;points.push_back({width*.5+v.p.x*projection.scale*q,height*.5-v.p.y*projection.scale*q,v.p.z,q,v.uv,v.color});}
        const auto& texture=scene.textures[face.texture];bool mipped=face.layer.mipmapped&&scene.requestedMips>0;int maxLevel=mipped?int(texture.levels.size())-1:0;
        for(size_t triangle=1;triangle+1<points.size();++triangle){std::array<V,3> p={points[0],points[triangle],points[triangle+1]};double area=edge(p[0],p[1],p[2].x,p[2].y);if(std::abs(area)<1e-9)continue;if(area<0){std::swap(p[1],p[2]);area=-area;}++stats.triangles;
            int loX=pf::max(0,int(std::ceil(pf::min({p[0].x,p[1].x,p[2].x})-.5))),hiX=pf::min(width-1,int(std::floor(pf::max({p[0].x,p[1].x,p[2].x})-.5)));
            int loY=pf::max(0,int(std::ceil(pf::min({p[0].y,p[1].y,p[2].y})-.5))),hiY=pf::min(height-1,int(std::floor(pf::max({p[0].y,p[1].y,p[2].y})-.5)));
            std::array<double,3> dx={(p[1].y-p[2].y)/area,(p[2].y-p[0].y)/area,(p[0].y-p[1].y)/area},dy={(p[2].x-p[1].x)/area,(p[0].x-p[2].x)/area,(p[1].x-p[0].x)/area};
            std::array<double,3> qs{},us{},vs{};double qx=0,qy=0,ux=0,uy=0,vx=0,vy=0;for(int i=0;i<3;++i){qs[i]=p[i].q;us[i]=p[i].uv[0]*qs[i];vs[i]=p[i].uv[1]*qs[i];qx+=dx[i]*qs[i];qy+=dy[i]*qs[i];ux+=dx[i]*us[i];uy+=dy[i]*us[i];vx+=dx[i]*vs[i];vy+=dy[i]*vs[i];}
            std::array<bool,3> inclusive={topLeft(p[1],p[2]),topLeft(p[2],p[0]),topLeft(p[0],p[1])};
            for(int y=loY;y<=hiY;++y)for(int x=loX;x<=hiX;++x){std::array<double,3> w={edge(p[1],p[2],x+.5,y+.5),edge(p[2],p[0],x+.5,y+.5),edge(p[0],p[1],x+.5,y+.5)};bool inside=true;for(int i=0;i<3;++i)if(w[i]<-1e-8||(std::abs(w[i])<=1e-8&&!inclusive[i]))inside=false;if(!inside)continue;
                for(auto& n:w)n/=area;double q=0,u=0,v=0,z=0;for(int i=0;i<3;++i){q+=w[i]*qs[i];u+=w[i]*us[i];v+=w[i]*vs[i];z+=w[i]*p[i].z;}if(q<=0)continue;if(projection.perspective)z=1/q;size_t at=size_t(y)*width+x;if(z>depths[at]+1e-7)continue;
                double lod=0;if(mipped){if(scene.forcedMip>=0)lod=scene.forcedMip;else{double dux=(ux*q-u*qx)/(q*q)*texture.levels[0].w,duy=(uy*q-u*qy)/(q*q)*texture.levels[0].w,dvx=(vx*q-v*qx)/(q*q)*texture.levels[0].h,dvy=(vy*q-v*qy)/(q*q)*texture.levels[0].h;lod=std::log2(pf::max({1.,std::hypot(dux,dvx),std::hypot(duy,dvy)}));}}
                auto texel=mcSample(texture,u/q,v/q,lod,maxLevel);std::array<double,4> color{};for(int c=0;c<4;++c)for(int i=0;i<3;++i)color[c]+=w[i]*p[i].color[c]*qs[i]/q;double alpha=texel[3]/255*color[3];if((face.layer.textureAlpha?texel[3]/255:alpha)+1e-10<face.layer.cutoff)continue;
                Pixel pixel{0,0,0,255},old=out.get(x,y);for(int c=0;c<3;++c){double value=texel[c]*color[c];if(face.layer.blend)value=value*alpha+old[c]*(face.layer.additive?1.:1-alpha);pixel[c]=uint8_t(pf::clamp(int(value+.5),0,255));}out.set(x,y,pixel);if(face.layer.depthWrite)depths[at]=z;++stats.fragments;stats.mips.insert(pf::clamp(int(lod),0,maxLevel));
            }
        }
    }return out;
}
}
