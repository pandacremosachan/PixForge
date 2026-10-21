#pragma once
// Shares only immutable project data and a local preview clock with the UI.
class ScenePlayer {
public:
    J program,entry=J::object(),carry=J::array();std::string state;
    double at=0,textureEntry=0,sequenceElapsed=0;bool prewarm=true,firstCycle=true,sequenceMode=false,finished=false,repeat=false;size_t sequenceIndex=0;uint64_t generation=0;
    explicit ScenePlayer(const J& scene):program(scene),state(scene["initial_state"].str()){if(!sceneProgram(program))throw std::runtime_error("ScenePlayer requires named states");prewarm=clip()["loop"].boolean();repeat=program["loop"].boolean();}
    const J& clip()const{for(auto& s:program["states"].arr())if(s["id"].str()==state)return s;throw std::runtime_error("Unknown animation state");}
    bool hasState(const std::string& identity)const{for(auto& s:program["states"].arr())if(s["id"].str()==identity)return true;return false;}
    std::string route(const std::string& event)const{for(auto& r:program["transitions"].arr())if(r["from"].str()==state&&r["event"].str()==event)return r["to"].str();return "";}
    double textureTime()const{return textureEntry+at*clip()["texture"]["speed"].number();}
    void setTextureTime(double value){textureEntry=value-at*clip()["texture"]["speed"].number();}
    J view()const{return J::object({{"state",state},{"time_ms",at},{"entry_values",entry},{"carry",carry},{"prewarm",prewarm},{"first_cycle",firstCycle},{"texture_entry_time_ms",textureEntry}});}
    double clock()const{if(!sequenceMode)return sceneTime(clip(),at);double sum=sequenceElapsed;for(size_t i=0;i<sequenceIndex;++i)sum+=program["preview_sequence"][i]["duration_ms"].number();return sum;}
    double duration()const{return sequenceMode?program["duration_ms"].number():clip()["duration_ms"].number();}
    J summary()const{J events=J::array();for(auto& r:program["transitions"].arr())if(r["from"].str()==state)events.arr().push_back(r["event"]);return J::object({{"state",state},{"label",clip()["label"]},{"time_ms",sceneTime(clip(),at)},{"duration_ms",clip()["duration_ms"]},{"sequence_mode",sequenceMode},{"sequence_time_ms",clock()},{"sequence_duration_ms",program["duration_ms"]},{"finished",finished},{"repeat_sequence",repeat},{"available_events",events}});}
    struct Capture {J values,particles;double texture;};
    Capture capture()const{
        J values=J::object(),flying=J::array();double time=sceneTime(clip(),at);for(auto& t:clip()["transforms"].arr())values[t["id"].str()]=sceneTrackValue(t,clip()["duration_ms"].number(),time,entry,firstCycle&&at<clip()["duration_ms"].number());
        auto fresh=sceneClipParticles(clip(),at,view()),old=sceneCarryParticles(carry,at);fresh.insert(fresh.end(),old.begin(),old.end());if(fresh.size()>2048)fresh.resize(2048);for(auto& p:fresh)flying.arr().push_back(sceneParticleJson(p,true));return {values,flying,textureTime()};
    }
    void enter(const std::string& identity,bool preserve=true){
        if(!hasState(identity))throw std::runtime_error("Unknown animation state: "+identity);auto source=preserve?capture():Capture{J::object(),J::array(),0};state=identity;at=0;entry=std::move(source.values);carry=std::move(source.particles);textureEntry=source.texture;prewarm=preserve?false:clip()["loop"].boolean();firstCycle=true;finished=false;++generation;
    }
    void select(const std::string& identity,bool preserve=false){enter(identity,preserve);sequenceMode=false;}
    void event(const std::string& name){auto target=route(name);if(target.empty())throw std::runtime_error("Current state does not accept event: "+name);enter(target,true);sequenceMode=false;}
    void beginSequence(bool preserve=false){enter(program["preview_sequence"][0]["state"].str(),preserve);sequenceMode=true;sequenceIndex=0;sequenceElapsed=0;finished=false;}
    void tick(double delta){
        at+=delta;double limit=clip()["duration_ms"].number()*(firstCycle?2:1);for(auto& p:carry.arr())limit=pf::max(limit,p["_remaining_ms"].number());if(clip()["loop"].boolean()&&at>=limit){double wrapped=at-std::fmod(at,clip()["duration_ms"].number());textureEntry+=wrapped*clip()["texture"]["speed"].number();at-=wrapped;carry=J::array();prewarm=true;firstCycle=false;}
    }
    void advance(double delta){
        if(!std::isfinite(delta)||delta<0||delta>120000)throw std::runtime_error("Invalid scene playback delta");double remaining=delta;
        while(!finished){
            if(sequenceMode){double limit=program["preview_sequence"][sequenceIndex]["duration_ms"].number(),step=pf::min(remaining,pf::max(0.,limit-sequenceElapsed));tick(step);sequenceElapsed+=step;remaining-=step;if(sequenceElapsed+1e-9<limit)break;
                if(sequenceIndex+1<program["preview_sequence"].size())++sequenceIndex;else if(repeat)sequenceIndex=0;else{finished=true;break;}sequenceElapsed=0;enter(program["preview_sequence"][sequenceIndex]["state"].str(),true);
            }else if(clip()["loop"].boolean()){tick(remaining);break;}
            else{double step=pf::min(remaining,pf::max(0.,clip()["duration_ms"].number()-at));tick(step);remaining-=step;if(at+1e-9<clip()["duration_ms"].number())break;if(clip()["next"].null()){finished=true;break;}enter(clip()["next"].str(),true);}
            if(remaining<=1e-9)break;
        }
    }
    void seek(double value){if(sequenceMode){beginSequence(false);advance(value);}else{at=value;finished=false;++generation;}}
};
