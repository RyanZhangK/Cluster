#include "flasher.hpp"
#include "serial_ports.hpp"
#include "theme.hpp"

#include "imgui.h"
#include "imgui_impl_glfw.h"
#include "imgui_impl_opengl3.h"
#include <GLFW/glfw3.h>

#include <atomic>
#include <cstdio>
#include <deque>
#include <fstream>
#include <mutex>
#include <thread>

// ---- Tiny native file dialog (no library needed) ----
#ifdef _WIN32
#include <windows.h>
static std::string
open_file_dialog()
{
  OPENFILENAMEA ofn{};
  char buf[MAX_PATH] = {};
  ofn.lStructSize = sizeof(ofn);
  ofn.lpstrFilter = "Firmware Files (*.bin)\0*.bin\0All Files (*.*)\0*.*\0";
  ofn.lpstrFile = buf;
  ofn.nMaxFile = sizeof(buf);
  ofn.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST;
  if (GetOpenFileNameA(&ofn))
    return buf;
  return {};
}
#else
// Use zenity / kdialog as a fallback; tinyfd is also an option.
// Here we just use a basic pipe to zenity (available on most Linux desktops).
static std::string
open_file_dialog()
{
  const char* cmd = "zenity --file-selection --file-filter='*.bin' 2>/dev/null";
  FILE* f = popen(cmd, "r");
  if (!f)
    return {};
  char buf[4096] = {};
  std::string result;
  if (fgets(buf, sizeof(buf), f)) {
    result = buf;
    while (!result.empty() && (result.back() == '\n' || result.back() == '\r'))
      result.pop_back();
  }
  pclose(f);
  return result;
}
#endif

// ---- Application state ----
struct AppState
{
  std::vector<PortInfo> ports;
  int selected_port = -1;
  char firmware_path[1024] = {};
  int baud_index = 0;
  std::atomic<FlashState> flash_state{ FlashState::Idle };
  std::atomic<float> progress{ 0.0f };
  std::deque<std::string> log_lines;
  std::mutex log_mutex;
  bool erase_chip = false;
  bool scroll_to_bottom = true;
  bool flash_result = false;
  std::thread flash_thread;

  const std::vector<int> baud_rates = { 460800, 115200, 921600, 230400, 74880 };

  void add_log(const std::string& line)
  {
    std::lock_guard<std::mutex> lock(log_mutex);
    log_lines.push_back(line);
    if (log_lines.size() > 500)
      log_lines.pop_front();
  }

  bool can_flash() const
  {
    return flash_state.load() == FlashState::Idle && selected_port >= 0 &&
           firmware_path[0] != '\0';
  }
};

// ---- Main ----
int
main()
{
  // --- GLFW window ---
  if (!glfwInit())
    return 1;
  glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
  glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 2);
  glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
  GLFWwindow* window =
    glfwCreateWindow(600, 520, "Cluster Firmware Flasher", nullptr, nullptr);
  if (!window) {
    glfwTerminate();
    return 1;
  }
  glfwMakeContextCurrent(window);
  glfwSwapInterval(1);

  // --- ImGui ---
  IMGUI_CHECKVERSION();
  ImGui::CreateContext();

  // Load Chinese font (fall back to default if not found)
  ImGuiIO& io = ImGui::GetIO();
  const char* font_paths[] = {
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/wenquanyi/wqy-microhei/wqy-microhei.ttc",
    "C:\\Windows\\Fonts\\msyh.ttc",
  };

  // GetGlyphRangesChineseSimplifiedCommon() covers ~2500 common chars but
  // misses some, e.g. U+6D4F (浏). Build custom ranges to fill the gap.
  static ImVector<ImWchar> s_glyph_ranges;
  if (s_glyph_ranges.empty()) {
    ImFontGlyphRangesBuilder builder;
    builder.AddRanges(io.Fonts->GetGlyphRangesChineseSimplifiedCommon());
    builder.AddChar(0x6D4F); // 浏 (U+6D4F)
    builder.BuildRanges(&s_glyph_ranges);
  }

  bool font_loaded = false;
  for (const char* path : font_paths) {
    std::ifstream test(path);
    if (test.good()) {
      io.Fonts->AddFontFromFileTTF(path, 18.0f, nullptr, s_glyph_ranges.Data);
      font_loaded = true;
      break;
    }
  }
  if (!font_loaded) {
    io.Fonts->AddFontDefault();
  }

  ImGui_ImplGlfw_InitForOpenGL(window, true);
  ImGui_ImplOpenGL3_Init("#version 130");
  apply_dark_theme();

  AppState st;
  st.ports = list_serial_ports();
  st.selected_port = st.ports.empty() ? -1 : 0;

  // --- Main loop ---
  while (!glfwWindowShouldClose(window)) {
    glfwPollEvents();
    ImGui_ImplOpenGL3_NewFrame();
    ImGui_ImplGlfw_NewFrame();
    ImGui::NewFrame();

    // Full-window UI
    ImGui::SetNextWindowPos(ImVec2(0, 0));
    ImGui::SetNextWindowSize(ImGui::GetIO().DisplaySize);
    ImGui::Begin("Main",
                 nullptr,
                 ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoResize |
                   ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoCollapse);

    ImGui::TextUnformatted("Cluster Firmware Flasher");
    ImGui::Separator();
    ImGui::Spacing();

    // --- Serial Port ---
    ImGui::TextUnformatted("串口");
    if (ImGui::Button("刷新")) {
      st.ports = list_serial_ports();
      if (!st.ports.empty() && st.selected_port < 0)
        st.selected_port = 0;
    }
    ImGui::SameLine();
    if (st.ports.empty()) {
      ImGui::TextDisabled("(未检测到串口)");
    } else {
      std::string preview = st.selected_port >= 0
                              ? st.ports[st.selected_port].display_name()
                              : "选择串口...";
      if (ImGui::BeginCombo("##port", preview.c_str())) {
        for (int i = 0; i < static_cast<int>(st.ports.size()); ++i) {
          bool sel = (st.selected_port == i);
          if (ImGui::Selectable(st.ports[i].display_name().c_str(), sel))
            st.selected_port = i;
          if (sel)
            ImGui::SetItemDefaultFocus();
        }
        ImGui::EndCombo();
      }
    }
    ImGui::Spacing();

    // --- Firmware path ---
    ImGui::TextUnformatted("固件文件");
    ImGui::InputText("##fw",
                     st.firmware_path,
                     sizeof(st.firmware_path),
                     ImGuiInputTextFlags_ReadOnly);
    ImGui::SameLine();
    if (ImGui::Button("浏览")) {
      std::string path = open_file_dialog();
      if (!path.empty()) {
        std::snprintf(
          st.firmware_path, sizeof(st.firmware_path), "%s", path.c_str());
      }
    }
    ImGui::Spacing();

    // --- Baud rate ---
    ImGui::TextUnformatted("波特率");
    ImGui::SameLine();
    ImGui::SetNextItemWidth(120);
    std::string baud_preview = std::to_string(st.baud_rates[st.baud_index]);
    if (ImGui::BeginCombo("##baud", baud_preview.c_str())) {
      for (int i = 0; i < static_cast<int>(st.baud_rates.size()); ++i) {
        bool sel = (st.baud_index == i);
        std::string label = std::to_string(st.baud_rates[i]);
        if (ImGui::Selectable(label.c_str(), sel))
          st.baud_index = i;
        if (sel)
          ImGui::SetItemDefaultFocus();
      }
      ImGui::EndCombo();
    }
    ImGui::Spacing();

    // --- Erase checkbox ---
    ImGui::Checkbox("烧录前全片擦除 (--erase-all)", &st.erase_chip);
    ImGui::Spacing();

    // --- Flash button ---
    bool was_disabled = !st.can_flash();
    if (was_disabled)
      ImGui::BeginDisabled();
    if (ImGui::Button("开始烧录", ImVec2(-1, 40))) {
      // Join previous thread if still running
      if (st.flash_thread.joinable())
        st.flash_thread.join();

      FlashConfig cfg;
      cfg.port = st.ports[st.selected_port].device;
      cfg.firmware_path = st.firmware_path;
      cfg.baud = st.baud_rates[st.baud_index];
      cfg.erase = st.erase_chip;
      st.flash_state.store(FlashState::Flashing);
      st.progress.store(0.0f);
      st.add_log("[INFO] Starting flash...");

      st.flash_thread = std::thread(
        [cfg](AppState* s) {
          s->flash_result = run_esptool(
            cfg,
            [s](const std::string& line) { s->add_log(line); },
            [s](int pct) {
              s->progress.store(static_cast<float>(pct) / 100.0f);
            });
          s->flash_state.store(s->flash_result ? FlashState::Success
                                               : FlashState::Failed);
        },
        &st);
    }
    if (was_disabled)
      ImGui::EndDisabled();
    ImGui::Spacing();

    // --- Progress bar ---
    FlashState current_state = st.flash_state.load();
    if (current_state == FlashState::Success)
      ImGui::PushStyleColor(ImGuiCol_PlotHistogram,
                            ImVec4(0.133f, 0.773f, 0.369f, 1.0f));
    else if (current_state == FlashState::Failed)
      ImGui::PushStyleColor(ImGuiCol_PlotHistogram,
                            ImVec4(0.937f, 0.267f, 0.267f, 1.0f));
    ImGui::ProgressBar(st.progress.load(), ImVec2(-1, 8), "");
    if (current_state != FlashState::Idle &&
        current_state != FlashState::Flashing)
      ImGui::PopStyleColor();
    ImGui::Spacing();

    // --- Status text ---
    const char* status = "就绪";
    if (current_state == FlashState::Flashing)
      status = "正在烧录...";
    else if (current_state == FlashState::Success)
      status = "烧录成功!";
    else if (current_state == FlashState::Failed)
      status = "烧录失败，请查看日志";
    ImGui::TextUnformatted(status);
    ImGui::Spacing();

    // --- Log area ---
    ImGui::TextUnformatted("烧录日志");
    ImGui::BeginChild("##log", ImVec2(-1, -1), true);
    {
      std::lock_guard<std::mutex> lock(st.log_mutex);
      for (const auto& line : st.log_lines) {
        ImGui::TextUnformatted(line.c_str());
      }
      if (st.scroll_to_bottom && !st.log_lines.empty())
        ImGui::SetScrollHereY(1.0f);
    }
    ImGui::EndChild();

    ImGui::End();

    // --- Render ---
    ImGui::Render();
    int w, h;
    glfwGetFramebufferSize(window, &w, &h);
    glViewport(0, 0, w, h);
    glClearColor(0.059f, 0.067f, 0.090f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
    glfwSwapBuffers(window);
  }

  // --- Cleanup ---
  if (st.flash_thread.joinable())
    st.flash_thread.join();
  ImGui_ImplOpenGL3_Shutdown();
  ImGui_ImplGlfw_Shutdown();
  ImGui::DestroyContext();
  glfwDestroyWindow(window);
  glfwTerminate();
  return 0;
}
