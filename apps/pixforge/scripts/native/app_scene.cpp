#include "app.hpp"

namespace pf {
double App::sceneClock()const{return scenePlayer?scenePlayer->clock():state["scene_animation"].null()?elapsed:sceneTime(state["scene_animation"],elapsed);}
double App::sceneDuration()const{return scenePlayer?scenePlayer->duration():state["scene_animation"]["duration_ms"].number();}
void App::resetScenePlayer(){
    scenePlayer.reset();if(sceneProgram(state["scene_animation"]))scenePlayer=std::make_unique<ScenePlayer>(state["scene_animation"]);elapsed=0;playStart=milliseconds();syncStateControls(true);
}
void App::syncStateControls(bool rebuild){
    if(!sceneStateCombo)return;
    if(rebuild){SendMessageW(sceneStateCombo,CB_RESETCONTENT,0,0);if(scenePlayer)for(auto& clip:state["scene_animation"]["states"].arr()){auto label=wide(clip["label"].str());SendMessageW(sceneStateCombo,CB_ADDSTRING,0,LPARAM(label.c_str()));}}
    if(scenePlayer){if(GetFocus()!=sceneStateCombo)for(size_t i=0;i<state["scene_animation"]["states"].size();++i)if(state["scene_animation"]["states"][i]["id"].str()==scenePlayer->state)comboSet(sceneStateCombo,int(i));EnableWindow(handles["state_start"],!scenePlayer->route("start").empty());EnableWindow(handles["state_stop"],!scenePlayer->route("stop").empty());}
    for(auto name:{"state_preview","state_demo","loop"})if(handles.count(name))InvalidateRect(handles[name],nullptr,FALSE);
    if(timeline)timeline->redraw();
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
    elapsed=scenePlayer->clock();playStart=milliseconds();playing=resume;programTextureStep();syncStateControls();renderKey.clear();layout();requestRender();InvalidateRect(handles["play"],nullptr,FALSE);
}
void App::advanceProgram(double delta){
    if(!scenePlayer)return;auto previous=scenePlayer->generation;scenePlayer->advance(pf::clamp(delta,0.,120000.));elapsed=scenePlayer->clock();programTextureStep();if(scenePlayer->finished){playing=false;InvalidateRect(handles["play"],nullptr,FALSE);}if(previous!=scenePlayer->generation)syncStateControls();
}
}
