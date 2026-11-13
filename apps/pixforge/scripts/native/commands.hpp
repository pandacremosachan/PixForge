#pragma once
#include "platform.hpp"
#include <set>

namespace pf {
struct CommandFailure : std::runtime_error {
    std::string code;
    CommandFailure(const std::string& message, const std::string& value = "INVALID_ARGUMENT")
        : std::runtime_error(message), code(value) {}
};

inline void commandWrite(HANDLE handle, const std::string& text) {
    DWORD consoleMode = 0;
    if (handle && handle != INVALID_HANDLE_VALUE && GetConsoleMode(handle, &consoleMode)) {
        auto unicode = wide(text);
        size_t offset = 0;
        while (offset < unicode.size()) {
            DWORD written = 0;
            if (!WriteConsoleW(handle, unicode.data() + offset, DWORD(pf::min<size_t>(unicode.size() - offset, 16384)), &written, nullptr) || !written)
                throw std::runtime_error("Cannot write command response");
            offset += written;
        }
        return;
    }
    size_t offset = 0;
    while (offset < text.size()) {
        DWORD written = 0;
        if (!handle || handle == INVALID_HANDLE_VALUE ||
            !WriteFile(handle, text.data() + offset, DWORD(pf::min<size_t>(text.size() - offset, 65536)), &written, nullptr) || !written)
            throw std::runtime_error("Cannot write command response");
        offset += written;
    }
}

inline int commandExit(const J& result) {
    if (result["ok"].boolean()) return 0;
    auto code = result["code"].str();
    if (code == "INVALID_ARGUMENT" || code == "UNKNOWN_ACTION") return 2;
    if (code == "REVISION_CONFLICT" || code == "DOCUMENT_CONFLICT" || code == "FILE_CONFLICT") return 3;
    if (code == "FILE_EXISTS") return 4;
    if (code == "BUSY" || code.find("TIMEOUT") != std::string::npos) return 5;
    for (auto fragment : {"APPROV", "CONFIRM", "STALE", "FINGERPRINT"})
        if (code.find(fragment) != std::string::npos) return 6;
    if (code == "SESSION_UNAVAILABLE" || code == "NATIVE_UNAVAILABLE" || code == "DESKTOP_UNAVAILABLE" || code == "SESSION_VERSION_MISMATCH") return 7;
    return 1;
}

inline std::set<std::string> commandTypes(const J& schema) {
    std::set<std::string> result;
    if (schema["type"].isString()) result.insert(schema["type"].str());
    if (schema["anyOf"].isArray()) for (const auto& branch : schema["anyOf"].arr()) {
        auto found = commandTypes(branch);
        result.insert(found.begin(), found.end());
    }
    return result;
}

inline bool commandValid(const J& schema, const J& value) {
    if (schema["anyOf"].isArray()) {
        bool matched = false;
        for (auto& branch : schema["anyOf"].arr()) matched |= commandValid(branch, value);
        if (!matched) return false;
    }
    auto kind = schema["type"].str();
    if (kind == "string" && !value.isString()) return false;
    if (kind == "boolean" && !value.isBool()) return false;
    if (kind == "object" && !value.isObject()) return false;
    if (kind == "array" && !value.isArray()) return false;
    if (kind == "null" && !value.null()) return false;
    if ((kind == "integer" || kind == "number") && !value.isNumber()) return false;
    if (kind == "integer" && value.number() != std::floor(value.number())) return false;
    if (schema["enum"].isArray() && std::find(schema["enum"].arr().begin(), schema["enum"].arr().end(), value) == schema["enum"].arr().end()) return false;
    if (value.isArray() && schema["items"].isObject())
        for (const auto& item : value.arr()) if (!commandValid(schema["items"], item)) return false;
    return true;
}

inline std::string commandText(const std::wstring& path, bool& stdinUsed) {
    std::string text;
    if (path == L"-") {
        if (stdinUsed) throw CommandFailure("Only one input may read standard input.");
        stdinUsed = true;
        char buffer[65536];
        DWORD read = 0;
        while (ReadFile(GetStdHandle(STD_INPUT_HANDLE), buffer, sizeof buffer, &read, nullptr) && read) {
            text.append(buffer, read);
            if (text.size() > 16000000) throw CommandFailure("Input exceeds 16MB.");
        }
    } else text = readFile(fs::path(path), 16000000);
    if (text.compare(0, 3, "\xef\xbb\xbf") == 0) text.erase(0, 3);
    return text;
}

inline J commandValue(const std::string& text, const J& schema) {
    auto accepted = commandTypes(schema);
    if (accepted == std::set<std::string>{"string"}) return text;
    try { return J::parse(text); }
    catch (const std::exception&) {
        if (accepted.count("string")) return text;
        throw CommandFailure("Expected a JSON value for this parameter.");
    }
}

inline int runNativeCommand(const std::vector<std::wstring>& arguments) {
    HANDLE responseFile = INVALID_HANDLE_VALUE;
    J result;
    try {
        auto root = executablePath().parent_path();
        std::vector<std::wstring> rest;
        fs::path workspace = fs::current_path(), runtime, resultPath;
        bool machine = false, version = false;
        for (size_t i = 0; i < arguments.size(); ++i) {
            const auto& option = arguments[i];
            if (option == L"--json") machine = true;
            else if (option == L"--version") version = true;
            else if (option == L"--workspace" || option == L"--runtime" || option == L"--result-file") {
                if (++i == arguments.size()) throw CommandFailure("Missing value for " + utf8(option));
                if (option == L"--workspace") workspace = arguments[i];
                else if (option == L"--runtime") runtime = arguments[i];
                else resultPath = arguments[i];
            } else rest.push_back(option);
        }
        auto help = [&](const J& data) { commandWrite(GetStdHandle(STD_OUTPUT_HANDLE), machine ? data["json"].dump() + "\n" : data["human"].str()); };
        if (version) {
            if (!rest.empty()) throw CommandFailure("--version does not accept a command.");
            auto application = readJson(root / L"application.json");
            auto value = J::object({{"application", application["application"]}, {"version", application["version"]}, {"public_api_version", application["public_api_version"]}});
            commandWrite(GetStdHandle(STD_OUTPUT_HANDLE), machine ? value.dump() + "\n" : "PixForge " + application["version"].str() + " / command API 4\n");
            return 0;
        }
        auto docs = readJson(root / L"command-help.json");
        if (docs["schema"].str() != "pixforge.command-help/v4") throw CommandFailure("Command help is missing or incompatible; use the complete application package.");
        if (!rest.empty() && rest[0] == L"help") { rest.erase(rest.begin()); rest.push_back(L"--help"); }
        if (rest.empty() || rest == std::vector<std::wstring>{L"--help"} || rest == std::vector<std::wstring>{L"-h"}) { help(docs["overview"]); return 0; }
        auto group = utf8(rest[0]);
        if (!docs["groups"].contains(group)) throw CommandFailure("Unknown command group: " + group + ". Use --help.");
        const J& domain = docs["groups"][group];
        if (rest.size() == 1 || rest[1] == L"--help" || rest[1] == L"-h") { help(domain["help"]); return 0; }
        auto action = utf8(rest[1]);
        if (!domain["actions"].contains(action)) throw CommandFailure("Unknown " + group + " action: " + action);
        const J& actionHelp = domain["actions"][action];
        const J& schema = actionHelp["json"]["params_schema"];
        if (std::find(rest.begin() + 2, rest.end(), L"--help") != rest.end() || std::find(rest.begin() + 2, rest.end(), L"-h") != rest.end()) { help(actionHelp); return 0; }
        std::map<std::string, std::pair<std::string, bool>> flags;
        for (auto& [key, spec] : schema["properties"].obj()) {
            auto option = key;
            std::replace(option.begin(), option.end(), '_', '-');
            flags["--" + option] = {key, false};
            flags["--" + option + "-file"] = {key, true};
        }
        struct Input {std::string key; bool file; std::wstring value;};
        std::vector<Input> inputs;
        std::wstring requestFile, requestJson;
        bool fileRequest = false, jsonRequest = false, stdinUsed = false;
        for (size_t i = 2; i < rest.size(); ++i) {
            auto option = utf8(rest[i]);
            if (option == "--request-file" || option == "--request-json") {
                if (fileRequest || jsonRequest || ++i == rest.size()) throw CommandFailure("Supply one request-file or request-json value.");
                if (option == "--request-file") { fileRequest = true; requestFile = rest[i]; }
                else { jsonRequest = true; requestJson = rest[i]; }
                continue;
            }
            auto found = flags.find(option);
            if (found == flags.end()) throw CommandFailure("Unknown parameter: " + option);
            auto [key, file] = found->second;
            std::wstring value;
            if (!file && commandTypes(schema["properties"][key]) == std::set<std::string>{"boolean"} &&
                (i + 1 == rest.size() || rest[i + 1].rfind(L"--", 0) == 0)) value = L"true";
            else {
                if (++i == rest.size()) throw CommandFailure("Missing value for " + option);
                value = rest[i];
            }
            inputs.push_back({key, file, value});
        }
        size_t stdinCount = fileRequest && requestFile == L"-" ? 1 : 0;
        for (auto& input : inputs) stdinCount += input.file && input.value == L"-";
        if (stdinCount > 1) throw CommandFailure("Only one input may read standard input.");
        J params = fileRequest ? J::parse(commandText(requestFile, stdinUsed)) : jsonRequest ? J::parse(utf8(requestJson)) : J::object();
        if (!params.isObject()) throw CommandFailure("The request must be a JSON parameter object.");
        for (auto& input : inputs) {
            if (params.contains(input.key)) throw CommandFailure("Parameter supplied twice: " + input.key);
            params[input.key] = commandValue(input.file ? commandText(input.value, stdinUsed) : utf8(input.value), schema["properties"][input.key]);
        }
        for (auto& [key, value] : params.obj()) {
            if (!schema["properties"].contains(key)) throw CommandFailure("Unknown parameter: " + key);
            if (!commandValid(schema["properties"][key], value)) throw CommandFailure("Invalid parameter type or value: " + key);
        }
        if (schema["required"].isArray()) for (auto& key : schema["required"].arr())
            if (!params.contains(key.str())) throw CommandFailure("Missing required parameter: " + key.str());
        if (!resultPath.empty()) {
            resultPath = fs::absolute(resultPath);
            fs::create_directories(resultPath.parent_path());
            responseFile = CreateFileW(resultPath.c_str(), GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
            if (responseFile == INVALID_HANDLE_VALUE) {
                auto error = GetLastError();
                throw CommandFailure("Cannot create response file: " + pathText(resultPath), error == ERROR_FILE_EXISTS || error == ERROR_ALREADY_EXISTS ? "FILE_EXISTS" : "INVALID_ARGUMENT");
            }
        }
        workspace = fs::absolute(workspace);
        if (runtime.empty()) {
            std::vector<wchar_t> environment(32768);
            auto n = GetEnvironmentVariableW(L"PIXFORGE_RUNTIME", environment.data(), DWORD(environment.size()));
            runtime = n && n < environment.size() ? fs::path(environment.data()) : workspace / L".runtime" / L"pixelforge-desktop";
        }
        runtime = fs::absolute(runtime);
        if (group == "project" && action == "info") {
            result = readJson(root / L"application.json");
            result["workspace"] = pathText(workspace); result["runtime"] = pathText(runtime); result["ok"] = true;
        } else {
            try { ensurePortableCore(workspace, runtime); }
            catch (const std::exception& error) { throw CommandFailure(error.what(), "SESSION_UNAVAILABLE"); }
            if (readJson(runtime / L"session.json")["command_contract"].integer() != 4)
                throw CommandFailure("The existing project process is from an older application; save its work and restart it with this version.", "SESSION_VERSION_MISMATCH");
            result = httpCall(runtime, J::object({{"action", "_command"}, {"group", group}, {"command", action}, {"params", params}}));
        }
    } catch (const CommandFailure& error) {
        result = J::object({{"ok", false}, {"error", error.what()}, {"code", error.code}});
    } catch (const std::exception& error) {
        result = J::object({{"ok", false}, {"error", error.what()}, {"code", "INVALID_ARGUMENT"}});
    }
    auto encoded = result.dump() + "\n";
    if (responseFile != INVALID_HANDLE_VALUE) { commandWrite(responseFile, encoded); CloseHandle(responseFile); }
    commandWrite(GetStdHandle(STD_OUTPUT_HANDLE), encoded);
    return commandExit(result);
}
}
