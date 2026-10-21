#pragma once
// Included by render.hpp inside namespace pf. No Python, RPC or system input.
#include "scene_curves.hpp"

inline Vec sceneClipTransform(const J& scene,int element,Vec p,double time,bool isNormal=false,const J& view=J()){
    if(scene.null())return p;
    for(auto& track:scene["transforms"].arr()){
        bool applies=false;for(auto& id:track["elements"].arr())if(id.integer()==element)applies=true;if(!applies)continue;
        double phase=track["phase_deg"].number()*PI/180,t=time/scene["duration_ms"].number();Vec pivot=isNormal?Vec{}:vec(track["pivot"]);auto type=track["type"].str();
        bool advanced=track.contains("entry")||track["keyframes"].isArray();auto value=advanced?sceneTrackValue(track,scene["duration_ms"].number(),sceneTime(scene,time),view["entry_values"],view["first_cycle"].boolean(true)&&time>=0&&time<scene["duration_ms"].number()):J();
        if(type=="rotate"){
            p=p-pivot;auto axis=vec(track["axis"]);double angle=advanced?value.number()*PI/180:phase+2*PI*track["turns"].number()*t,c=std::cos(angle),s=std::sin(angle);
            Vec cross{axis.y*p.z-axis.z*p.y,axis.z*p.x-axis.x*p.z,axis.x*p.y-axis.y*p.x};p=pivot+p*c+cross*s+axis*(axis.dot(p)*(1-c));
        }else{
            double wave=std::sin(phase+2*PI*track["cycles"].number(1)*t);auto motion=advanced?vec(value):vec(track["amplitude"])*wave;
            if(type=="translate"){if(!isNormal)p=p+motion;}
            else for(int i=0;i<3;++i){double scale=advanced?motion.at(i):1+motion.at(i);p.at(i)=pivot.at(i)+(p.at(i)-pivot.at(i))*(isNormal?1/scale:scale);}
        }
    }
    if(isNormal&&length(p)>1e-12)p=p*(1/length(p));return p;
}
inline double sceneRandom(uint32_t seed){seed^=seed>>16;seed*=0x7feb352dU;seed^=seed>>15;seed*=0x846ca68bU;seed^=seed>>16;return seed/4294967296.;}
struct SceneParticle{std::string emitter;int birth=0;double age=0;Vec position;double size=0;std::array<double,4> color{};bool additive=false;Vec velocity,gravity;double remaining=0,endSize=0;std::array<double,4> endColor{};};
inline J sceneParticleJson(const SceneParticle& p,bool raw=false){
    J color=J::array();for(double c:p.color)color.arr().push_back(c);J out=J::object({{"emitter",p.emitter},{"birth_id",p.birth},{"age_ms",p.age},{"position",sceneVector(p.position)},{"size",p.size},{"color",color},{"blend",p.additive?"additive":"alpha"}});
    if(raw){J end=J::array();for(double c:p.endColor)end.arr().push_back(c);out["_velocity"]=sceneVector(p.velocity);out["_gravity"]=sceneVector(p.gravity);out["_remaining_ms"]=p.remaining;out["_end_size"]=p.endSize;out["_end_color"]=end;}return out;
}
inline SceneParticle sceneParticleFromJson(const J& item){SceneParticle p;p.emitter=item["emitter"].str();p.birth=item["birth_id"].integer();p.age=item["age_ms"].number();p.position=vec(item["position"]);p.size=item["size"].number();p.additive=item["blend"].str()=="additive";p.velocity=vec(item["_velocity"]);p.gravity=vec(item["_gravity"]);p.remaining=item["_remaining_ms"].number();p.endSize=item["_end_size"].number();for(int i=0;i<4;++i){p.color[i]=item["color"][i].number();p.endColor[i]=item["_end_color"][i].number();}return p;}
inline std::vector<SceneParticle> sceneClipParticles(const J& scene,double time,const J& view=J()){
    std::vector<SceneParticle> output;if(scene.null())return output;double duration=scene["duration_ms"].number();bool advanced=scene["schema"].str()=="pixelforge.scene-animation/v2";double t=advanced&&scene["loop"].boolean()?time:sceneTime(scene,time);int ei=0;
    for(auto& e:scene["emitters"].arr()){
        int count=e["count_per_cycle"].integer();double spacing=duration/count,life=e["lifetime_ms"].number();int last=int(std::floor(t/spacing+1e-10)),first=int(std::floor((t-life)/spacing))+1;
        for(int birth=first;birth<=last;++birth){
            if(!scene["loop"].boolean()&&(birth<0||birth>=count))continue;if(advanced&&birth<0&&!view["prewarm"].boolean(scene["loop"].boolean()))continue;double ageMs=t-birth*spacing;if(ageMs<0||ageMs>=life)continue;
            int identity=(birth%count+count)%count;uint32_t seed=uint32_t(scene["seed"].integer())+uint32_t(ei)*1000003U+uint32_t(identity)*9176U;
            if(advanced){double at=scene["loop"].boolean()?std::fmod(std::fmod(birth*spacing,duration)+duration,duration):birth*spacing,intensity=sceneCurve(e["emission"],at).number();if(intensity<=0||(intensity<1&&sceneRandom(seed^0x9e3779b9U)>=intensity))continue;}
            auto direction=vec(e["direction"]),spread=vec(e["spread"]);for(int i=0;i<3;++i)direction.at(i)+=(2*sceneRandom(seed+uint32_t(i)*374761393U)-1)*spread.at(i);double magnitude=length(direction);direction=magnitude>1e-9?direction*(1/magnitude):vec(e["direction"]);
            auto origin=vec(e["position"]);if(!e["anchor_element"].null()){int anchor=e["anchor_element"].integer();auto end=sceneClipTransform(scene,anchor,origin+direction,birth*spacing,false,view);origin=sceneClipTransform(scene,anchor,origin,birth*spacing,false,view);direction=end-origin;direction=direction*(1/length(direction));}
            double age=ageMs/1000,ratio=ageMs/life;SceneParticle particle;particle.emitter=e["id"].str();particle.birth=identity;particle.age=ageMs;particle.gravity=vec(e["gravity"]);particle.position=origin+direction*(e["speed"].number()*age)+particle.gravity*(.5*age*age);particle.velocity=direction*e["speed"].number()+particle.gravity*age;particle.remaining=life-ageMs;particle.size=e["size"][0].number()*(1-ratio)+e["size"][1].number()*ratio;particle.endSize=e["size"][1].number();for(int i=0;i<4;++i){particle.color[i]=e["color"][0][i].number()*(1-ratio)+e["color"][1][i].number()*ratio;particle.endColor[i]=e["color"][1][i].number();}particle.additive=e["blend"].str()=="additive";output.push_back(std::move(particle));
        }++ei;
    }return output;
}
inline std::vector<SceneParticle> sceneCarryParticles(const J& carry,double time){
    std::vector<SceneParticle> output;for(auto& item:carry.arr()){auto p=sceneParticleFromJson(item);if(time<0||time>=p.remaining)continue;double t=time/1000,ratio=time/p.remaining;p.age+=time;p.position=p.position+p.velocity*t+p.gravity*(.5*t*t);p.velocity=p.velocity+p.gravity*t;p.size+=(p.endSize-p.size)*ratio;for(int i=0;i<4;++i)p.color[i]+=(p.endColor[i]-p.color[i])*ratio;p.remaining-=time;output.push_back(std::move(p));}return output;
}

#include "scene_player.hpp"

struct SceneEvaluation{J clip,view;};
inline SceneEvaluation sceneResolve(const J& scene,double time,const J& view=J(),const std::string& state=""){
    if(!sceneProgram(scene))return {scene,view.null()?J::object({{"time_ms",time},{"entry_values",J::object()},{"carry",J::array()},{"prewarm",scene["loop"]},{"first_cycle",true},{"texture_entry_time_ms",0}}):view};
    J actual=view;if(actual.null()){ScenePlayer player(scene);if(state.empty()){player.beginSequence();player.advance(time);}else{player.select(state);player.at=time;}actual=player.view();}
    for(auto& clip:scene["states"].arr())if(clip["id"]==actual["state"])return {clip,actual};throw std::runtime_error("Unknown animation state");
}
inline Vec sceneTransform(const J& scene,int element,Vec p,double time,bool isNormal=false,const J& view=J()){if(scene.null())return p;auto e=sceneResolve(scene,time,view);return sceneClipTransform(e.clip,element,p,e.view["time_ms"].number(),isNormal,e.view);}
inline std::vector<Face> poseMesh(const std::vector<Face>& base,const J& scene,double time,const J& view=J()){
    if(scene.null())return base;auto e=sceneResolve(scene,time,view);auto output=base;for(auto& face:output){for(auto& p:face.points)p=sceneClipTransform(e.clip,face.element,p,e.view["time_ms"].number(),false,e.view);face.normal=sceneClipTransform(e.clip,face.element,face.normal,e.view["time_ms"].number(),true,e.view);}return output;
}
inline std::vector<SceneParticle> sceneParticles(const J& scene,double time,const J& view=J()){
    if(scene.null())return {};auto e=sceneResolve(scene,time,view);auto out=sceneClipParticles(e.clip,e.view["time_ms"].number(),e.view),carry=sceneCarryParticles(e.view["carry"],e.view["time_ms"].number());out.insert(out.end(),carry.begin(),carry.end());if(out.size()>2048)out.resize(2048);return out;
}
// Cover every state's channel range and all released particle trajectories.
inline std::pair<Vec,Vec> scenePointBounds(const J& scene,int element,Vec lo,Vec hi){
    for(auto& track:sceneEntries(scene,"transforms").arr()){
        bool applies=false;for(auto& id:track["elements"].arr())if(id.integer()==element)applies=true;if(!applies)continue;
        auto pivot=vec(track["pivot"]);auto type=track["type"].str();
        if(type=="rotate"){double r=0;for(auto p:vertices(lo,hi))r=pf::max(r,length(p-pivot));lo=pivot-Vec{r,r,r};hi=pivot+Vec{r,r,r};}
        else{auto range=sceneValueRange(scene,track);for(int i=0;i<3;++i){if(type=="translate"){lo.at(i)+=range.first.at(i);hi.at(i)+=range.second.at(i);}else{double a=lo.at(i)-pivot.at(i),b=hi.at(i)-pivot.at(i),s=range.first.at(i),S=range.second.at(i);lo.at(i)=pivot.at(i)+pf::min({a*s,a*S,b*s,b*S});hi.at(i)=pivot.at(i)+pf::max({a*s,a*S,b*s,b*S});}}}
    }return {lo,hi};
}
// Keep a sphere through the chain: reboxing it at every joint otherwise
// multiplies its radius, even when all rotations have the same pivot.
inline std::pair<Vec,double> scenePointSphere(const J& scene,int element,Vec lo,Vec hi){
    Vec center=(lo+hi)*.5;double radius=length(hi-lo)*.5;
    for(auto& track:sceneEntries(scene,"transforms").arr()){
        bool applies=false;for(auto& id:track["elements"].arr())if(id.integer()==element)applies=true;if(!applies)continue;
        auto pivot=vec(track["pivot"]);auto type=track["type"].str();
        if(type=="rotate"){auto axis=vec(track["axis"]),projected=pivot+axis*(axis.dot(center-pivot));radius+=length(center-projected);center=projected;}
        else{auto range=sceneValueRange(scene,track);
            if(type=="translate"){center=center+(range.first+range.second)*.5;radius+=length(range.second-range.first)*.5;}
            else{Vec offset=center-pivot,variation;double scale=0;for(int i=0;i<3;++i){double a=range.first.at(i),b=range.second.at(i);center.at(i)=pivot.at(i)+offset.at(i)*(a+b)*.5;variation.at(i)=offset.at(i)*(b-a)*.5;scale=pf::max({scale,std::abs(a),std::abs(b)});}radius=radius*scale+length(variation);}
        }
    }return {center,radius};
}
inline std::pair<Vec,double> sceneBounds(const J& shapes,const std::vector<Face>& base,const J& scene){
    if(scene.null())return shapeBounds(shapes,base);Vec lo{1e20,1e20,1e20},hi{-1e20,-1e20,-1e20};
    auto include=[&](Vec a,Vec b){for(int i=0;i<3;++i){lo.at(i)=pf::min(lo.at(i),a.at(i));hi.at(i)=pf::max(hi.at(i),b.at(i));}};
    for(auto& f:base)for(auto p:f.points)include(p,p);for(auto& target:{"base","collision","selection"})for(auto& b:effective(shapes,target).arr())include(vec(b["from"]),vec(b["to"]));if(lo.x>hi.x)include({0,0,0},{16,16,16});
    Vec initialLo=lo,initialHi=hi;std::vector<std::pair<Vec,double>> spheres;
    for(int element=0;element<int(shapes["model"]["elements"].size());++element){bool have=false;Vec a,b;for(auto& f:base)if(f.element==element)for(auto p:f.points){if(!have){a=b=p;have=true;}for(int i=0;i<3;++i){a.at(i)=pf::min(a.at(i),p.at(i));b.at(i)=pf::max(b.at(i),p.at(i));}}if(have)spheres.push_back(scenePointSphere(scene,element,a,b));}
    auto emitters=[&](const J& clip){for(auto& e:clip["emitters"].arr()){Vec origin=vec(e["position"]);auto sphere=e["anchor_element"].null()?std::pair<Vec,double>{origin,0}:scenePointSphere(scene,e["anchor_element"].integer(),origin,origin);double life=e["lifetime_ms"].number()/1000,speed=e["speed"].number(),size=pf::max(e["size"][0].number(),e["size"][1].number())*.5;sphere.second+=speed*life+length(vec(e["gravity"]))* .5*life*life+size;spheres.push_back(sphere);}};
    if(sceneProgram(scene))for(auto& clip:scene["states"].arr())emitters(clip);else emitters(scene);
    for(auto& [c,r]:spheres)include(c-Vec{r,r,r},c+Vec{r,r,r});auto center=(lo+hi)*.5;double radius=1;
    for(auto p:vertices(initialLo,initialHi))radius=pf::max(radius,length(p-center));for(auto& [c,r]:spheres)radius=pf::max(radius,length(c-center)+r);return {center,radius};
}
inline J sceneTextureControl(const J& scene,double time,const J& view=J()){
    if(!sceneProgram(scene)&&scene["texture"].null())return J::object({{"mode","play"},{"time_ms",time}});auto e=sceneResolve(scene,time,view);J result=e.clip["texture"];const J& texture=result;result["time_ms"]=e.view["texture_entry_time_ms"].number()+e.view["time_ms"].number()*texture["speed"].number();return result;
}
inline J nativeSceneSample(const J& scene,const J& model,double time,const J& view=J(),const std::string& state=""){
    if(scene.null())return J();auto e=sceneResolve(scene,time,view,state);double t=sceneTime(e.clip,e.view["time_ms"].number()),poseTime=e.clip["schema"].str()=="pixelforge.scene-animation/v2"?e.view["time_ms"].number():t;J parts=J::array(),particles=J::array();for(int i=0;i<int(model["elements"].size());++i){J basis=J::array();for(Vec p:{Vec{1,0,0},Vec{0,1,0},Vec{0,0,1}})basis.arr().push_back(sceneVector(sceneClipTransform(e.clip,i,p,poseTime,false,e.view)));parts.arr().push_back(J::object({{"element",i},{"origin",sceneVector(sceneClipTransform(e.clip,i,{},poseTime,false,e.view))},{"basis",basis}}));}
    for(auto& p:sceneParticles(scene,time,e.view))particles.arr().push_back(sceneParticleJson(p));J result=J::object({{"time_ms",t},{"parts",parts},{"particles",particles}});if(sceneProgram(scene)){result["scene_state"]=e.clip["id"];result["state_label"]=e.clip["label"];result["texture"]=sceneTextureControl(scene,time,e.view);}return result;
}
