#pragma once
#include "app.hpp"
namespace pf {
void openMinecraftEditor(App& app);
void exportMinecraft(App& app,bool modAssets=false);
void exportForgeRuntime(App& app,bool standalone=false);
J minecraftEditorCommand(App& app,const J& request);
}
