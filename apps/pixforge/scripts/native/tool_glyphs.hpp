#pragma once
#include "platform.hpp"

namespace pf {
// Toolbar order, shortcuts, tool names and cursor slots use the same indices.
enum ToolId { PEN, ERASER, FILL, PICKER, LINE, RECTANGLE, ELLIPSE, HAND, SELECT, MOVE, TOOL_COUNT };
inline const std::array<std::string,TOOL_COUNT> TOOLS={"pen","eraser","fill","picker","line","rect","ellipse","hand","select","move"};

// Draw in a 24-unit square. Callers supply the scale and the pen.
inline void drawToolGlyph(Gdiplus::Graphics& g,ToolId id,Gdiplus::Pen& pen){
    using Gdiplus::PointF;
    pen.SetStartCap(Gdiplus::LineCapRound);pen.SetEndCap(Gdiplus::LineCapRound);pen.SetLineJoin(Gdiplus::LineJoinRound);
    auto stroke=[&](std::initializer_list<PointF> points,bool closed=false){
        if(closed)g.DrawPolygon(&pen,points.begin(),int(points.size()));
        else g.DrawLines(&pen,points.begin(),int(points.size()));
    };
    switch(id){
    case PEN:
        stroke({{5,17},{4,21},{8,20},{20,8},{17,5}},true);stroke({{14,8},{17,11}});break;
    case ERASER:
        stroke({{4,15},{13,5},{16,5},{21,10},{21,13},{13,21},{9,21},{4,17}},true);
        stroke({{9,10},{16,17}});stroke({{12,21},{21,21}});break;
    case FILL:
        stroke({{11,3},{3,11},{3,14},{8,19},{11,19},{19,11}},true);
        stroke({{5,4},{15,14}});stroke({{3,12},{18,12}});stroke({{20,16},{17,21},{20,23},{23,21}},true);break;
    case PICKER:
        stroke({{14,5},{19,10}});stroke({{16,3},{21,8},{18,11},{13,6}},true);
        stroke({{14,8},{5,17},{4,21},{8,20},{17,9}});break;
    case LINE:
        stroke({{5,19},{19,5}});g.DrawEllipse(&pen,3.f,17.f,4.f,4.f);g.DrawEllipse(&pen,17.f,3.f,4.f,4.f);break;
    case RECTANGLE:g.DrawRectangle(&pen,4.f,5.f,16.f,14.f);break;
    case ELLIPSE:g.DrawEllipse(&pen,4.f,5.f,16.f,14.f);break;
    case SELECT:
        // Fixed segments keep the dashes aligned for both passes of the cursor outline.
        for(float t:{4.f,10.5f,17.f}){
            g.DrawLine(&pen,t,4.f,t+3.f,4.f);g.DrawLine(&pen,t,20.f,t+3.f,20.f);
            g.DrawLine(&pen,4.f,t,4.f,t+3.f);g.DrawLine(&pen,20.f,t,20.f,t+3.f);
        }break;
    case MOVE:
        stroke({{12,2},{12,22}});stroke({{2,12},{22,12}});stroke({{8,6},{12,2},{16,6}});
        stroke({{8,18},{12,22},{16,18}});stroke({{6,8},{2,12},{6,16}});stroke({{18,8},{22,12},{18,16}});break;
    case HAND:
        stroke({{7,13},{7,7},{9,5},{11,7},{11,12},{11,4},{13,3},{15,5},{15,12},{15,7},{17,5},{19,7},{19,14},{18,19},{14,22},{10,22},{7,19},{3,14},{4,12},{6,12},{9,15}});break;
    default:break;
    }
}
}
