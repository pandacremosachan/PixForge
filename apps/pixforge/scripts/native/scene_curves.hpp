#pragma once
// Included inside namespace pf, after Vec and JSON have been defined.
inline J sceneVector(Vec p){return J::array({p.x,p.y,p.z});}
inline bool sceneProgram(const J& scene){return scene["states"].isArray();}
inline const J& sceneEntries(const J& scene,const std::string& kind){return sceneProgram(scene)?scene["states"][0][kind]:scene[kind];}
inline double sceneTime(const J& scene,double time){double duration=scene["duration_ms"].number(1);return scene["loop"].boolean()?std::fmod(std::fmod(time,duration)+duration,duration):pf::clamp(time,0.,duration);}
inline double sceneEase(double t,const std::string& kind){if(kind=="hold")return 0;if(kind=="smooth")return t*t*(3-2*t);if(kind=="ease_in")return t*t;if(kind=="ease_out")return 1-(1-t)*(1-t);return t;}
inline J sceneCurve(const J& keys,double time,const J& first=J()){
    if(time<=keys[0]["time_ms"].number())return first.null()?keys[0]["value"]:first;
    if(time>=keys[keys.size()-1]["time_ms"].number())return keys[keys.size()-1]["value"];
    for(size_t i=0;i+1<keys.size();++i){auto& a=keys[i];auto& b=keys[i+1];if(time<b["time_ms"].number()){
        double p=sceneEase((time-a["time_ms"].number())/(b["time_ms"].number()-a["time_ms"].number()),a["easing"].str());auto start=i==0&&!first.null()?first:a["value"];
        if(start.isArray()){J out=J::array();for(size_t n=0;n<start.size();++n)out.arr().push_back(start[n].number()+(b["value"][n].number()-start[n].number())*p);return out;}
        return start.number()+(b["value"].number()-start.number())*p;
    }}return keys[keys.size()-1]["value"];
}
inline J sceneTrackValue(const J& track,double duration,double time,const J& entry=J(),bool firstCycle=true){
    auto inherited=entry[track["id"].str()];auto mode=track["entry"].str("absolute");J value;
    if(track["keyframes"].isArray())value=sceneCurve(track["keyframes"],time,mode=="from_current"&&firstCycle?inherited:J());
    else if(track["type"].str()=="rotate")value=track["phase_deg"].number()+360*track["turns"].number()*time/duration;
    else{double wave=std::sin(track["phase_deg"].number()*PI/180+2*PI*track["cycles"].number()*time/duration),base=track["type"].str()=="scale"?1:0;auto a=vec(track["amplitude"]);value=J::array({base+a.x*wave,base+a.y*wave,base+a.z*wave});}
    if(mode=="relative"&&!inherited.null())value=value.number()+inherited.number();return value;
}
inline std::pair<Vec,Vec> sceneValueRange(const J& scene,const J& channel){
    Vec lo{1e20,1e20,1e20},hi{-1e20,-1e20,-1e20};
    auto include=[&](Vec p){for(int i=0;i<3;++i){lo.at(i)=pf::min(lo.at(i),p.at(i));hi.at(i)=pf::max(hi.at(i),p.at(i));}};
    auto clip=[&](const J& definition){for(auto& track:definition["transforms"].arr())if(track["id"]==channel["id"]){if(track["keyframes"].isArray())for(auto& key:track["keyframes"].arr())include(vec(key["value"]));else{double base=track["type"].str()=="scale"?1:0;auto a=vec(track["amplitude"]);for(int i=0;i<3;++i){lo.at(i)=pf::min(lo.at(i),base-std::abs(a.at(i)));hi.at(i)=pf::max(hi.at(i),base+std::abs(a.at(i)));}}}};
    if(sceneProgram(scene))for(auto& state:scene["states"].arr())clip(state);else clip(scene);return {lo,hi};
}
