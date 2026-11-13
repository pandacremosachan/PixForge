#include "app.hpp"

namespace pf {
double App::sceneClock()const{return studio()?rigTime:scenePlayer?scenePlayer->clock():state["scene_animation"].null()?elapsed:sceneTime(state["scene_animation"],elapsed);}
double App::sceneDuration()const{return studio()?rigEnd:scenePlayer?scenePlayer->duration():state["scene_animation"]["duration_ms"].number();}
void App::resetScenePlayer(){
    scenePlayer.reset();if(sceneProgram(state["scene_animation"]))scenePlayer=std::make_unique<ScenePlayer>(state["scene_animation"]);elapsed=0;playStart=milliseconds();syncStateControls(true);
}
void App::syncStateControls(bool rebuild){
    if(!sceneStateCombo)return;
    if(studio()){int i=0;for(const auto& a:playerRig()["clips"].arr()){if(a["name"].str()==rigClip){comboSet(sceneStateCombo,i);break;}++i;}syncPlayback();return;}
    const auto& states=static_cast<const J&>(state)["scene_animation"]["states"];int index=-1;
    if(scenePlayer){
        if(scenePlayer->sequenceMode)index=int(states.size());
        else for(size_t i=0;i<states.size();++i)if(states[i]["id"].str()==scenePlayer->state){index=int(i);break;}
    }
    if(rebuild){
        std::vector<std::wstring> names;
        if(scenePlayer){for(const auto& clip:states.arr())names.push_back(wide(clip["label"].str()));names.push_back(L"完整流程");}
        playbackStates.set(sceneStateCombo,std::move(names),index);
    }else comboSet(sceneStateCombo,index);
    syncPlayback();
}
void App::programTextureStep(){
    if(!scenePlayer||!loaded)return;auto control=sceneTextureControl(state["scene_animation"],elapsed,scenePlayer->view());auto& steps=state["animation"]["steps"];int found=0;
    if(control["mode"].str()=="hold"&&control.contains("frame")){
        int wanted=control["frame"].integer();for(int i=0;i<int(steps.size());++i)if(steps[i]["frame"].integer()==wanted){found=i;break;}
    }else{double total=0;for(auto& s:steps.arr())total+=s["duration_ms"].number();double time=control["time_ms"].number();time=state["animation"]["loop"].boolean()?std::fmod(std::fmod(time,total)+total,total):pf::min(time,total-1e-7);for(int i=0;i<int(steps.size());++i){found=i;if(time<steps[i]["duration_ms"].number())break;time-=steps[i]["duration_ms"].number();}}
    if(found!=step)seek(found,false);
}
void App::stateAction(const std::string& action,const std::string& identity,bool resume){
    if(!scenePlayer||!loaded||!canWrite())return;
    if(action=="preview")scenePlayer->select(identity);else if(action=="demo")scenePlayer->beginSequence(true);else if(action=="leave_demo")scenePlayer->sequenceMode=false;else scenePlayer->event(action);
    elapsed=scenePlayer->clock();playStart=milliseconds();playing=resume;programTextureStep();syncStateControls();renderKey.clear();layout();requestRender();syncPlayback();
}
void App::advanceProgram(double delta){
    if(!scenePlayer)return;auto previous=scenePlayer->generation;scenePlayer->advance(pf::clamp(delta,0.,120000.));elapsed=scenePlayer->clock();programTextureStep();if(scenePlayer->finished){playing=false;syncPlayback();}if(previous!=scenePlayer->generation)syncStateControls();
}
}
