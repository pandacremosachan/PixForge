"""Public command groups; parameter help is discovered on demand."""

CATALOG = {
    "project": {
        "info": "application_info", "state": "info", "plan": "plan_project",
        "create": "create_project", "open": "open_project", "save": "save_project",
        "undo": "undo", "redo": "redo", "note": "add_project_note",
        "recover": "create_recovery_copy", "shutdown": "shutdown_session",
    },
    "canvas": {"draw": "draw", "validate": "validate", "read": "read", "preview": "preview"},
    "model": {
        "uv": "model_uv", "import": "import_block_model", "shapes": "configure_shapes",
        "edit_shapes": "edit_shapes", "build_shapes": "build_shapes", "optimize_shapes": "optimize_shapes",
        "preview": "preview_shapes",
    },
    "animation": {
        "capabilities": "animation_capabilities", "prepare_frames": "prepare_animation_frames",
        "edit_frames": "edit_animation_frames", "configure": "configure_animation",
        "scene_validate": "validate_scene_animation", "scene_configure": "configure_scene_animation",
        "sample": "sample_scene", "preview": "preview_animation",
        "minecraft_inspect": "inspect_minecraft_animation", "minecraft_configure": "configure_minecraft_animation",
    },
    "minecraft": {
        "capabilities": "minecraft_capabilities", "configure": "configure_minecraft_target",
        "check": "check_minecraft_resources", "scene": "inspect_minecraft_scene", "preview": "preview_minecraft_scene",
        "performance": "inspect_minecraft_performance", "compare": "compare_minecraft_regression",
        "material_inspect": "inspect_minecraft_material", "material_configure": "configure_minecraft_material",
        "material_import": "import_minecraft_material", "material_edit": "edit_minecraft_material",
    },
    "workbench": {
        "open": "open_workbench", "wait": "wait_workbench", "present": "present_workbench", "close": "close_workbench",
        "help": "desktop_help", "state": "desktop_state", "context": "desktop_scene_context",
        "controls": "desktop_controls", "view": "desktop_view", "capture": "desktop_capture",
        "focus": "desktop_focus", "metrics": "desktop_metrics", "sample": "desktop_sample_scene", "editor": "editor_control",
    },
    "asset": {
        "inspect": "inspect_texture", "playback": "preview_texture_animation", "batch": "run_offline_batch",
        "approve": "approve_export", "export_png": "export_current", "export_shapes": "export_shapes",
        "export_minecraft": "export_minecraft_resources",
    },
}

PURPOSES = {
    "project": "工程、状态、历史和恢复",
    "canvas": "绘图、预演、像素读取和画布预览",
    "model": "模型、UV、形状和模型预览",
    "animation": "纹理时序、源帧、部件和粒子",
    "minecraft": "目标、资源、渲染、数据材质和回归",
    "workbench": "窗口生命周期、视图和原生编辑器",
    "asset": "独立素材检查、离线草稿、确认和导出",
}

CATALOG = {group: {action.replace("_", "-"): handler for action, handler in actions.items()}
           for group, actions in CATALOG.items()}
