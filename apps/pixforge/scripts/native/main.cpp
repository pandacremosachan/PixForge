#include "app.hpp"
#include "minecraft_preview.hpp"
#include "minecraft_workbench.hpp"
#include "material_editor.hpp"
#include "commands.hpp"

namespace pf {
static void output(const std::string& text) {
    DWORD written = 0;
    auto handle = GetStdHandle(STD_OUTPUT_HANDLE);
    if (handle && handle != INVALID_HANDLE_VALUE)
        WriteFile(handle, text.data(), DWORD(text.size()), &written, nullptr);
}

static bool commandMode(const std::vector<std::wstring>& arguments) {
    for (size_t i = 0; i < arguments.size(); ++i) {
        const auto& value = arguments[i];
        if (value == L"--workspace" || value == L"--runtime" || value == L"--open" || value == L"--open-minecraft-preview") {
            if (++i == arguments.size()) return true;
        } else if (value == L"--open-material-editor" || value == L"--open-minecraft-workbench") {
            continue;
        } else if (value.rfind(L"--", 0) == 0) {
            return true;
        } else {
            auto extension = fs::path(value).extension().wstring();
            std::transform(extension.begin(), extension.end(), extension.begin(), [](wchar_t c) { return wchar_t(towlower(c)); });
            if (extension != L".pixforge" && extension != L".png") return true;
        }
    }
    return false;
}
}

// The resident host can open and close its native workbench on a UI thread.
// The same message loop is used when the desktop is launched directly.
static void runWindow(pf::App& app) {
    MSG message;
    while (GetMessageW(&message, nullptr, 0, 0) > 0) {
        try {
            if (app.key(message) || IsDialogMessageW(app.hwnd, &message)) continue;
        } catch (std::exception& error) {
            app.message = pf::wide(error.what());
            app.statusBar->redraw();
        }
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }
}

using WindowOptions = std::map<std::wstring, std::wstring>;
static WindowOptions firstWindow;

static void showWindow(const pf::fs::path& workspace, const pf::fs::path& runtime, const WindowOptions& opts) {
    using namespace pf;
    App app(workspace, runtime, opts.count(L"--open") ? pathText(fs::absolute(opts.at(L"--open"))) : "");
    if (opts.count(L"--open-material-editor"))
        app.userActions.push_back([&app] { openMaterialEditor(app); });
    if (opts.count(L"--open-minecraft-workbench"))
        app.userActions.push_back([&app] { openMinecraftWorkbench(app); });
    if (opts.count(L"--open-minecraft-preview")) {
        auto initial = readJson(opts.at(L"--open-minecraft-preview"));
        app.userActions.push_back([&app, initial] { openMinecraftPreview(app, initial); });
    }
    runWindow(app);
}

extern "C" __declspec(dllexport) int WINAPI PixForgeRunWorkbench(const wchar_t* workspace, const wchar_t* runtime) {
    auto com = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    int result = 0;
    try { WindowOptions initial; initial.swap(firstWindow); showWindow(workspace, runtime, initial); }
    catch (const std::exception& error) { pf::output(std::string(error.what()) + "\n"); result = 1; }
    if (SUCCEEDED(com)) CoUninitialize();
    return result;
}

// Load the application's own core in this EXE. The listening socket and the
// document then belong to the resident PID, with no interpreter subprocess.
static int runResident(const std::vector<std::wstring>& raw) {
    using namespace pf;
    if (raw.size() == 2 && (raw[1] == L"--help" || raw[1] == L"-h")) {
        commandWrite(GetStdHandle(STD_OUTPUT_HANDLE), "PixForgeNative.exe serve [--workspace DIR] [--runtime DIR]\nConnection: RUNTIME/commands.json (POST /v1/commands).\n");
        return 0;
    }
    auto installation = coreInstallation();
    if (!fs::is_regular_file(installation.library)) throw std::runtime_error("Missing PixForge core library; use the complete installation.");
    auto lib = LoadLibraryExW(installation.library.c_str(), nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
    auto run = lib ? reinterpret_cast<int (__cdecl*)(int, wchar_t**)>(GetProcAddress(lib, "Py_Main")) : nullptr;
    if (!run) throw std::runtime_error("Could not load the PixForge core library.");
    SetEnvironmentVariableW(L"PIXFORGE_NATIVE_EXE", executablePath().c_str());
    SetEnvironmentVariableW(L"__PYVENV_LAUNCHER__", installation.python.c_str());
    std::vector<std::wstring> args{installation.python.wstring(), L"-I", L"-B", L"-X", L"utf8"};
    if (installation.sourceEntry.empty()) { args.push_back(L"-m"); args.push_back(L"pixelforge"); }
    else args.push_back(installation.sourceEntry.wstring());
    args.insert(args.end(), raw.begin(), raw.end());
    std::vector<wchar_t*> argv;
    for (auto& arg : args) argv.push_back(arg.data());
    argv.push_back(nullptr);
    return run(static_cast<int>(args.size()), argv.data());
}

int wmain(int argc, wchar_t* argv[]) {
    using namespace pf;
    std::vector<std::wstring> raw;
    for (int i = 1; i < argc; ++i) raw.emplace_back(argv[i]);
    bool publicCommand = commandMode(raw);
    if (!publicCommand) FreeConsole();
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    INITCOMMONCONTROLSEX common{sizeof common, ICC_STANDARD_CLASSES | ICC_WIN95_CLASSES};
    InitCommonControlsEx(&common);
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    Gdiplus::GdiplusStartupInput input;
    ULONG_PTR gdip = 0;
    Gdiplus::GdiplusStartup(&gdip, &input, nullptr);
    int code = 0;
    try {
        if (!raw.empty() && raw.front() == L"serve") {
            code = runResident(raw);
        } else if (publicCommand) {
            code = runNativeCommand(raw);
        } else {
            std::map<std::wstring, std::wstring> args;
            for (size_t i = 0; i < raw.size(); ++i) {
                const auto& key = raw[i];
                if (key == L"--help" || key == L"--open-material-editor" || key == L"--open-minecraft-workbench") {
                    args[key] = L"true";
                } else if (key == L"--workspace" || key == L"--runtime" || key == L"--open" || key == L"--open-minecraft-preview") {
                    if (i + 1 == raw.size() || raw[i + 1].rfind(L"--", 0) == 0)
                        throw std::runtime_error("Missing value for " + utf8(key));
                    args[key] = raw[++i];
                } else if (key.rfind(L"--", 0) == 0) {
                    throw std::runtime_error("Unknown option: " + utf8(key));
                } else {
                    args[L"--open"] = key;
                }
            }
            {
                fs::path workspace = args.count(L"--workspace") ? fs::path(args[L"--workspace"]) : coreInstallation().defaultWorkspace;
                workspace = fs::absolute(workspace);
                fs::path runtime = args.count(L"--runtime") ? fs::path(args[L"--runtime"]) : workspace / L".runtime" / L"pixelforge-desktop";
                bool running = false;
                try {
                    running = httpCall(runtime, J::object({{"action", "status"}})).contains("document_id");
                } catch (...) {}
                if (!running) {
                    firstWindow = args;
                    for (const auto key : {L"--open", L"--open-minecraft-preview"})
                        if (firstWindow.count(key)) firstWindow[key] = fs::absolute(firstWindow[key]).wstring();
                    code = runResident({L"serve", L"--workspace", workspace.wstring(), L"--runtime", runtime.wstring(), L"--workbench"});
                } else if (fs::exists(runtime / L"commands.json") && !args.count(L"--open") &&
                           !args.count(L"--open-material-editor") && !args.count(L"--open-minecraft-workbench") && !args.count(L"--open-minecraft-preview")) {
                    auto result = httpCall(runtime, J::object({{"action", "_command"}, {"group", "workbench"}, {"command", "open"}, {"params", J::object()}}));
                    if (!result["ok"].boolean()) throw std::runtime_error(result["error"].str());
                } else {
                    bool reused = false;
                    try { reused = !httpCall(runtime / L"gui", J::object({{"action", "focus"}})).contains("error"); } catch (...) {}
                    if (!reused) showWindow(workspace, runtime, args);
                }
            }
        }
    } catch (std::exception& error) {
        output(J::object({{"error", error.what()}}).dump() + "\n");
        if (!publicCommand) MessageBoxW(nullptr, wide(error.what()).c_str(), L"PixForge C++", MB_ICONERROR);
        code = 1;
    }
    Gdiplus::GdiplusShutdown(gdip);
    CoUninitialize();
    return code;
}
