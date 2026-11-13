#pragma once
#include "widgets.hpp"
#include <cctype>

namespace pf {
// Local preview context: expressions are arithmetic, never host-language scripts.
class RigExpression {
    const char* p;double seconds;
    void space(){while(std::isspace((unsigned char)*p))++p;}
    bool take(const char* s){space();size_t n=std::strlen(s);if(std::strncmp(p,s,n))return false;p+=n;return true;}
    double atom(){
        if(take("-"))return -atom();if(take("+"))return atom();if(take("!"))return !atom();
        if(take("(")){auto a=branch();take(")");return a;}
        space();char* end=nullptr;double n=std::strtod(p,&end);if(end!=p){p=end;return n;}
        const char* start=p;while(std::isalnum((unsigned char)*p)||*p=='_'||*p=='.')++p;
        std::string id(start,p);if(id.empty())return 0;
        if(take("(")){std::vector<double> args;if(!take(")")){do{args.push_back(branch());}while(take(","));take(")");}
            double a=args.empty()?0:args[0],b=args.size()>1?args[1]:0,c=args.size()>2?args[2]:0;
            if(id=="math.sin")return std::sin(a*PI/180);if(id=="math.cos")return std::cos(a*PI/180);
            if(id=="math.abs")return std::abs(a);if(id=="math.min")return pf::min(a,b);if(id=="math.max")return pf::max(a,b);
            if(id=="math.sqrt")return std::sqrt(pf::max(0.,a));if(id=="math.exp")return std::exp(a);
            if(id=="math.clamp")return pf::clamp(a,b,c);if(id=="math.lerp")return a+(b-a)*c;return 0;
        }
        if(id=="query.anim_time"||id=="q.anim_time"||id=="query.life_time"||id=="q.life_time")return seconds;
        if(id=="ysm.food_level"||id=="ysm.health")return 20;return 0;
    }
    double product(){double a=atom();for(;;){if(take("*"))a*=atom();else if(take("/")){double b=atom();a=b?a/b:0;}else return a;}}
    double sum(){double a=product();for(;;){if(take("+"))a+=product();else if(take("-"))a-=product();else return a;}}
    double compare(){double a=sum();if(take("<="))return a<=sum();if(take(">="))return a>=sum();if(take("=="))return a==sum();if(take("!="))return a!=sum();if(take("<"))return a<sum();if(take(">"))return a>sum();return a;}
    double branch(){double a=compare();if(take("?")){double b=branch();take(":");double c=branch();return a?b:c;}return a;}
public: RigExpression(const char* s,double t):p(s),seconds(t){} double value(){auto n=branch();return std::isfinite(n)?n:0;}
};
inline double rigScalar(const J& value,double at){if(value.isNumber())return value.number();if(!value.isString())return 0;auto& s=std::get<std::string>(value.v);return RigExpression(s.c_str(),at).value();}
inline double rigPoint(const J& key,int axis,bool post,double at){auto& arr=key["data_points"];if(arr.empty())return 0;return rigScalar(arr[post?arr.size()-1:0][std::string(1,"xyz"[axis])],at);}
inline double rigCubic(double a,double b,double c,double d,double t){double q=1-t;return q*q*q*a+3*q*q*t*b+3*q*t*t*c+t*t*t*d;}
inline double rigHandle(const J& k,const char* name,int axis,double fallback){return k[name].isArray()&&k[name].size()>size_t(axis)?k[name][axis].number():fallback;}
inline double rigValue(const J& ks,int axis,double sec,bool loop,double fallback){
    if(ks.empty())return fallback;auto& arr=ks.arr();auto it=std::lower_bound(arr.begin(),arr.end(),sec,[](const J& k,double x){return k["time"].number()<x;});
    if(it==arr.begin()||(it!=arr.end()&&std::abs((*it)["time"].number()-sec)<1e-8))return rigPoint(*it,axis,false,sec);
    if(it==arr.end())return rigPoint(arr.back(),axis,true,sec);
    const auto& a=*(it-1);const auto& b=*it;double t0=a["time"].number(),t1=b["time"].number(),t=(sec-t0)/(t1-t0),v0=rigPoint(a,axis,true,sec),v1=rigPoint(b,axis,false,sec);
    auto sa=a["interpolation"].str(),sb=b["interpolation"].str();
    if(sa=="step")return v0;
    if(sa=="catmullrom"||sb=="catmullrom"){
        double l=v0,r=v1;
        if(a["data_points"].size()==1){if(it-1!=arr.begin())l=rigPoint(*(it-2),axis,true,sec);else if(loop&&arr.size()>2)l=rigPoint(arr[arr.size()-2],axis,true,sec);}
        if(b["data_points"].size()==1){if(it+1!=arr.end())r=rigPoint(*(it+1),axis,false,sec);else if(loop&&arr.size()>2)r=rigPoint(arr[1],axis,false,sec);}
        double m=(v1-l)*.5,n=(r-v0)*.5;return (2*v0-2*v1+m+n)*t*t*t+(-3*v0+3*v1-2*m-n)*t*t+m*t+v0;
    }
    if(sa=="bezier"||sb=="bezier"){
        double x1=t0+pf::clamp(rigHandle(a,"bezier_right_time",axis,.1),0.,t1-t0),x2=t1+pf::clamp(rigHandle(b,"bezier_left_time",axis,-.1),t0-t1,0.);
        double lo=0,hi=1;for(int i=0;i<22;++i){double f=(lo+hi)/2;if(rigCubic(t0,x1,x2,t1,f)<sec)lo=f;else hi=f;}
        return rigCubic(v0,v0+rigHandle(a,"bezier_right_value",axis,0),v1+rigHandle(b,"bezier_left_value",axis,0),v1,(lo+hi)/2);
    }
    return v0+(v1-v0)*t;
}
struct RigMatrix {
    Vec col[3]={{1,0,0},{0,1,0},{0,0,1}},offset{};
    Vec dir(Vec v)const{return col[0]*v.x+col[1]*v.y+col[2]*v.z;}
    Vec point(Vec p)const{return dir(p)+offset;}
    RigMatrix after(const RigMatrix& local)const{RigMatrix m;for(int i=0;i<3;++i)m.col[i]=dir(local.col[i]);m.offset=point(local.offset);return m;}
    static RigMatrix transform(Vec pivot,Vec rot,Vec scale,Vec pos={}){
        double x=rot.x*PI/180,y=rot.y*PI/180,z=rot.z*PI/180,A=std::cos(x),B=std::sin(x),C=std::cos(y),D=std::sin(y),E=std::cos(z),F=std::sin(z);
        RigMatrix m;m.col[0]=Vec{C*E,C*F,-D}*scale.x;m.col[1]=Vec{B*D*E-A*F,B*D*F+A*E,B*C}*scale.y;
        m.col[2]=Vec{A*D*E+B*F,A*D*F-B*E,A*C}*scale.z;m.offset=pivot+pos-m.dir(pivot);return m;
    }
};
inline Vec rigFlip(Vec p){return {-p.x,p.y,-p.z};}
struct RigVisual {
    struct Bone{std::string id,name;int parent;Vec pivot,rot;bool visible;};
    struct Cube{std::string id,name;int bone;RigMatrix bind;bool visible;};
    std::vector<Bone> bones;std::map<std::string,int> ids;std::vector<Cube> cubes;
    std::vector<Face> base,faces;std::vector<std::array<double,4>> localUV;std::vector<RigMatrix> world;std::vector<Vec> pivots;
    std::vector<Rect> textures;std::vector<PickId> hits;int sheetW=1,sheetH=1;bool modernKeys=false;Bounds modelBounds;Vec center;double radius=1;
    void loadSkeleton(const J& model){
        bones.clear();ids.clear();cubes.clear();const auto& rig=model["player_rig"];modernKeys=rig["key_axes"].str()=="model";
        for(auto& b:rig["bones"].arr()){
            std::string id=b["uuid"].str();int parent=b["parent_id"].isString()?ids.at(b["parent_id"].str()):-1;
            ids[id]=int(bones.size());bones.push_back({id,b["name"].str(),parent,rigFlip(vec(b["pivot"])),rigFlip(vec(b["rotation"])),b["visible"].boolean(true)&&(parent<0||bones[parent].visible)});
        }
        for(auto& e:model["elements"].arr()){
            int bi=ids.at(e["bone"].str());cubes.push_back({e["uuid"].str(),e["name"].str(),bi,RigMatrix::transform(rigFlip(vec(e["pivot"])),rigFlip(vec(e["turn"])),{1,1,1}),bones[bi].visible&&e["visible"].boolean(true)});
        }
    }
    void load(const J& model){
        loadSkeleton(model);localUV.clear();textures.clear();
        for(const auto& e:model["elements"].arr()){
            for(auto& [name,f]:e["faces"].obj()){const auto& u=e["local_uv"][name];localUV.push_back({u[0].number(),u[1].number(),u[2].number(),u[3].number()});}
        }
        for(auto& t:model["player_rig"]["textures"].arr())textures.push_back({t["rect"][0].integer(),t["rect"][1].integer(),t["rect"][2].integer(),t["rect"][3].integer()});sheetW=model["texture_size"][0].integer();sheetH=model["texture_size"][1].integer();
        base=modelMesh(model);pose(J(),0,false,-1);
        modelBounds={};for(const auto& f:faces)for(auto p:f.points)modelBounds.include(p);
        auto bounds=modelBounds.sphere();center=bounds.first;radius=bounds.second;
    }
    void poseSkeleton(const J& tracks,double sec,bool loop,int dragBone=-1,int axis=0,double delta=0,const std::string& channel="rotation"){
        world.resize(bones.size());pivots.resize(bones.size());
        for(int i=0;i<int(bones.size());++i){
            auto& b=bones[i];const J& ch=tracks[b.id];Vec r=b.rot,p{},s{};
            for(int j=0;j<3;++j){int sign=modernKeys?(j==1?1:-1):(j==0?1:-1);r.at(j)+=sign*(rigValue(ch["rotation"],j,sec,loop,0)+(i==dragBone&&j==axis&&channel=="rotation"?delta:0));
                p.at(j)=((j==2||(j==0&&modernKeys))?-1:1)*(rigValue(ch["position"],j,sec,loop,0)+(i==dragBone&&j==axis&&channel=="position"?delta:0));
                s.at(j)=rigValue(ch["scale"],j,sec,loop,1)+(i==dragBone&&j==axis&&channel=="scale"?delta:0);}
            auto m=RigMatrix::transform(b.pivot,r,s,p);world[i]=b.parent<0?m:world[b.parent].after(m);pivots[i]=world[i].point(b.pivot);
        }
    }
    void pose(const J& tracks,double sec,bool loop,int texture,int dragBone=-1,int axis=0,double delta=0,const std::string& channel="rotation"){
        poseSkeleton(tracks,sec,loop,dragBone,axis,delta,channel);
        faces.clear();faces.reserve(base.size());
        // modelMesh emits each cube's faces consecutively.
        int lastCube=-1;RigMatrix m;
        for(size_t i=0;i<base.size();++i){const auto& source=base[i];const auto& cube=cubes[source.element];if(!cube.visible)continue;
            if(source.element!=lastCube){m=world[cube.bone].after(cube.bind);lastCube=source.element;}
            auto& f=faces.emplace_back(source);
            for(auto& p:f.points)p=m.point(p);auto u=f.points[1]-f.points[0],v=f.points[2]-f.points[0];Vec n={u.y*v.z-u.z*v.y,u.z*v.x-u.x*v.z,u.x*v.y-u.y*v.x};if(n.dot(m.dir(f.normal))<0)n=n*(-1);f.normal=n;
            if(texture>=0){auto rect=textures.at(texture);auto a=localUV[i];int shift=base[i].uvTurn;
                f.uv={{{a[0],a[1]},{a[0],a[3]},{a[2],a[3]},{a[2],a[1]}}};std::rotate(f.uv.begin(),f.uv.begin()+shift,f.uv.end());
                for(auto& uv:f.uv){uv[0]=(rect.x+uv[0]*rect.w)/sheetW;uv[1]=(rect.y+uv[1]*rect.h)/sheetH;}
            }
        }
    }
    J sample(double ms,const std::string& clip)const{
        J parts=J::array(),joints=J::array();
        for(size_t i=0;i<bones.size();++i)joints.arr().push_back(J::object({{"bone",bones[i].name},{"uuid",bones[i].id},{"pivot",sceneVector(pivots[i])}}));
        for(size_t i=0;i<cubes.size();++i){auto& c=cubes[i];auto m=world[c.bone].after(c.bind);J basis=J::array();
            for(Vec v:{Vec{1,0,0},Vec{0,1,0},Vec{0,0,1}})basis.arr().push_back(sceneVector(m.point(v)));
            parts.arr().push_back(J::object({{"element",i},{"uuid",c.id},{"origin",sceneVector(m.offset)},{"basis",basis}}));}
        return J::object({{"scene_state",clip},{"time_ms",ms},{"parts",parts},{"joints",joints},{"particles",J::array()}});
    }
    Image draw(const Image& atlas,int size,double yaw,double pitch,double zoom,bool pick,bool show,
               const J& shapes,const std::vector<std::string>& overlays){
        auto bounds=modelBounds;
        for(const auto& name:overlays)for(const auto& b:effective(shapes,name).arr()){
            bounds.include(vec(b["from"]));bounds.include(vec(b["to"]));
        }
        auto frame=bounds.sphere();center=frame.first;radius=frame.second;
        Camera camera(center,radius,size,yaw,pitch,pf::min(40,size*.10),zoom);
        return rasterMesh(shapes,atlas,size,overlays,show,3,J(),0,J(),faces,camera,pick?&hits:nullptr).compose();
    }
};
}

