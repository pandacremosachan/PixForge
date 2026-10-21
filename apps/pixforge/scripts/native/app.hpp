#pragma once
#include "gpu.hpp"
#include "clipboard.hpp"
#include "cursors.hpp"

namespace pf {
struct RenderJob {std::string key,context;uint64_t serial=0;J definition,scene,sceneView;double time=0;Image atlas;int size=440,background=0;double yaw=25,pitch=20,zoom=1;std::vector<std::string> overlays;bool showModel=true;};
struct RenderReady {std::string key,context;uint64_t serial=0;RenderResult result;double ms=0;};
class Renderer {
    std::mutex mutex;std::condition_variable wake;std::unique_ptr<RenderJob> job;bool closing=false;std::thread thread;HWND hwnd;
public:
    explicit Renderer(HWND window):hwnd(window){thread=std::thread([this]{for(;;){std::unique_lock<std::mutex> guard(mutex);wake.wait(guard,[&]{return closing||job!=nullptr;});if(closing)break;auto next=std::move(job);guard.unlock();double start=milliseconds();try{RenderResult result=renderShapes(next->definition,next->atlas,next->size,next->yaw,next->pitch,next->overlays,next->showModel,next->background,next->scene,next->time,next->zoom,next->sceneView);auto ready=new RenderReady{next->key,next->context,next->serial,std::move(result),milliseconds()-start};if(!PostMessageW(hwnd,WM_RENDER,0,LPARAM(ready)))delete ready;}catch(...){}}});}
    ~Renderer(){{std::lock_guard<std::mutex> guard(mutex);closing=true;job.reset();}wake.notify_one();thread.join();}
    void submit(RenderJob next){{std::lock_guard<std::mutex> guard(mutex);job=std::make_unique<RenderJob>(std::move(next));}wake.notify_one();}
};
struct Button {HWND hwnd;std::wstring title;std::function<void()> click;std::function<bool()> checked;bool primary=false;int toolIndex=-1;std::wstring tooltip;bool toggleSwitch=false;};
class App {
public:
    HCURSOR panOpen=nullptr,panClosed=nullptr;int cursorDpi=0;
    HWND hwnd=nullptr,tooltipWindow=nullptr;fs::path workspace,runtime;HFONT font=nullptr,boldFont=nullptr;int dpi=96,pendingTool=-1;
    std::unique_ptr<Rpc> rpc;std::unique_ptr<Frontend> frontend;std::unique_ptr<Renderer> renderer;std::unique_ptr<GpuScene> gpu;
    std::unique_ptr<ScenePlayer> scenePlayer;HWND sceneStateCombo=nullptr;
    std::vector<std::unique_ptr<Surface>> surfaces;std::map<std::string,HWND> handles;std::map<int,Button> buttons;int nextButton=100;
    Surface *menuBar=nullptr,*toolbar=nullptr,*rail=nullptr,*documentBar=nullptr,*tabs=nullptr,*canvasView=nullptr,*sceneView=nullptr,*sceneHeading=nullptr,*colorWheel=nullptr,*paletteView=nullptr,*navigator=nullptr,*layerView=nullptr,*timeline=nullptr,*statusBar=nullptr;
    Surface* uvInspector=nullptr;J modelUv;bool uvGuides=true,uvPinned=false;int uvX=-1,uvY=-1,uvScroll=0,uvContentHeight=0;std::string uvRegion;std::vector<int> uvHits;
    HWND sizeEdit=nullptr,opacityEdit=nullptr,solidButton=nullptr,hexEdit=nullptr,alphaEdit=nullptr,zoomEdit=nullptr,durationEdit=nullptr;
    std::unique_ptr<Form> shapesForm;
    HWND shapeTarget=nullptr,shapeMode=nullptr,shapeConstruction=nullptr,errorEdit=nullptr,targetEdit=nullptr,boxList=nullptr,boxName=nullptr,boxCoords=nullptr,shapeReport=nullptr,shapeExportFormat=nullptr;
    HWND shapeYaw=nullptr,shapePitch=nullptr,showModelButton=nullptr;
    std::array<HWND,6> boxAxes{};
    J state=J::object(),snapshot=J::object(),lastPoll=J::object(),proposedShapes,proposalTokens;
    Canvas canvas;bool loaded=false,loading=false,fetching=false,mutationPending=false,closing=false,inspectorVisible=true,timelineVisible=true,nativePatches=false,fastPoll=false,fillApplied=false;
    std::function<void()> afterFetch;
    std::deque<std::function<void()>> userActions;
    std::map<HWND,J> editObservations;
    std::map<HWND,std::wstring> tooltipText;
    int panel=0,inspectorTab=0,tool=7,frame=0,step=0,layerOffset=0,timelineOffset=0,rightWidth=294,timelineHeight=182,sideWidth=290;
    bool grid=false,tiled=false,onion=false,mirrorX=false,mirrorY=false,solid=false,playing=false;
    Pixel ink={217,162,106,255};double zoom=12,panX=0,panY=0,playStart=0,elapsed=0,lastRecovery=0,lastSceneTick=0;bool sceneScrubbing=false;
    Rect selection,selectionStart;bool selecting=false,movingSelection=false;int selectionX=0,selectionY=0;
    bool dragging=false,panning=false,strokePending=false,strokeReleased=false,strokeCancelled=false,strokeCommitting=false;std::string lease;Stroke stroke;
    int lastMouseX=0,lastMouseY=0,splitDrag=0,colorDrag=0;double hue=0;Rect strokeRegion;
    double yaw=25,pitch=20,sceneZoom=1,lastRenderMs=0;bool overlays[3]={false,true,false},showModel=true;
    std::string renderKey,sceneContext,gpuContext;uint64_t sceneSerial=0;std::shared_ptr<RenderReady> rendered;
    std::map<std::string,std::shared_ptr<RenderReady>> renderCache;std::deque<std::string> renderOrder;
    Image frameImage;std::vector<uint32_t> frameDib;int frameCache=-1;std::string frameContent;bool frameDirty=true;
    std::wstring message=L"正在连接独立核心…";std::vector<double> paintSamples,strokeSamples;uint64_t paintCount=0,frameSwitches=0,renderCount=0,pollCount=0;
    bool emptyModelTexture=false;std::string textureContext;
    double bootTime=milliseconds(),readyTime=0;bool firstFit=true;std::string startupPath;

    App(fs::path work,fs::path run,std::string openPath="");
    ~App();
    int D(int n)const{return MulDiv(n,dpi,96);}
    HWND button(HWND parent,std::string name,std::wstring title,std::function<void()> callback,std::function<bool()> checked={},bool primary=false);
    HWND edit(HWND parent,std::string name,std::wstring value,bool numeric=false);
    HWND combo(HWND parent,std::string name,std::initializer_list<std::wstring> values);
    Surface* surface(HWND parent,int id,std::function<void(HDC,RECT)> draw);
    void create();void layout();void updateFont();void command(int id,int notification);void menu(int group,int x,int y);
    void fetch();void apply(const J& response);void poll();void refresh(bool contentChanged=true);void error(const J& failure);
    J tokens()const;J payload(std::string action,J fields=J::object())const;
    void mutate(std::string action,J fields=J::object(),std::function<void(const J&)> after={});
    void replaceCanvas(Canvas next,std::string label);void layerAction(std::string action);void dimensions(bool split);
    void newProject();void openProject(fs::path path={});void saveProject(bool as=false);bool saveBefore(std::function<void()> next);
    void exportAsset(std::string action,bool currentFrame=false);void seek(int target,bool pause=true);void playback();void seekTime(double value,bool pause=true);void animationEdit(std::string action);void duration();void reorder(int direction);
    Rect currentRect()const;bool canWrite()const;void setColor(Pixel color);void setZoom(double value,int x=-1,int y=-1);void fit();
    void frameCacheUpdate();void paintCanvas(HDC dc,RECT area);LRESULT canvasEvent(UINT,WPARAM,LPARAM);void beginStroke(int x,int y);void moveStroke(int x,int y);void endStroke(bool cancel=false);void commitStroke();
    void paintUvGuides(HDC dc,RECT area,double ox,double oy,int repeats);void paintUvInspector(HDC dc,RECT area);void inspectUvPixel(int x,int y,bool pin=false);void clearUvPin();J uvStatus()const;
    void paintWheel(HDC dc,RECT r);LRESULT wheelEvent(UINT,WPARAM,LPARAM);void paintPalette(HDC dc,RECT r);
    void paintLayers(HDC dc,RECT r);void paintTimeline(HDC dc,RECT r);void paintScene(HDC dc,RECT r);void paintStatus(HDC dc,RECT r);
    void buildShapes();void refreshShapes();std::string shapeTargetName()const;J shapeItems()const;void shapeCommit(J operations);void construct(bool dry);void selectBox(int index);void shapeBox(std::string action);
    void requestRender();void renderComplete(RenderReady* result);J uiStatus()const;J uiHelp()const;J uiCommand(const J& command);J metrics()const;void capture(const fs::path& path,bool overwrite=false);
    bool key(MSG& message);void close();LRESULT procedure(UINT,WPARAM,LPARAM);static LRESULT CALLBACK proc(HWND,UINT,WPARAM,LPARAM);
    void selectTool(int index);void tooltips();J controls()const;
    void userAction(std::function<void()> callback);
    void syncViewSwitches();
    void resetScenePlayer();void syncStateControls(bool rebuild=false);void stateAction(const std::string& action,const std::string& identity="",bool resume=true);void programTextureStep();void advanceProgram(double delta);double sceneClock()const;double sceneDuration()const;
    HCURSOR canvasCursor();void updateCanvasCursor();
    void selectionAction(std::string action);void updateSelection(int x,int y);void clearSelection();
    void startLease();void editPixels(Image next,Rect region);
};
}
