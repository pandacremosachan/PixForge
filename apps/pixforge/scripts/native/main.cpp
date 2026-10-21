#include "app.hpp"
#include "minecraft_preview.hpp"
#include "minecraft_workbench.hpp"
#include "material_editor.hpp"

namespace pf {
static void output(const std::string& text) {
    DWORD written = 0;
    auto handle = GetStdHandle(STD_OUTPUT_HANDLE);
    if (handle && handle != INVALID_HANDLE_VALUE)
        WriteFile(handle, text.data(), DWORD(text.size()), &written, nullptr);
}
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    using namespace pf;
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    INITCOMMONCONTROLSEX common{sizeof common, ICC_STANDARD_CLASSES | ICC_WIN95_CLASSES};
    InitCommonControlsEx(&common);
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    Gdiplus::GdiplusStartupInput input;
    ULONG_PTR gdip = 0;
    Gdiplus::GdiplusStartup(&gdip, &input, nullptr);
    int argc = 0;
    LPWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    std::vector<std::wstring> raw;
    for (int i = 1; i < argc; ++i) raw.emplace_back(argv[i]);
    LocalFree(argv);
    bool publicCommand = !raw.empty() &&
        (raw[0] == L"--cli" || raw[0] == L"--mcp" || raw[0] == L"--describe");
    int code = 0;
    try {
        if (publicCommand) {
            if (raw[0] == L"--describe") {
                output(J::object({
                    {"schema", "pixforge.application/v1"}, {"application", "PixForge"},
                    {"version", "2.9.0"}, {"public_api_version", 1},
                    {"capabilities", J::array({"minecraft-assets/v1", "forge-runtime/v1",
                        "minecraft-preview/v1", "minecraft-animation/v1", "minecraft-regression/v1",
                        "minecraft-material/v1"})},
                    {"interfaces", J::array({"cli", "mcp-stdio", "authenticated-loopback-json"})},
                    {"commands", J::object({{"cli", "--cli"}, {"mcp", "--mcp"}, {"describe", "--describe"}})}
                }).dump() + "\n");
            } else {
                bool mcp = raw[0] == L"--mcp";
                raw.erase(raw.begin());
                if (mcp) raw.insert(raw.begin(), L"mcp");
                code = runPublicCommand(raw);
            }
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
            if (args.count(L"--help")) {
                output("PixForgeNative.exe --workspace DIR --runtime CORE_SESSION [--open PROJECT]\n"
                    "Standalone C++ desktop; no skill installation required.\n"
                    "Public API: --describe; --cli <arguments>; --mcp [--workspace DIR --runtime DIR].\n"
                    "Model UI commands: pixelforge ui --runtime CORE_SESSION help\n");
            } else {
                fs::path workspace = args.count(L"--workspace") ? fs::path(args[L"--workspace"]) : coreInstallation().defaultWorkspace;
                workspace = fs::absolute(workspace);
                fs::path runtime = args.count(L"--runtime") ? fs::path(args[L"--runtime"]) : workspace / L".runtime" / L"pixelforge-desktop";
                ensurePortableCore(workspace, runtime);
                bool reused = false;
                try {
                    reused = !httpCall(runtime / L"gui", J::object({{"action", "focus"}})).contains("error");
                } catch (...) {}
                if (!reused) {
                    App app(workspace, runtime, args.count(L"--open") ? pathText(fs::absolute(args[L"--open"])) : "");
                    if (args.count(L"--open-material-editor"))
                        app.userActions.push_back([&app] { openMaterialEditor(app); });
                    if (args.count(L"--open-minecraft-workbench"))
                        app.userActions.push_back([&app] { openMinecraftWorkbench(app); });
                    if (args.count(L"--open-minecraft-preview")) {
                        auto initial = readJson(args[L"--open-minecraft-preview"]);
                        app.userActions.push_back([&app, initial] { openMinecraftPreview(app, initial); });
                    }
                    MSG message;
                    while (GetMessageW(&message, nullptr, 0, 0) > 0) {
                        try {
                            if (app.key(message) || IsDialogMessageW(app.hwnd, &message)) continue;
                        } catch (std::exception& error) {
                            app.message = wide(error.what());
                            app.statusBar->redraw();
                        }
                        TranslateMessage(&message);
                        DispatchMessageW(&message);
                    }
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
