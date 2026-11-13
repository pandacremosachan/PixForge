#pragma once

namespace pf {
class App;
class StartPage {
public:
    enum class Task { block, item, model };
    bool visible=false;
    ~StartPage();
    void create(App&);
    void show(bool fromWorkbench);
    void hide();
    void layout();
    bool key(MSG&);
    bool drawButton(const DRAWITEMSTRUCT&) const;
    const char* taskName() const;

private:
    App* app=nullptr;
    Surface* page=nullptr;
    Task task=Task::block;
    bool fromEditor=false;
    HWND cards[3]{},mapping=nullptr,resolution=nullptr;
    HWND open=nullptr,resume=nullptr,begin=nullptr;
    RECT content{},rail{},settings{};
    int fieldsTop=0,rowHeight=0;
    HFONT heading=nullptr,title=nullptr;
    int fontDpi=0;
    bool canResume() const;
    void select(Task);
    void launch();
    void paint(HDC,RECT);
};
}
