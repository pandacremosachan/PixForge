#pragma once
#include "app.hpp"
namespace pf {
void openMinecraftPreview(App& app,const J& initial=J());
J minecraftPreviewCommand(App& app,const J& request);
}
