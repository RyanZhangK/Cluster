#pragma once
#include "imgui.h"

inline void apply_dark_theme() {
    ImGui::StyleColorsDark();
    ImVec4* colors = ImGui::GetStyle().Colors;
    // Backgrounds: #0f1117, surfaces: #161b27, cards: #1e2435
    colors[ImGuiCol_WindowBg]       = ImVec4(0.059f, 0.067f, 0.090f, 1.00f); // #0f1117
    colors[ImGuiCol_ChildBg]        = ImVec4(0.086f, 0.106f, 0.153f, 1.00f); // #161b27
    colors[ImGuiCol_FrameBg]        = ImVec4(0.118f, 0.141f, 0.208f, 0.60f); // #1e2435
    colors[ImGuiCol_FrameBgHovered] = ImVec4(0.165f, 0.188f, 0.271f, 1.00f); // #2a3045
    colors[ImGuiCol_FrameBgActive]  = ImVec4(0.165f, 0.188f, 0.271f, 1.00f);
    // Primary: #4f6ef7 (blue)
    colors[ImGuiCol_Button]         = ImVec4(0.310f, 0.431f, 0.969f, 1.00f); // #4f6ef7
    colors[ImGuiCol_ButtonHovered]  = ImVec4(0.420f, 0.518f, 0.973f, 1.00f); // #6b84f8
    colors[ImGuiCol_ButtonActive]   = ImVec4(0.235f, 0.345f, 0.969f, 1.00f);
    // Success / Danger
    colors[ImGuiCol_PlotHistogram]  = ImVec4(0.133f, 0.773f, 0.369f, 1.00f); // #22c55e
    // Text
    colors[ImGuiCol_Text]           = ImVec4(0.886f, 0.910f, 0.941f, 1.00f); // #e2e8f0
    colors[ImGuiCol_TextDisabled]   = ImVec4(0.545f, 0.584f, 0.690f, 1.00f); // #8b95b0
    // Headers, tabs, etc.
    colors[ImGuiCol_Header]         = ImVec4(0.310f, 0.431f, 0.969f, 0.40f);
    colors[ImGuiCol_HeaderHovered]  = ImVec4(0.310f, 0.431f, 0.969f, 0.60f);
    colors[ImGuiCol_HeaderActive]   = ImVec4(0.310f, 0.431f, 0.969f, 0.80f);
    colors[ImGuiCol_Tab]            = ImVec4(0.086f, 0.106f, 0.153f, 1.00f);
    colors[ImGuiCol_TabActive]      = ImVec4(0.310f, 0.431f, 0.969f, 1.00f);
    colors[ImGuiCol_TabHovered]     = ImVec4(0.165f, 0.188f, 0.271f, 1.00f);
    colors[ImGuiCol_TitleBg]        = ImVec4(0.047f, 0.059f, 0.102f, 1.00f); // #0c0f1a
    colors[ImGuiCol_TitleBgActive]  = ImVec4(0.047f, 0.059f, 0.102f, 1.00f);
    // Borders, scrollbar
    colors[ImGuiCol_Border]         = ImVec4(0.165f, 0.188f, 0.271f, 0.50f); // #2a3045
    colors[ImGuiCol_ScrollbarBg]    = ImVec4(0.086f, 0.106f, 0.153f, 1.00f);
    colors[ImGuiCol_ScrollbarGrab]  = ImVec4(0.165f, 0.188f, 0.271f, 1.00f);
    colors[ImGuiCol_ScrollbarGrabHovered]  = ImVec4(0.310f, 0.431f, 0.969f, 0.50f);
    colors[ImGuiCol_ScrollbarGrabActive]  = ImVec4(0.310f, 0.431f, 0.969f, 0.80f);
    // Misc
    colors[ImGuiCol_PopupBg]        = ImVec4(0.086f, 0.106f, 0.153f, 1.00f);
    colors[ImGuiCol_CheckMark]      = ImVec4(0.310f, 0.431f, 0.969f, 1.00f);
    colors[ImGuiCol_SliderGrab]     = ImVec4(0.310f, 0.431f, 0.969f, 1.00f);
    colors[ImGuiCol_SliderGrabActive] = ImVec4(0.420f, 0.518f, 0.973f, 1.00f);
    colors[ImGuiCol_ResizeGrip]     = ImVec4(0.310f, 0.431f, 0.969f, 0.30f);
    colors[ImGuiCol_ResizeGripHovered] = ImVec4(0.310f, 0.431f, 0.969f, 0.60f);
    colors[ImGuiCol_ResizeGripActive]  = ImVec4(0.310f, 0.431f, 0.969f, 0.90f);

    auto& style = ImGui::GetStyle();
    style.WindowRounding    = 8.0f;
    style.FrameRounding     = 6.0f;
    style.GrabRounding      = 4.0f;
    style.ChildRounding     = 8.0f;
    style.PopupRounding     = 6.0f;
    style.ScrollbarRounding = 6.0f;
    style.TabRounding       = 6.0f;
    style.WindowPadding     = ImVec2(12, 12);
    style.FramePadding      = ImVec2(10, 6);
    style.ItemSpacing       = ImVec2(10, 8);
    style.ScrollbarSize     = 10.0f;
}
