#pragma once

namespace pf {
inline std::wstring uvNumber(double n){wchar_t out[32];std::swprintf(out,32,L"%.5g",n);return out;}
inline std::wstring uvBounds(const J& region,int ox=0,int oy=0){
    std::wstring out;for(auto& rect:region["pixel_rects"].arr()){if(!out.empty())out+=L" / ";out+=L"["+std::to_wstring(rect[0].integer()+ox)+L", "+std::to_wstring(rect[1].integer()+oy)+L"] "+std::to_wstring(rect[2].integer())+L"×"+std::to_wstring(rect[3].integer());}return out;
}
void App::clearUvPin(){uvPinned=false;uvRegion.clear();uvX=uvY=-1;uvHits.clear();uvScroll=0;if(uvInspector)uvInspector->redraw();if(canvasView)canvasView->redraw();}
void App::inspectUvPixel(int x,int y,bool pin){
    if(!uvGuides||!loaded)return;auto frameRect=currentRect();int px=x-frameRect.x,py=y-frameRect.y;if(uvPinned&&!pin)return;
    if(pin&&uvPinned){clearUvPin();return;}if(!pin&&uvX==px&&uvY==py)return;uvX=px;uvY=py;uvRegion.clear();uvHits.clear();uvScroll=0;
    if(frameRect.contains(x,y))for(int i=0;i<int(modelUv["regions"].size());++i){for(auto& r:modelUv["regions"][i]["pixel_rects"].arr())if(px>=r[0].number()&&py>=r[1].number()&&px<r[0].number()+r[2].number()&&py<r[1].number()+r[3].number()){uvHits.push_back(i);break;}}
    uvPinned=pin;canvasView->redraw();uvInspector->redraw();
}
J App::uvStatus()const{
    J regions=J::array(),faces=J::array();for(int i:uvHits){auto& group=modelUv["regions"][i];regions.arr().push_back(group["id"]);for(auto& id:group["face_ids"].arr())faces.arr().push_back(id);}
    auto r=currentRect();return J::object({{"guides",uvGuides},{"canvas_labels",false},{"pinned",uvPinned},{"pixel",uvX>=0?J::array({uvX+r.x,uvY+r.y}):J()},{"region_ids",regions},{"face_ids",faces},{"face_count",int(modelUv["faces"].size())},{"region_count",int(modelUv["regions"].size())},{"shared_region_count",modelUv["shared_region_count"]},{"direction_space","element-local"},{"pixels_modified",false}});
}
void App::paintUvGuides(HDC dc,RECT area,double ox,double oy,int repeats){
    if(!uvGuides||modelUv["regions"].empty())return;auto f=currentRect();double fw=f.w*zoom,fh=f.h*zoom;int saved=SaveDC(dc);IntersectClipRect(dc,area.left,area.top,area.right,area.bottom);
    auto outline=[&](const J& group,bool active){for(int b=0;b<repeats;++b)for(int a=0;a<repeats;++a)for(auto& bounds:group["bounds"].arr()){
        int left=rounded(ox+a*fw+bounds[0].number()*zoom),top=rounded(oy+b*fh+bounds[1].number()*zoom),right=rounded(ox+a*fw+(bounds[0].number()+bounds[2].number())*zoom),bottom=rounded(oy+b*fh+(bounds[1].number()+bounds[3].number())*zoom);
        if(right<0||bottom<0||left>area.right||top>area.bottom)continue;right=pf::max(right,left+1);bottom=pf::max(bottom,top+1);auto c=active?RGB(255,210,103):RGB(114,139,169);int width=active?D(2):1;
        line(dc,left,top,right,top,c,width);line(dc,left,top,left,bottom,c,width);line(dc,right,top,right,bottom,c,width);line(dc,left,bottom,right,bottom,c,width);
    }};
    for(auto& group:modelUv["regions"].arr())outline(group,false);for(int i:uvHits)outline(modelUv["regions"][i],true);
    RestoreDC(dc,saved);
}
void App::paintUvInspector(HDC dc,RECT area){
    fill(dc,area,RGB(37,41,50));int width=area.right;auto r=currentRect();text(dc,L"模型面域 / UV",{D(10),D(4),width-D(8),D(31)},RGB(226,230,245));
    std::wstring summary=L"模型 "+std::to_wstring(modelUv["faces"].size())+L" 面 · UV "+std::to_wstring(modelUv["regions"].size())+L" 区";text(dc,summary,{D(10),D(31),width-D(6),D(55)},RGB(172,185,207));
    if(modelUv["faces"].empty()){text(dc,L"载入带 UV 的模型后显示对应关系。\n仅凭 PNG 无法确定哪个区域属于哪个面。",{D(10),D(65),width-D(10),area.bottom},RGB(167,178,198),DT_LEFT|DT_TOP|DT_WORDBREAK);return;}
    text(dc,uvPinned?L"已固定 · 单击此行解除":L"悬停画布查看 · Ctrl+单击固定",{D(10),D(57),width-D(6),D(81)},uvPinned?RGB(255,215,125):RGB(190,198,216));
    std::wstring point=uvX>=0?L"画布像素 "+std::to_wstring(uvX+r.x)+L", "+std::to_wstring(uvY+r.y):L"点击面域条目可固定查看";text(dc,point,{D(10),D(82),width-D(5),D(105)},RGB(207,217,233));
    text(dc,L"模型决定映射 · 换模型不重排贴图",{D(10),D(105),width-D(5),D(128)},RGB(139,152,175));line(dc,D(8),D(132),width-D(8),D(132),RGB(66,75,92));
    int saved=SaveDC(dc);IntersectClipRect(dc,0,D(136),width,area.bottom);int y=D(140)-uvScroll;
    std::vector<int> groups=uvHits;if(groups.empty()&&uvX<0)for(int i=0;i<int(modelUv["regions"].size());++i)groups.push_back(i);
    if(groups.empty())text(dc,L"此像素未被当前模型采样。",{D(10),D(145),width-D(8),D(176)},RGB(180,192,211));
    for(int i:groups){auto& group=modelUv["regions"][i];bool active=!uvHits.empty();std::wstring title=wide(group["id"].str())+L" · "+std::to_wstring(group["face_count"].integer())+(group["face_count"].integer()>1?L" 个面共用":L" 个面");text(dc,title,{D(10),y,width-D(8),y+D(23)},active?RGB(255,216,128):RGB(188,208,236));y+=D(23);text(dc,uvBounds(group,r.x,r.y),{D(10),y,width-D(8),y+D(22)},RGB(146,163,187));y+=D(24);
        int shown=0;for(auto& face:modelUv["faces"].arr()){if(face["region_id"]!=group["id"])continue;if(!active&&shown++>=1)break;std::wstring label=wide(face["element_name"].str()+" · "+face["direction_label"].str());text(dc,label,{D(16),y,width-D(7),y+D(23)},RGB(216,222,234),DT_LEFT|DT_VCENTER|DT_SINGLELINE|DT_END_ELLIPSIS);y+=D(23);if(active){auto uv=face["uv"];std::wstring detail=L"UV ";for(int k=0;k<4;++k){if(k)detail+=L", ";detail+=uvNumber(uv[k].number());}detail+=L" · "+std::to_wstring(face["rotation"].integer())+L"°";text(dc,detail,{D(16),y,width-D(7),y+D(21)},RGB(139,155,181));y+=D(22);}}
        y+=D(9);
    }uvContentHeight=pf::max(0,y+uvScroll-D(136));RestoreDC(dc,saved);
}
}
