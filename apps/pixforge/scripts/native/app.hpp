#pragma once
#include "gpu.hpp"
#include "clipboard.hpp"
#include "cursors.hpp"

namespace pf {
inline const std::array<std::string,10> TOOLS={"pen","eraser","fill","picker","line","rect","ellipse","hand","select","move"};
inline constexpr int HAND=7;
struct RenderJob {std::string key,context;uint64_t serial=0;J definition,scene,sceneView;double time=0;Image atlas;int size=440,background=0;double yaw=25,pitch=20,zoom=1;std::vector<std::string> overlays;bool showModel=true;};
struct RenderReady {std::string key,context;uint64_t serial=0;RenderResult result;double ms=0;};
class Renderer {
    std::mutex mutex;std::condition_variable wake;std::unique_ptr<RenderJob> job;bool closing=false;std::thread thread;HWND hwnd;
public:
    explicit Renderer(HWND window):hwnd(window){thread=std::thread([this]{for(;;){std::unique_lock<std::mutex> guard(mutex);wake.wait(guard,[&]{return closing||job!=nullptr;});if(closing)break;auto next=std::move(job);guard.unlock();double start=milliseconds();try{RenderResult result=renderShapes(next->definition,next->atlas,next->size,next->yaw,next->pitch,next->overlays,next->showModel,next->background,next->scene,next->time,next->zoom,next->sceneView);auto ready=new RenderReady{next->key,next->context,next->serial,std::move(result),milliseconds()-start};if(!PostMessageW(hwnd,WM_RENDER,0,LPARAM(ready)))delete ready;}catch(...){}}});}
    ~Renderer(){{std::lock_guard<std::mutex> guard(mutex);closing=true;job.reset();}wake.notify_one();thread.join();}
    void submit(RenderJob next){{std::lock_guard<std::mutex> guard(mutex);job=std::make_unique<RenderJob>(std::move(next));}wake.notify_one();}
};
struct Button {HWND hwnd;std::wstring title;std::function<void()> click;std::function<bool()> checked;int icon=-1;bool toggle=false,wasChecked=false;};
struct Caption {
    RECT area;std::wstring label;bool heading=false;
    bool operator==(const Caption& other)const{return EqualRect(&area,&other.area)&&label==other.label&&heading==other.heading;}
};
struct LayerRow {std::wstring name;bool visible;Image thumb;};
class App {
public:
    HCURSOR panOpen=nullptr,panClosed=nullptr;int cursorDpi=0;
    HWND hwnd=nullptr,tooltipWindow=nullptr;fs::path workspace,runtime;HFONT font=nullptr,boldFont=nullptr;int dpi=96,pendingTool=-1;
    std::unique_ptr<Rpc> rpc;std::unique_ptr<Frontend> frontend;std::unique_ptr<Renderer> renderer;std::unique_ptr<GpuScene> gpu;
    std::unique_ptr<ScenePlayer> scenePlayer;HWND sceneStateCombo=nullptr;
    std::vector<std::unique_ptr<Surface>> surfaces;std::map<std::string,HWND> handles;std::map<int,Button> buttons;int nextButton=100;
    Surface *documentBar=nullptr,*canvasView=nullptr,*sceneView=nullptr,*details=nullptr,*timeline=nullptr,*statusBar=nullptr;
    J modelUv;bool uvGuides=false,uvPinned=false;int uvX=-1,uvY=-1,uvScroll=0,uvContentHeight=0;std::string uvRegion;std::vector<int> uvHits;
    HWND sizeCombo=nullptr,opacityCombo=nullptr,layerList=nullptr,yawSlider=nullptr,pitchSlider=nullptr;
    Surface *colorField=nullptr,*swatches=nullptr;
    std::vector<Caption> captions;
    std::map<HWND,ControlPlacement> placements;
    std::vector<Pixel> paletteColors;
    std::vector<LayerRow> layerRows;ComboChoices playbackStates;
    int shownYaw=-361,shownPitch=-361;
    int paletteOffset=0,colorDrag=0;double colorHue=0;
    int brushSize=1;double brushOpacity=100;
    J state=J::object(),snapshot=J::object(),lastPoll=J::object();
    Canvas canvas;bool loaded=false,loading=false,fetching=false,mutationPending=false,closing=false,inspectorVisible=true,timelineVisible=true,nativePatches=false,fastPoll=false,fillApplied=false;
    std::function<void()> afterFetch;
    std::deque<std::function<void()>> userActions;
    std::map<HWND,std::wstring> tooltipText;
    int panel=0,inspectorTab=0,tool=HAND,frame=0,step=0;
    bool grid=false,tiled=false,onion=false,mirrorX=false,mirrorY=false,solid=false,playing=false;
    Pixel ink={217,162,106,255};double zoom=12,panX=0,panY=0,playStart=0,elapsed=0,lastRecovery=0,lastSceneTick=0;bool sceneScrubbing=false;
    Rect selection,selectionStart;bool selecting=false,movingSelection=false;int selectionX=0,selectionY=0;
    bool dragging=false,panning=false,strokePending=false,strokeReleased=false,strokeCancelled=false,strokeCommitting=false;std::string lease;Stroke stroke;
    int lastMouseX=0,lastMouseY=0;Rect strokeRegion;
    double yaw=25,pitch=20,sceneZoom=1,lastRenderMs=0;bool overlays[3]={false,false,false},showModel=true;
    std::string renderKey,sceneContext,gpuContext;uint64_t sceneSerial=0;std::shared_ptr<RenderReady> rendered;
    std::map<std::string,std::shared_ptr<RenderReady>> renderCache;std::deque<std::string> renderOrder;
    Image frameImage;std::vector<uint32_t> frameDib;int frameCache=-1;std::string frameContent;bool frameDirty=true;
    std::wstring message=L"正在打开工程…";std::vector<double> paintSamples,strokeSamples;uint64_t paintCount=0,frameSwitches=0,renderCount=0,pollCount=0;
    double bootTime=milliseconds(),readyTime=0;bool firstFit=true,pixelAutoFit=true;std::string startupPath;

    App(fs::path work,fs::path run,std::string openPath="");
    ~App();
    int D(int n)const{return MulDiv(n,dpi,96);}
    HWND button(HWND parent,std::string name,std::wstring title,std::function<void()> callback,std::function<bool()> checked={});
    HWND combo(HWND parent,std::string name,std::initializer_list<std::wstring> values);
    Surface* surface(HWND parent,int id,std::function<void(HDC,RECT)> draw);
    void create();void layout();void updateFont();void command(int id,int notification);void fileMenu();void switchPanel(int value);
    void placeControl(HWND control,int x,int y,int w,int h,bool visible=true);
    void createPanels();void paintChrome(HDC dc,RECT r);void syncCamera();void syncButtons();
    void syncLayers();void refreshPalette();void paintColors(HDC dc,RECT r);LRESULT colorEvent(UINT,WPARAM,LPARAM);
    void paintSwatches(HDC dc,RECT r);LRESULT swatchEvent(UINT,WPARAM,LPARAM);void drawLayer(const DRAWITEMSTRUCT& item);
    bool adjusting()const{return panel==0&&tool!=HAND;}
    bool animated()const{return state["animation"]["steps"].size()>1||!state["scene_animation"].null();}
    bool showTransport()const{return loaded&&animated()&&timelineVisible;}
    void fetch();void apply(const J& response);void poll();void refresh();void error(const J& failure);
    J tokens()const;J payload(std::string action,J fields=J::object())const;
    void mutate(std::string action,J fields=J::object(),std::function<void(const J&)> after={});
    void openProject(fs::path path={});void saveProject(bool as=false);bool saveBefore(std::function<void()> next);
    void exportPng();void seek(int target,bool pause=true);void playback();void togglePlayback();void seekTime(double value,bool pause=true);
    Rect currentRect()const;bool canWrite()const;void setColor(Pixel color);void setZoom(double value,int x=-1,int y=-1);void fit();
    void frameCacheUpdate();void paintCanvas(HDC dc,RECT area);LRESULT canvasEvent(UINT,WPARAM,LPARAM);void beginStroke(int x,int y);void moveStroke(int x,int y);void endStroke(bool cancel=false);void commitStroke();
    void paintUvGuides(HDC dc,RECT area,double ox,double oy,int repeats);void paintUvInspector(HDC dc,RECT area);void inspectUvPixel(int x,int y,bool pin=false);void clearUvPin();J uvStatus()const;
    void chooseInk();void paintDetails(HDC dc,RECT r);void paintTimeline(HDC dc,RECT r);void paintScene(HDC dc,RECT r);void paintStatus(HDC dc,RECT r);
    void drawButton(const DRAWITEMSTRUCT& item);void syncPlayback();
    void requestRender();void renderComplete(RenderReady* result);J uiStatus()const;J uiHelp()const;J uiCommand(const J& command);J metrics()const;void capture(const fs::path& path,bool overwrite=false);
    bool key(MSG& message);void close();LRESULT procedure(UINT,WPARAM,LPARAM);static LRESULT CALLBACK proc(HWND,UINT,WPARAM,LPARAM);
    void selectTool(int index);void tooltips();J controls()const;
    void userAction(std::function<void()> callback);
    void resetScenePlayer();void syncStateControls(bool rebuild=false);void stateAction(const std::string& action,const std::string& identity="",bool resume=true);void programTextureStep();void advanceProgram(double delta);double sceneClock()const;double sceneDuration()const;
    HCURSOR canvasCursor();void updateCanvasCursor();
    void selectionAction(std::string action);void updateSelection(int x,int y);void clearSelection();
    void startLease();void editPixels(Image next,Rect region);
};
}
