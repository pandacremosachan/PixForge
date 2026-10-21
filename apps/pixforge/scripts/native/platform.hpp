#pragma once
#define NOMINMAX
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <windowsx.h>
#include <winhttp.h>
#include <bcrypt.h>
#include <commctrl.h>
#include <commdlg.h>
#include <objidl.h>
#include <gdiplus.h>
#include <shellapi.h>
#include <shlobj.h>
#include "resource.h"
#include <filesystem>
#include <fstream>
#include <sstream>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <future>
#include <functional>
#include <atomic>
#include <chrono>
#include "render.hpp"

#pragma comment(lib,"user32.lib")
#pragma comment(lib,"gdi32.lib")
#pragma comment(lib,"gdiplus.lib")
#pragma comment(lib,"comctl32.lib")
#pragma comment(lib,"comdlg32.lib")
#pragma comment(lib,"shell32.lib")
#pragma comment(lib,"ole32.lib")
#pragma comment(lib,"winhttp.lib")
#pragma comment(lib,"ws2_32.lib")
#pragma comment(lib,"bcrypt.lib")

namespace pf {
namespace fs=std::filesystem;
inline HICON applicationIcon(int size){return static_cast<HICON>(LoadImageW(GetModuleHandleW(nullptr),MAKEINTRESOURCEW(IDI_PIXFORGE),IMAGE_ICON,size,size,LR_SHARED));}
inline void applicationIcons(WNDCLASSEXW& wc){wc.hIcon=applicationIcon(GetSystemMetrics(SM_CXICON));wc.hIconSm=applicationIcon(GetSystemMetrics(SM_CXSMICON));}
inline void updateWindowIcons(HWND window){auto dpi=GetDpiForWindow(window);SendMessageW(window,WM_SETICON,ICON_BIG,LPARAM(applicationIcon(GetSystemMetricsForDpi(SM_CXICON,dpi))));SendMessageW(window,WM_SETICON,ICON_SMALL,LPARAM(applicationIcon(GetSystemMetricsForDpi(SM_CXSMICON,dpi))));}
inline std::wstring wide(const std::string& s){if(s.empty())return {};int n=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),int(s.size()),nullptr,0);if(!n)throw std::runtime_error("Invalid UTF-8 text");std::wstring w(n,0);MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),int(s.size()),w.data(),n);return w;}
inline std::string utf8(const std::wstring& w){if(w.empty())return {};int n=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,w.data(),int(w.size()),nullptr,0,nullptr,nullptr);if(!n)throw std::runtime_error("Invalid UTF-16 text");std::string s(n,0);WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,w.data(),int(w.size()),s.data(),n,nullptr,nullptr);return s;}
inline std::string pathText(const fs::path& p){return utf8(p.wstring());}
inline std::string readFile(const fs::path& path,size_t limit=128*1024*1024){std::ifstream f(path,std::ios::binary);if(!f)throw std::runtime_error("Cannot open "+pathText(path));f.seekg(0,std::ios::end);auto size=f.tellg();if(size<0||uint64_t(size)>limit)throw std::runtime_error("File too large");f.seekg(0);std::string data(size_t(size),'\0');if(size&&!f.read(data.data(),size))throw std::runtime_error("Cannot read file");return data;}
inline void writeFile(const fs::path& path,const std::string& content){fs::create_directories(path.parent_path());std::ofstream f(path,std::ios::binary|std::ios::trunc);if(!f||!f.write(content.data(),std::streamsize(content.size())))throw std::runtime_error("Cannot write "+pathText(path));}
inline void atomicFile(const fs::path& path,const std::string& content){auto tmp=path;tmp+=L".native.tmp";writeFile(tmp,content);if(!MoveFileExW(tmp.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))throw std::runtime_error("Cannot publish session file");}
inline std::string randomHex(size_t n){std::vector<unsigned char> b(n);if(BCryptGenRandom(nullptr,b.data(),ULONG(n),BCRYPT_USE_SYSTEM_PREFERRED_RNG))throw std::runtime_error("Random generator failed");static constexpr char hex[]="0123456789abcdef";std::string out;for(auto c:b){out+=hex[c>>4];out+=hex[c&15];}return out;}
inline bool equalSecret(const std::string& a,const std::string& b){if(a.size()!=b.size())return false;unsigned diff=0;for(size_t i=0;i<a.size();++i)diff|=uint8_t(a[i])^uint8_t(b[i]);return diff==0;}
inline double milliseconds(){using namespace std::chrono;return duration<double,std::milli>(steady_clock::now().time_since_epoch()).count();}
inline std::string trim(std::string s){auto ws=[](char c){return c==' '||c=='\t'||c=='\r'||c=='\n';};while(!s.empty()&&ws(s.back()))s.pop_back();size_t i=0;while(i<s.size()&&ws(s[i]))++i;return s.substr(i);}
inline Rect rectJson(const J& a){return{a[0].integer(),a[1].integer(),a[2].integer(),a[3].integer()};}
inline J readJson(const fs::path& p){return J::parse(readFile(p));}
inline std::wstring quoteArgument(const std::wstring& value){std::wstring out=L"\"";size_t slashes=0;for(wchar_t c:value){if(c==L'\\'){++slashes;continue;}if(c==L'\"'){out.append(slashes*2+1,L'\\');out+=c;}else{out.append(slashes,L'\\');out+=c;}slashes=0;}out.append(slashes*2,L'\\');return out+L'\"';}
struct HttpHandle {HINTERNET h=nullptr;explicit HttpHandle(HINTERNET x=nullptr):h(x){}~HttpHandle(){if(h)WinHttpCloseHandle(h);}operator HINTERNET()const{return h;}HttpHandle(const HttpHandle&)=delete;};
inline J httpCall(const fs::path& runtime,const J& payload){
    J session=readJson(runtime/L"session.json");std::string uri=session["url"].str(),prefix="http://127.0.0.1:";if(uri.compare(0,prefix.size(),prefix)!=0)throw std::runtime_error("Session must use loopback HTTP");auto portText=uri.substr(prefix.size());if(portText.empty()||portText.find_first_not_of("0123456789")!=std::string::npos)throw std::runtime_error("Invalid session port");int port=std::stoi(portText);if(port<1||port>65535)throw std::runtime_error("Invalid session port");
    HttpHandle agent(WinHttpOpen(L"PixForge-Native/1.9",WINHTTP_ACCESS_TYPE_NO_PROXY,WINHTTP_NO_PROXY_NAME,WINHTTP_NO_PROXY_BYPASS,0));if(!agent.h)throw std::runtime_error("HTTP initialization failed");WinHttpSetTimeouts(agent,1000,1000,25000,25000);
    HttpHandle connection(WinHttpConnect(agent,L"127.0.0.1",INTERNET_PORT(port),0));HttpHandle request(WinHttpOpenRequest(connection,L"POST",L"/api",nullptr,WINHTTP_NO_REFERER,WINHTTP_DEFAULT_ACCEPT_TYPES,0));if(!request.h)throw std::runtime_error("HTTP request failed");
    auto body=payload.dump();auto headers=wide("Content-Type: application/json\r\nX-PixForge-Session: "+session["token"].str()+"\r\n");if(!WinHttpSendRequest(request,headers.c_str(),DWORD(headers.size()),body.data(),DWORD(body.size()),DWORD(body.size()),0)||!WinHttpReceiveResponse(request,nullptr))throw std::runtime_error("Core unavailable; reread session state before retrying");
    std::string response;for(;;){DWORD n=0;if(!WinHttpQueryDataAvailable(request,&n))throw std::runtime_error("HTTP read failed");if(!n)break;if(response.size()+n>128*1024*1024)throw std::runtime_error("Response too large");size_t p=response.size();response.resize(p+n);DWORD got=0;if(!WinHttpReadData(request,response.data()+p,n,&got))throw std::runtime_error("HTTP read failed");response.resize(p+got);}
    return J::parse(response);
}
inline fs::path executablePath(){std::vector<wchar_t> path(32768);DWORD n=GetModuleFileNameW(nullptr,path.data(),DWORD(path.size()));if(!n||n>=path.size())throw std::runtime_error("Cannot resolve native executable path");return fs::path(std::wstring(path.data(),n));}
struct CoreInstallation {fs::path python,sourceEntry,defaultWorkspace;};
inline CoreInstallation coreInstallation(){
    auto root=executablePath().parent_path();auto bundled=root/L"backend"/L"python.exe";
    if(fs::is_regular_file(bundled))return {bundled,{},root/L"workspace"};
    auto configuration=root/L"pixforge-development.json";
    if(fs::is_regular_file(configuration)){
        auto data=readJson(configuration);if(data["schema"].str()!="pixforge.development-install/v1")throw std::runtime_error("Unsupported PixForge development installation");
        auto resolve=[&](const char* name){auto p=fs::path(wide(data[name].str()));return p.is_absolute()?p:fs::absolute(root/p);};
        auto python=resolve("python"),entry=resolve("entry"),workspace=resolve("workspace");
        if(fs::is_regular_file(python)&&fs::is_regular_file(entry))return {python,entry,workspace};
    }
    return {{},{},root/L"workspace"};
}
inline std::wstring coreCommand(const CoreInstallation& installation){return quoteArgument(installation.python.wstring())+L" -B "+(installation.sourceEntry.empty()?L"-m pixelforge":quoteArgument(installation.sourceEntry.wstring()));}
inline int runPublicCommand(const std::vector<std::wstring>& arguments){
    auto installation=coreInstallation();if(installation.python.empty())throw std::runtime_error("找不到软件运行环境；请使用完整的 PixForge 软件包。");
    std::wstring command=coreCommand(installation);for(auto& argument:arguments)command+=L" "+quoteArgument(argument);
    SetEnvironmentVariableW(L"PYTHONUTF8",L"1");SetEnvironmentVariableW(L"PYTHONIOENCODING",L"utf-8");
    STARTUPINFOW startup{sizeof startup};PROCESS_INFORMATION process{};startup.dwFlags=STARTF_USESTDHANDLES;
    HANDLE streams[3]{};DWORD ids[3]={STD_INPUT_HANDLE,STD_OUTPUT_HANDLE,STD_ERROR_HANDLE};
    for(int i=0;i<3;++i){auto original=GetStdHandle(ids[i]);if(original&&original!=INVALID_HANDLE_VALUE)DuplicateHandle(GetCurrentProcess(),original,GetCurrentProcess(),&streams[i],0,TRUE,DUPLICATE_SAME_ACCESS);}
    startup.hStdInput=streams[0];startup.hStdOutput=streams[1];startup.hStdError=streams[2];
    BOOL started=CreateProcessW(installation.python.c_str(),command.data(),nullptr,nullptr,TRUE,CREATE_NO_WINDOW,nullptr,nullptr,&startup,&process);for(auto stream:streams)if(stream)CloseHandle(stream);
    if(!started)throw std::runtime_error("Cannot start PixForge public CLI/MCP");
    CloseHandle(process.hThread);WaitForSingleObject(process.hProcess,INFINITE);DWORD code=1;GetExitCodeProcess(process.hProcess,&code);CloseHandle(process.hProcess);return int(code);
}
inline void ensurePortableCore(const fs::path& workspace,const fs::path& runtime){
    try{auto state=httpCall(runtime,J::object({{"action","status"}}));if(state.contains("document_id"))return;}catch(...){}
    auto installation=coreInstallation();if(installation.python.empty())throw std::runtime_error("未找到 PixForge 核心运行环境。\n\n请完整解压软件包，并将 PixForgeNative.exe 与 backend 文件夹放在同一目录。开发构建需要同目录的 pixforge-development.json。软件运行不需要安装 skill。\n\n程序位置："+pathText(executablePath()));
    fs::create_directories(workspace);fs::create_directories(runtime);std::wstring command=coreCommand(installation)+L" serve --workspace "+quoteArgument(workspace.wstring())+L" --runtime "+quoteArgument(runtime.wstring());STARTUPINFOW startup{sizeof startup};PROCESS_INFORMATION process{};SECURITY_ATTRIBUTES security{sizeof security,nullptr,TRUE};HANDLE log=CreateFileW((runtime/L"service.log").c_str(),FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,&security,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr),input=CreateFileW(L"NUL",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,&security,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);startup.dwFlags=STARTF_USESTDHANDLES;startup.hStdOutput=startup.hStdError=log;startup.hStdInput=input;
    BOOL started=CreateProcessW(installation.python.c_str(),command.data(),nullptr,nullptr,TRUE,CREATE_NO_WINDOW,nullptr,workspace.c_str(),&startup,&process);if(log!=INVALID_HANDLE_VALUE)CloseHandle(log);if(input!=INVALID_HANDLE_VALUE)CloseHandle(input);if(!started)throw std::runtime_error("无法启动 PixForge 核心，请检查私有运行环境。日志："+pathText(runtime/L"service.log"));CloseHandle(process.hThread);CloseHandle(process.hProcess);
    for(int i=0;i<100;++i){try{auto state=httpCall(runtime,J::object({{"action","status"}}));if(state.contains("document_id"))return;}catch(...){}Sleep(100);}throw std::runtime_error("PixForge 核心未能就绪。请查看日志："+pathText(runtime/L"service.log"));
}
constexpr UINT WM_RPC=WM_APP+41,WM_FRONTEND=WM_APP+42,WM_RENDER=WM_APP+43;
struct RpcResult {uint64_t id;J value;double ms;};
class Rpc {
    struct Task{uint64_t id;J payload;};std::deque<Task> tasks;std::mutex mutex;std::condition_variable wake;std::thread worker;bool closing=false;std::atomic<int> pending{0};uint64_t sequence=0;HWND window;fs::path runtime;
public:
    std::map<uint64_t,std::function<void(const J&)>> callbacks;std::function<void(const J&)> onError;double lastMs=0;uint64_t count=0;
    Rpc(HWND hwnd,fs::path root):window(hwnd),runtime(std::move(root)){
        worker=std::thread([this]{for(;;){Task task;{std::unique_lock<std::mutex> lock(mutex);wake.wait(lock,[&]{return closing||!tasks.empty();});if(closing)break;task=std::move(tasks.front());tasks.pop_front();}double started=milliseconds();J value;try{value=httpCall(runtime,task.payload);}catch(std::exception& e){value=J::object({{"error",e.what()},{"code","SESSION_UNAVAILABLE"}});}auto result=new RpcResult{task.id,std::move(value),milliseconds()-started};--pending;if(!PostMessageW(window,WM_RPC,0,LPARAM(result)))delete result;}});
    }
    ~Rpc(){{std::lock_guard<std::mutex> lock(mutex);closing=true;tasks.clear();}wake.notify_all();if(worker.joinable())worker.join();}
    void call(J payload,std::function<void(const J&)> callback={},bool quiet=false){uint64_t id=++sequence;callbacks[id]=[this,callback,quiet](const J& response){if(response.contains("error")){if(!quiet&&onError)onError(response);else if(quiet&&callback)callback(response);return;}if(callback)callback(response);};{std::lock_guard<std::mutex> lock(mutex);tasks.push_back({id,std::move(payload)});++pending;}wake.notify_one();}
    bool idle()const{return pending==0;}
    void complete(RpcResult* raw){std::unique_ptr<RpcResult> result(raw);lastMs=result->ms;++count;auto it=callbacks.find(result->id);if(it!=callbacks.end()){auto callback=std::move(it->second);callbacks.erase(it);callback(result->value);}}
};
struct FrontendRequest {J payload;std::promise<J> promise;std::atomic<bool> cancelled{false};};
class Frontend {
    HWND window;fs::path runtime;SOCKET listener=INVALID_SOCKET;std::thread thread;std::atomic<bool> stopping{false};std::string token,id;HANDLE lock=INVALID_HANDLE_VALUE;
    void send(SOCKET socket,int status,const J& value){auto body=value.dump();std::string headers="HTTP/1.1 "+std::to_string(status)+(status==200?" OK":" Error")+"\r\nContent-Type: application/json; charset=utf-8\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: "+std::to_string(body.size())+"\r\n\r\n";auto all=headers+body;size_t p=0;while(p<all.size()){int n=::send(socket,all.data()+p,int(pf::min<size_t>(all.size()-p,65536)),0);if(n<=0)break;p+=n;}}
    void serve(SOCKET client){
        DWORD timeout=25000;setsockopt(client,SOL_SOCKET,SO_RCVTIMEO,reinterpret_cast<const char*>(&timeout),sizeof timeout);setsockopt(client,SOL_SOCKET,SO_SNDTIMEO,reinterpret_cast<const char*>(&timeout),sizeof timeout);
        try{std::string data;size_t end=std::string::npos;char buffer[8192];while((end=data.find("\r\n\r\n"))==std::string::npos){int n=recv(client,buffer,sizeof buffer,0);if(n<=0)return;data.append(buffer,n);if(data.size()>32768)throw std::runtime_error("Headers too large");}
            auto lineEnd=data.find("\r\n");auto first=data.substr(0,lineEnd);if(first=="GET /health HTTP/1.1"||first=="GET /health HTTP/1.0"){send(client,200,J::object({{"application","PixForge"},{"session_id",id},{"mode","native"}}));return;}
            std::map<std::string,std::string> headers;size_t p=lineEnd+2;while(p<end){auto e=data.find("\r\n",p);auto line=data.substr(p,e-p);auto colon=line.find(':');if(colon==std::string::npos)throw std::runtime_error("Invalid header");auto key=line.substr(0,colon);std::transform(key.begin(),key.end(),key.begin(),[](unsigned char c){return char(std::tolower(c));});if(headers.count(key))throw std::runtime_error("Duplicate header");headers[key]=trim(line.substr(colon+1));p=e+2;}
            if((first!="POST /api HTTP/1.1"&&first!="POST /api HTTP/1.0")||!equalSecret(headers["x-pixforge-session"],token)){send(client,401,J::object({{"error","Local session credentials required"},{"code","AUTH_REQUIRED"}}));return;}
            if(headers.count("origin")||headers.count("transfer-encoding"))throw std::runtime_error("Browser origins and chunked bodies are unsupported");auto lengthText=headers["content-length"];if(lengthText.empty()||lengthText.find_first_not_of("0123456789")!=std::string::npos)throw std::runtime_error("Invalid request size");size_t length=std::stoull(lengthText);if(!length||length>16000000||headers["content-type"].find("application/json")!=0)throw std::runtime_error("Expected JSON up to 16MB");std::string body=data.substr(end+4);while(body.size()<length){int n=recv(client,buffer,int(pf::min<size_t>(sizeof buffer,length-body.size())),0);if(n<=0)return;body.append(buffer,n);}if(body.size()!=length)throw std::runtime_error("Invalid body size");
            auto request=std::make_shared<FrontendRequest>();request->payload=J::parse(body);auto future=request->promise.get_future();auto raw=new std::shared_ptr<FrontendRequest>(request);if(!PostMessageW(window,WM_FRONTEND,0,LPARAM(raw))){delete raw;return;}if(future.wait_for(std::chrono::seconds(20))!=std::future_status::ready){request->cancelled=true;send(client,503,J::object({{"error","Frontend busy; reread UI state"},{"code","BUSY"}}));return;}auto response=future.get();send(client,response.contains("error")?400:200,response);
        }catch(std::exception& e){send(client,400,J::object({{"error",e.what()},{"code","INVALID_ARGUMENT"}}));}
    }
public:
    Frontend(HWND hwnd,fs::path root):window(hwnd),runtime(std::move(root)),token(randomHex(32)),id(randomHex(16)){
        fs::create_directories(runtime);lock=CreateFileW((runtime/L"native.lock").c_str(),GENERIC_READ|GENERIC_WRITE,0,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(lock==INVALID_HANDLE_VALUE)throw std::runtime_error("A native frontend is already opening this session");
        WSADATA wsa{};if(WSAStartup(MAKEWORD(2,2),&wsa))throw std::runtime_error("Socket initialization failed");listener=socket(AF_INET,SOCK_STREAM,IPPROTO_TCP);BOOL exclusive=TRUE;setsockopt(listener,SOL_SOCKET,SO_EXCLUSIVEADDRUSE,reinterpret_cast<const char*>(&exclusive),sizeof exclusive);sockaddr_in address{};address.sin_family=AF_INET;address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);if(bind(listener,reinterpret_cast<sockaddr*>(&address),sizeof address)||listen(listener,8))throw std::runtime_error("Cannot bind frontend loopback socket");int len=sizeof address;getsockname(listener,reinterpret_cast<sockaddr*>(&address),&len);
        atomicFile(runtime/L"session.json",J::object({{"url","http://127.0.0.1:"+std::to_string(ntohs(address.sin_port))},{"token",token},{"session_id",id},{"pid",int(GetCurrentProcessId())},{"mode","native"},{"implementation","C++20/Win32"}}).dump());
        thread=std::thread([this]{while(!stopping){SOCKET client=accept(listener,nullptr,nullptr);if(client==INVALID_SOCKET)break;serve(client);closesocket(client);}});
    }
    ~Frontend(){stopping=true;if(listener!=INVALID_SOCKET){shutdown(listener,SD_BOTH);closesocket(listener);}if(thread.joinable())thread.join();try{auto record=readJson(runtime/L"session.json");if(record["session_id"].str()==id)fs::remove(runtime/L"session.json");}catch(...){}if(lock!=INVALID_HANDLE_VALUE)CloseHandle(lock);WSACleanup();}
};
inline bool savePng(const Image& image,const fs::path& path){
    std::vector<uint8_t> bgra(image.bytes.size());for(size_t i=0;i<bgra.size();i+=4){bgra[i]=image.bytes[i+2];bgra[i+1]=image.bytes[i+1];bgra[i+2]=image.bytes[i];bgra[i+3]=image.bytes[i+3];}
    Gdiplus::Bitmap bitmap(image.w,image.h,image.w*4,PixelFormat32bppARGB,bgra.data());UINT count=0,size=0;Gdiplus::GetImageEncodersSize(&count,&size);std::vector<uint8_t> storage(size);auto codecs=reinterpret_cast<Gdiplus::ImageCodecInfo*>(storage.data());Gdiplus::GetImageEncoders(count,size,codecs);for(UINT i=0;i<count;++i)if(std::wcscmp(codecs[i].MimeType,L"image/png")==0){fs::create_directories(path.parent_path());return bitmap.Save(path.c_str(),&codecs[i].Clsid,nullptr)==Gdiplus::Ok;}return false;
}
}
