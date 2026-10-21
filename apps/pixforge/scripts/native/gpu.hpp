#pragma once
#include "widgets.hpp"
#include <gl/GL.h>
#pragma comment(lib,"opengl32.lib")

namespace pf {
// A persistent system OpenGL context keeps orbiting independent of raster jobs,
// JSON, HTTP and texture uploads. The CPU renderer remains the offline reference
// and the fallback when a hardware context is unavailable.
class GpuScene {
    HWND window;HDC dc=nullptr;HGLRC context=nullptr;GLuint texture=0,checkerTexture=0;std::vector<Face> faces;
    J shapes,scene,sceneView;double sceneAt=0;Vec center;double radius=1,yaw=25,pitch=20,zoom=1;bool showModel=true,emptyTexture=false;
    std::vector<std::string> overlays;int referenceSize=400,background=0;bool prepared=false;
public:
    bool available=false;std::string vendor,device;double lastMs=0;uint64_t frames=0,uploads=0,geometryBuilds=0;
    explicit GpuScene(HWND hwnd):window(hwnd){
        wchar_t disabled[8]{};if(GetEnvironmentVariableW(L"PIXFORGE_DISABLE_GPU",disabled,8)&&std::wstring(disabled)==L"1")return;
        dc=GetDC(window);PIXELFORMATDESCRIPTOR format{};format.nSize=sizeof format;format.nVersion=1;format.dwFlags=PFD_DRAW_TO_WINDOW|PFD_SUPPORT_OPENGL|PFD_DOUBLEBUFFER;format.iPixelType=PFD_TYPE_RGBA;format.cColorBits=32;format.cAlphaBits=8;format.cDepthBits=24;format.iLayerType=PFD_MAIN_PLANE;int index=ChoosePixelFormat(dc,&format);if(!index||!SetPixelFormat(dc,index,&format))return;context=wglCreateContext(dc);if(!context||!wglMakeCurrent(dc,context))return;
        auto string=[](GLenum name){auto p=glGetString(name);return p?std::string(reinterpret_cast<const char*>(p)):std::string();};vendor=string(GL_VENDOR);device=string(GL_RENDERER);
        if(device.find("GDI Generic")!=std::string::npos||device.empty()){wglMakeCurrent(nullptr,nullptr);return;}
        using SwapInterval=BOOL(WINAPI*)(int);auto swap=reinterpret_cast<SwapInterval>(wglGetProcAddress("wglSwapIntervalEXT"));if(swap)swap(1);
        glGenTextures(1,&checkerTexture);glBindTexture(GL_TEXTURE_2D,checkerTexture);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_REPEAT);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_REPEAT);const uint8_t checker[]={55,59,68,255,65,70,80,255,65,70,80,255,55,59,68,255};glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,2,2,0,GL_RGBA,GL_UNSIGNED_BYTE,checker);
        glGenTextures(1,&texture);glBindTexture(GL_TEXTURE_2D,texture);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_REPEAT);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_REPEAT);glTexEnvi(GL_TEXTURE_ENV,GL_TEXTURE_ENV_MODE,GL_MODULATE);glPixelStorei(GL_UNPACK_ALIGNMENT,1);available=true;
    }
    ~GpuScene(){if(context){wglMakeCurrent(dc,context);if(texture)glDeleteTextures(1,&texture);if(checkerTexture)glDeleteTextures(1,&checkerTexture);wglMakeCurrent(nullptr,nullptr);wglDeleteContext(context);}if(dc)ReleaseDC(window,dc);}
    void angles(double y,double p){yaw=y;pitch=p;}
    void time(double value){sceneAt=value;}
    void playback(const J& view){sceneView=view;}
    void magnification(double value){zoom=value;}
    void setBackground(int mode){background=pf::clamp(mode,0,2);}
    void configure(const J& definition,const Image& atlas,const std::vector<std::string>& visible,bool model,const J& animation=J()){
        if(!available)return;overlays=visible;showModel=model;shapes=definition;scene=animation;emptyTexture=!hasVisiblePixels(atlas);
        faces=modelMesh(definition["model"]);auto bound=sceneBounds(definition,faces,scene);center=bound.first;radius=bound.second;referenceSize=400;
        ++geometryBuilds;wglMakeCurrent(dc,context);glBindTexture(GL_TEXTURE_2D,texture);glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,atlas.w,atlas.h,0,GL_RGBA,GL_UNSIGNED_BYTE,atlas.bytes.data());++uploads;prepared=true;
    }
    bool draw(int width,int height){
        if(!available||!prepared||width<=0||height<=0)return false;double started=milliseconds();wglMakeCurrent(dc,context);glViewport(0,0,width,height);auto bg=backgroundPixel(background);glClearColor(bg[0]/255.f,bg[1]/255.f,bg[2]/255.f,1);glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT);if(background==0){glDisable(GL_DEPTH_TEST);glDisable(GL_BLEND);glDisable(GL_ALPHA_TEST);glMatrixMode(GL_PROJECTION);glLoadIdentity();glMatrixMode(GL_MODELVIEW);glLoadIdentity();glEnable(GL_TEXTURE_2D);glBindTexture(GL_TEXTURE_2D,checkerTexture);glColor4f(1,1,1,1);glBegin(GL_QUADS);glTexCoord2d(0,0);glVertex2d(-1,-1);glTexCoord2d(width/16.,0);glVertex2d(1,-1);glTexCoord2d(width/16.,height/16.);glVertex2d(1,1);glTexCoord2d(0,height/16.);glVertex2d(-1,1);glEnd();}int side=pf::max(1,pf::min(width-16,height-24));glViewport((width-side)/2,(height-side)/2,side,side);glMatrixMode(GL_PROJECTION);glLoadIdentity();glMatrixMode(GL_MODELVIEW);glLoadIdentity();glEnable(GL_TEXTURE_2D);glBindTexture(GL_TEXTURE_2D,texture);glEnable(GL_ALPHA_TEST);glAlphaFunc(GL_GREATER,0);glEnable(GL_BLEND);glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA);glEnable(GL_DEPTH_TEST);glDepthFunc(GL_LEQUAL);glDepthMask(GL_TRUE);Camera camera(center,radius,referenceSize,yaw,pitch,50,zoom);
        auto vertex=[&](Vec p){auto v=camera.project(p);glVertex3d(v.x/referenceSize*2-1,1-v.y/referenceSize*2,-v.z/(radius*2));};
        auto posed=poseMesh(faces,scene,sceneAt,sceneView);auto& activeFaces=posed;
        std::vector<int> order;for(int i=0;i<int(activeFaces.size());++i)if(activeFaces[i].normal.dot(camera.depth)>1e-9)order.push_back(i);
        if(showModel){glBegin(GL_TRIANGLES);for(int i:order){auto& face=activeFaces[i];glColor4d(face.shade,face.shade,face.shade,1);for(int n:{0,1,2,0,2,3}){glTexCoord2d(face.uv[n][0],face.uv[n][1]);vertex(face.points[n]);}}glEnd();}
        glDisable(GL_TEXTURE_2D);glDisable(GL_ALPHA_TEST);
        if(!scene.null()){auto particles=sceneParticles(scene,sceneAt,sceneView);std::stable_sort(particles.begin(),particles.end(),[&](auto& a,auto& b){return a.position.dot(camera.depth)<b.position.dot(camera.depth);});glEnable(GL_DEPTH_TEST);glDepthMask(GL_FALSE);glEnable(GL_BLEND);for(auto& p:particles){glBlendFunc(GL_SRC_ALPHA,p.additive?GL_ONE:GL_ONE_MINUS_SRC_ALPHA);glColor4d(p.color[0]/255.,p.color[1]/255.,p.color[2]/255.,p.color[3]/255.);auto right=camera.right*(p.size*.5),up=camera.up*(p.size*.5);glBegin(GL_QUADS);vertex(p.position-right+up);vertex(p.position-right-up);vertex(p.position+right-up);vertex(p.position+right+up);glEnd();}glDepthMask(GL_TRUE);glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA);}
        glDisable(GL_DEPTH_TEST);glDisable(GL_BLEND);
        if(showModel&&emptyTexture){glColor3ub(153,176,205);glBegin(GL_LINES);for(int i:order)for(int edge=0;edge<4;++edge){vertex(activeFaces[i].points[edge]);vertex(activeFaces[i].points[(edge+1)%4]);}glEnd();}
        {static constexpr int edges[][2]={{0,1},{1,2},{2,3},{3,0},{4,5},{5,6},{6,7},{7,4},{0,4},{1,5},{2,6},{3,7}};glBegin(GL_LINES);for(auto& target:overlays){Pixel c=target=="base"?Pixel{255,202,104,255}:target=="collision"?Pixel{255,103,139,255}:Pixel{98,229,255,255};glColor3ub(c[0],c[1],c[2]);for(auto& box:effective(shapes,target).arr()){auto vv=vertices(vec(box["from"]),vec(box["to"]));for(auto& edge:edges){vertex(vv[edge[0]]);vertex(vv[edge[1]]);}}}glEnd();}
        SwapBuffers(dc);lastMs=milliseconds()-started;++frames;return true;
    }
    Image readback(){RECT r;GetClientRect(window,&r);draw(r.right,r.bottom);Image out(r.right,r.bottom);std::vector<uint8_t> raw(out.bytes.size());wglMakeCurrent(dc,context);glReadBuffer(GL_FRONT);glPixelStorei(GL_PACK_ALIGNMENT,1);glReadPixels(0,0,r.right,r.bottom,GL_RGBA,GL_UNSIGNED_BYTE,raw.data());for(int y=0;y<out.h;++y)std::memcpy(out.bytes.data()+size_t(y)*out.w*4,raw.data()+size_t(out.h-1-y)*out.w*4,size_t(out.w)*4);glReadBuffer(GL_BACK);return out;}
    bool ready()const{return available&&prepared;}
    J metrics()const{return J::object({{"available",available},{"backend",available?"OpenGL hardware":"C++ raster fallback"},{"vendor",vendor},{"device",device},{"presented_frames",size_t(frames)},{"texture_uploads",size_t(uploads)},{"geometry_builds",size_t(geometryBuilds)},{"background",std::array<const char*,3>{"checker","light","dark"}[background]},{"last_frame_ms",lastMs}});}
};
}
