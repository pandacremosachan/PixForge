#pragma once
#include "platform.hpp"

namespace pf::choice {
enum class Kind { item, heading, line };
struct Row {
    Kind kind;
    int id;
    std::wstring label, shortcut;
    bool checked, enabled;
};

class Menu {
    std::vector<Row> rows;
public:
    void item(int id,std::wstring label,bool checked=false,bool enabled=true);
    void heading(std::wstring label);
    void separator();
    // Positive command ID on acceptance, zero on cancellation.
    int open(HWND trigger,bool preferAbove=false,int maxHeight=500) const;
};

enum class Trigger { field, command, footer };
void trackHover(HWND h,UINT message);
bool hovered(HWND h);
void paintTrigger(HDC dc,RECT r,HWND h,const std::wstring& value,Trigger style,bool pressed=false);
void styleSelect(HWND combo);
}
