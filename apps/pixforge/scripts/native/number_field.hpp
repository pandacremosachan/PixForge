#pragma once
#include "platform.hpp"

namespace pf::numberField {
HWND create(HWND parent,int id,HFONT font,const wchar_t* unit,double minimum,double maximum,
            double value,bool integral,std::function<void(double)> changed);
void set(HWND control,double value);
void range(HWND control,double minimum,double maximum);
}
