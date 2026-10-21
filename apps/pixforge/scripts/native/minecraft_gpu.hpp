#pragma once
#include "minecraft_render.hpp"
#include <gl/GL.h>
#pragma comment(lib,"opengl32.lib")

namespace pf {
class McGpu {
    HWND window;HDC dc=nullptr;HGLRC context=nullptr;
    struct Texture {GLuint id=0;std::string hash;int levels=0;};
    std::map<std::string,Texture> textures;
    GLuint program=0;GLint cutoffLocation=-1,rawAlphaLocation=-1;
    using CreateShader=GLuint(APIENTRY*)(GLenum);using ShaderSource=void(APIENTRY*)(GLuint,GLsizei,const char* const*,const GLint*);using CompileShader=void(APIENTRY*)(GLuint);using ShaderInfo=void(APIENTRY*)(GLuint,GLenum,GLint*);
    using CreateProgram=GLuint(APIENTRY*)();using AttachShader=void(APIENTRY*)(GLuint,GLuint);using ProgramOp=void(APIENTRY*)(GLuint);using UniformLocation=GLint(APIENTRY*)(GLuint,const char*);using Uniform1f=void(APIENTRY*)(GLint,GLfloat);using Uniform1i=void(APIENTRY*)(GLint,GLint);
    ProgramOp useProgram=nullptr,deleteProgram=nullptr;Uniform1f uniformFloat=nullptr;Uniform1i uniformInt=nullptr;
    bool shaders(){
        auto create=reinterpret_cast<CreateShader>(wglGetProcAddress("glCreateShader"));auto source=reinterpret_cast<ShaderSource>(wglGetProcAddress("glShaderSource"));auto compile=reinterpret_cast<CompileShader>(wglGetProcAddress("glCompileShader"));auto shaderInfo=reinterpret_cast<ShaderInfo>(wglGetProcAddress("glGetShaderiv"));auto newProgram=reinterpret_cast<CreateProgram>(wglGetProcAddress("glCreateProgram"));auto attach=reinterpret_cast<AttachShader>(wglGetProcAddress("glAttachShader"));auto link=reinterpret_cast<ProgramOp>(wglGetProcAddress("glLinkProgram"));auto programInfo=reinterpret_cast<ShaderInfo>(wglGetProcAddress("glGetProgramiv"));auto deleteShader=reinterpret_cast<ProgramOp>(wglGetProcAddress("glDeleteShader"));auto location=reinterpret_cast<UniformLocation>(wglGetProcAddress("glGetUniformLocation"));
        useProgram=reinterpret_cast<ProgramOp>(wglGetProcAddress("glUseProgram"));deleteProgram=reinterpret_cast<ProgramOp>(wglGetProcAddress("glDeleteProgram"));uniformFloat=reinterpret_cast<Uniform1f>(wglGetProcAddress("glUniform1f"));uniformInt=reinterpret_cast<Uniform1i>(wglGetProcAddress("glUniform1i"));
        if(!create||!source||!compile||!shaderInfo||!newProgram||!attach||!link||!programInfo||!deleteShader||!location||!useProgram||!deleteProgram||!uniformFloat||!uniformInt)return false;
        const char* vertex="#version 120\nvarying vec2 uv;varying vec4 tint;void main(){gl_Position=ftransform();uv=gl_MultiTexCoord0.xy;tint=gl_Color;}";
        const char* fragment="#version 120\nuniform sampler2D sprite;uniform float cutoff;uniform int rawAlpha;varying vec2 uv;varying vec4 tint;void main(){vec4 texel=texture2D(sprite,uv);vec4 color=texel*tint;if((rawAlpha!=0?texel.a:color.a)<cutoff)discard;gl_FragColor=color;}";
        GLuint vs=create(0x8b31),fs=create(0x8b30);source(vs,1,&vertex,nullptr);source(fs,1,&fragment,nullptr);compile(vs);compile(fs);GLint a=0,b=0;shaderInfo(vs,0x8b81,&a);shaderInfo(fs,0x8b81,&b);if(a&&b){program=newProgram();attach(program,vs);attach(program,fs);link(program);programInfo(program,0x8b82,&a);}deleteShader(vs);deleteShader(fs);if(!a||!b){if(program)deleteProgram(program);program=0;return false;}
        cutoffLocation=location(program,"cutoff");rawAlphaLocation=location(program,"rawAlpha");useProgram(program);uniformInt(location(program,"sprite"),0);useProgram(0);return true;
    }
    static constexpr GLenum BASE_LEVEL=0x813c,MAX_LEVEL=0x813d,CLAMP_EDGE=0x812f;
public:
    bool available=false;std::string vendor,device;uint64_t uploads=0,frames=0;double lastMs=0;
    explicit McGpu(HWND hwnd):window(hwnd){
        wchar_t disabled[8]{};if(GetEnvironmentVariableW(L"PIXFORGE_DISABLE_GPU",disabled,8)&&std::wstring(disabled)==L"1")return;
        dc=GetDC(window);PIXELFORMATDESCRIPTOR format{};format.nSize=sizeof format;format.nVersion=1;format.dwFlags=PFD_DRAW_TO_WINDOW|PFD_SUPPORT_OPENGL|PFD_DOUBLEBUFFER;format.iPixelType=PFD_TYPE_RGBA;format.cColorBits=32;format.cAlphaBits=8;format.cDepthBits=24;format.iLayerType=PFD_MAIN_PLANE;
        int index=ChoosePixelFormat(dc,&format);if(!index||!SetPixelFormat(dc,index,&format))return;context=wglCreateContext(dc);if(!context||!wglMakeCurrent(dc,context))return;
        auto get=[](GLenum kind){auto value=glGetString(kind);return value?std::string(reinterpret_cast<const char*>(value)):std::string();};vendor=get(GL_VENDOR);device=get(GL_RENDERER);
        available=!device.empty()&&device.find("GDI Generic")==std::string::npos;
        if(available)available=shaders();
        using SwapInterval=BOOL(WINAPI*)(int);auto swap=reinterpret_cast<SwapInterval>(wglGetProcAddress("wglSwapIntervalEXT"));if(swap)swap(0);
    }
    ~McGpu(){if(context){wglMakeCurrent(dc,context);for(auto& [key,texture]:textures)if(texture.id)glDeleteTextures(1,&texture.id);if(program)deleteProgram(program);wglMakeCurrent(nullptr,nullptr);wglDeleteContext(context);}if(dc)ReleaseDC(window,dc);}
    void prepare(const McScene& scene){
        if(!available)return;wglMakeCurrent(dc,context);glPixelStorei(GL_UNPACK_ALIGNMENT,1);std::set<std::string> used;
        for(auto& source:scene.textures){used.insert(source.id);auto& texture=textures[source.id];if(texture.id&&texture.hash==source.hash&&texture.levels==int(source.levels.size()))continue;
            if(!texture.id)glGenTextures(1,&texture.id);glBindTexture(GL_TEXTURE_2D,texture.id);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,CLAMP_EDGE);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,CLAMP_EDGE);glTexEnvi(GL_TEXTURE_ENV,GL_TEXTURE_ENV_MODE,GL_MODULATE);
            for(int i=0;i<int(source.levels.size());++i){auto& image=source.levels[i];glTexImage2D(GL_TEXTURE_2D,i,GL_RGBA,image.w,image.h,0,GL_RGBA,GL_UNSIGNED_BYTE,image.bytes.data());}
            texture.hash=source.hash;texture.levels=int(source.levels.size());++uploads;
        }
        for(auto it=textures.begin();it!=textures.end();){if(!used.count(it->first)){glDeleteTextures(1,&it->second.id);it=textures.erase(it);}else ++it;}
    }
    bool draw(const McScene& scene,const McCamera& camera,int width,int height,bool swap=true){
        if(!available||width<1||height<1)return false;double started=milliseconds();wglMakeCurrent(dc,context);glViewport(0,0,width,height);auto bg=scene.background;glClearColor(bg[0]/255.f,bg[1]/255.f,bg[2]/255.f,1.f);glDepthMask(GL_TRUE);glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT);glEnable(GL_DEPTH_TEST);glDepthFunc(GL_LEQUAL);glDisable(GL_DITHER);glDisable(GL_LIGHTING);glDisable(GL_FOG);
        McProjection p(scene,camera,width,height);glMatrixMode(GL_PROJECTION);glLoadIdentity();double aspect=double(width)/height;
        if(camera.perspective){double top=.1*std::tan(camera.fov*PI/360)/camera.zoom;glFrustum(-top*aspect,top*aspect,-top,top,.1,8192.);}else glOrtho(-p.halfHeight*aspect,p.halfHeight*aspect,-p.halfHeight,p.halfHeight,.1,8192.);
        glMatrixMode(GL_MODELVIEW);GLdouble matrix[]={p.right.x,p.up.x,p.depth.x,0,p.right.y,p.up.y,p.depth.y,0,p.right.z,p.up.z,p.depth.z,0,-p.center.dot(p.right),-p.center.dot(p.up),-p.center.dot(p.depth)-camera.distance,1};glLoadMatrixd(matrix);glEnable(GL_TEXTURE_2D);glFrontFace(GL_CCW);glCullFace(GL_BACK);glShadeModel(GL_SMOOTH);
        useProgram(program);glDisable(GL_ALPHA_TEST);for(auto& face:mcDrawFaces(scene,p)){
            auto found=textures.find(scene.textures[face.texture].id);if(found==textures.end())continue;auto& texture=found->second;glBindTexture(GL_TEXTURE_2D,texture.id);
            bool mip=face.layer.mipmapped&&scene.requestedMips>0;int forced=mip?pf::clamp(scene.forcedMip,0,texture.levels-1):0;int base=mip&&scene.forcedMip>=0?forced:0,maximum=mip?(scene.forcedMip>=0?base:texture.levels-1):0;
            glTexParameteri(GL_TEXTURE_2D,BASE_LEVEL,base);glTexParameteri(GL_TEXTURE_2D,MAX_LEVEL,maximum);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,mip?GL_NEAREST_MIPMAP_LINEAR:GL_NEAREST);
            if(face.twoSided)glDisable(GL_CULL_FACE);else glEnable(GL_CULL_FACE);
            uniformFloat(cutoffLocation,GLfloat(face.layer.cutoff));uniformInt(rawAlphaLocation,face.layer.textureAlpha?1:0);
            if(face.layer.blend){glEnable(GL_BLEND);glBlendFunc(GL_SRC_ALPHA,face.layer.additive?GL_ONE:GL_ONE_MINUS_SRC_ALPHA);}else glDisable(GL_BLEND);
            glDepthMask(face.layer.depthWrite?GL_TRUE:GL_FALSE);glBegin(GL_TRIANGLES);for(int i:{0,1,2,0,2,3}){auto& c=face.colors[i];glColor4d(c[0],c[1],c[2],c[3]);glTexCoord2d(face.uv[i][0],face.uv[i][1]);auto v=face.points[i];glVertex3d(v.x,v.y,v.z);}glEnd();
        }
        useProgram(0);glDepthMask(GL_TRUE);glDisable(GL_BLEND);glDisable(GL_ALPHA_TEST);glDisable(GL_CULL_FACE);glDisable(GL_TEXTURE_2D);if(swap)SwapBuffers(dc);lastMs=milliseconds()-started;++frames;return true;
    }
    Image readback(const McScene& scene,const McCamera& camera,int width,int height){
        if(!draw(scene,camera,width,height,false))throw std::runtime_error("Minecraft GPU preview unavailable");glFinish();glReadBuffer(GL_BACK);glPixelStorei(GL_PACK_ALIGNMENT,1);Image raw(width,height),out(width,height);glReadPixels(0,0,width,height,GL_RGBA,GL_UNSIGNED_BYTE,raw.bytes.data());for(int y=0;y<height;++y)for(int x=0;x<width;++x){auto p=raw.get(x,height-1-y);p[3]=255;out.set(x,y,p);}return out;
    }
    J metrics()const{return J::object({{"available",available},{"vendor",vendor},{"device",device},{"texture_uploads",uploads},{"frames",frames},{"last_frame_ms",lastMs}});}
};
}
