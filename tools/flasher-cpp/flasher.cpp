#include "flasher.hpp"

#include <array>
#include <filesystem>
#include <regex>
#include <string>
#include <thread>

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#include <limits.h>
#endif

#ifndef _WIN32
#include <sys/wait.h>
#endif

namespace fs = std::filesystem;

// ---- Locate esptool executable ----
static std::string find_esptool() {
    // 1. Bundled esptool next to the flasher binary
    std::error_code ec;
#ifdef _WIN32
    char exe_path[MAX_PATH];
    GetModuleFileNameA(nullptr, exe_path, sizeof(exe_path));
    fs::path exe_dir = fs::path(exe_path).parent_path();
    fs::path bundled = exe_dir / "esptool.exe";
#else
    char exe_path[PATH_MAX];
    ssize_t len = readlink("/proc/self/exe", exe_path, sizeof(exe_path) - 1);
    if (len != -1) exe_path[len] = '\0';
    fs::path exe_dir = fs::path(exe_path).parent_path();
    fs::path bundled = exe_dir / "esptool";
#endif
    if (fs::exists(bundled, ec)) return bundled.string();

    // 2. Fall back to system python + esptool
#ifdef _WIN32
    return "python -m esptool";
#else
    return "python3 -m esptool";
#endif
}

// ---- Parse progress percentage from esptool stderr ----
static int parse_progress(const std::string& line) {
    static std::regex re(R"(\((\d+)\s*%\))");
    std::smatch m;
    if (std::regex_search(line, m, re)) return std::stoi(m[1].str());
    return -1;
}

// ---- Build the esptool argument list ----
static std::string build_cmdline(const FlashConfig& cfg) {
    std::string cmd = find_esptool();
    cmd += " --chip auto";
    cmd += " --port " + cfg.port;
    cmd += " --baud " + std::to_string(cfg.baud);
    cmd += " --before default_reset --after hard_reset";
    cmd += " write_flash";
    if (cfg.erase) cmd += " --erase-all";
    cmd += " 0x00000 ";
    cmd += cfg.firmware_path;
    return cmd;
}

// ---- Linux implementation (fork/exec + pipe) ----
#ifndef _WIN32

static void read_pipe(int fd, bool is_stderr,
                       std::function<void(const std::string&)> on_output,
                       std::function<void(int)> on_progress) {
    std::array<char, 1024> buf{};
    std::string leftover;
    for (;;) {
        ssize_t n = read(fd, buf.data(), buf.size() - 1);
        if (n <= 0) break;
        buf[n] = '\0';
        leftover += buf.data();
        // Process complete lines
        for (;;) {
            auto pos = leftover.find('\n');
            if (pos == std::string::npos) break;
            std::string line = leftover.substr(0, pos);
            leftover.erase(0, pos + 1);
            if (!line.empty() && line.back() == '\r') line.pop_back();
            if (line.empty()) continue;
            on_output(line);
            if (is_stderr) {
                int pct = parse_progress(line);
                if (pct >= 0) on_progress(pct);
            }
        }
    }
    // Flush remaining (incomplete line)
    if (!leftover.empty()) {
        on_output(leftover);
    }
}

bool run_esptool(const FlashConfig& cfg,
                  std::function<void(const std::string&)> on_output,
                  std::function<void(int)> on_progress) {
    std::string cmd = build_cmdline(cfg);
    on_output("[CMD] " + cmd);

    int pipe_stdout[2], pipe_stderr[2];
    if (pipe(pipe_stdout) != 0 || pipe(pipe_stderr) != 0) {
        on_output("[ERROR] Failed to create pipes");
        return false;
    }

    pid_t pid = fork();
    if (pid < 0) {
        on_output("[ERROR] fork() failed");
        return false;
    }

    if (pid == 0) {
        // Child: redirect stdout/stderr, exec
        dup2(pipe_stdout[1], STDOUT_FILENO);
        dup2(pipe_stderr[1], STDERR_FILENO);
        close(pipe_stdout[0]); close(pipe_stdout[1]);
        close(pipe_stderr[0]); close(pipe_stderr[1]);
        execl("/bin/sh", "sh", "-c", cmd.c_str(), nullptr);
        _exit(127);
    }

    // Parent: read both pipes
    close(pipe_stdout[1]);
    close(pipe_stderr[1]);

    std::thread stdout_thread([&] {
        read_pipe(pipe_stdout[0], false, on_output, on_progress);
    });
    std::thread stderr_thread([&] {
        read_pipe(pipe_stderr[0], true, on_output, on_progress);
    });

    stdout_thread.join();
    stderr_thread.join();
    close(pipe_stdout[0]);
    close(pipe_stderr[0]);

    int status = 0;
    waitpid(pid, &status, 0);
    bool ok = WIFEXITED(status) && WEXITSTATUS(status) == 0;
    if (ok) {
        on_progress(100);
        on_output("[DONE] Flash successful!");
    } else {
        on_output("[ERROR] esptool exited with code " +
                  std::to_string(WEXITSTATUS(status)));
    }
    return ok;
}

#else // _WIN32

// ---- Windows implementation (CreateProcess + anonymous pipes) ----

static std::string win_error(DWORD code) {
    char* msg = nullptr;
    FormatMessageA(FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM,
                   nullptr, code, 0, reinterpret_cast<LPSTR>(&msg), 0, nullptr);
    std::string result(msg ? msg : "Unknown error");
    if (msg) LocalFree(msg);
    return result;
}

static void read_pipe_win(HANDLE h, bool is_stderr,
                           std::function<void(const std::string&)> on_output,
                           std::function<void(int)> on_progress) {
    std::array<char, 1024> buf{};
    std::string leftover;
    for (;;) {
        DWORD n = 0;
        if (!ReadFile(h, buf.data(), static_cast<DWORD>(buf.size() - 1), &n, nullptr))
            break;
        if (n == 0) break;
        buf[n] = '\0';
        leftover += buf.data();
        for (;;) {
            auto pos = leftover.find('\n');
            if (pos == std::string::npos) break;
            std::string line = leftover.substr(0, pos);
            leftover.erase(0, pos + 1);
            if (!line.empty() && line.back() == '\r') line.pop_back();
            if (line.empty()) continue;
            on_output(line);
            if (is_stderr) {
                int pct = parse_progress(line);
                if (pct >= 0) on_progress(pct);
            }
        }
    }
    if (!leftover.empty()) {
        on_output(leftover);
    }
}

bool run_esptool(const FlashConfig& cfg,
                  std::function<void(const std::string&)> on_output,
                  std::function<void(int)> on_progress) {
    std::string cmd = build_cmdline(cfg);
    on_output("[CMD] " + cmd);

    // Build the command line for CreateProcess
    std::string cmdline = "cmd /c " + cmd;

    SECURITY_ATTRIBUTES sa{};
    sa.nLength = sizeof(sa);
    sa.bInheritHandle = TRUE;
    sa.lpSecurityDescriptor = nullptr;

    HANDLE h_stdout_r, h_stdout_w;
    HANDLE h_stderr_r, h_stderr_w;
    if (!CreatePipe(&h_stdout_r, &h_stdout_w, &sa, 0) ||
        !CreatePipe(&h_stderr_r, &h_stderr_w, &sa, 0)) {
        on_output("[ERROR] Failed to create pipes: " + win_error(GetLastError()));
        return false;
    }
    SetHandleInformation(h_stdout_r, HANDLE_FLAG_INHERIT, 0);
    SetHandleInformation(h_stderr_r, HANDLE_FLAG_INHERIT, 0);

    PROCESS_INFORMATION pi{};
    STARTUPINFOA si{};
    si.cb = sizeof(si);
    si.hStdOutput = h_stdout_w;
    si.hStdError  = h_stderr_w;
    si.dwFlags |= STARTF_USESTDHANDLES;

    // cmdline is mutable for CreateProcessA
    std::vector<char> cmd_buf(cmdline.begin(), cmdline.end());
    cmd_buf.push_back('\0');

    if (!CreateProcessA(nullptr, cmd_buf.data(), nullptr, nullptr, TRUE,
                        CREATE_NO_WINDOW, nullptr, nullptr, &si, &pi)) {
        on_output("[ERROR] CreateProcess failed: " + win_error(GetLastError()));
        CloseHandle(h_stdout_r); CloseHandle(h_stdout_w);
        CloseHandle(h_stderr_r); CloseHandle(h_stderr_w);
        return false;
    }

    CloseHandle(h_stdout_w);
    CloseHandle(h_stderr_w);

    std::thread stdout_thread([&] {
        read_pipe_win(h_stdout_r, false, on_output, on_progress);
    });
    std::thread stderr_thread([&] {
        read_pipe_win(h_stderr_r, true, on_output, on_progress);
    });

    stdout_thread.join();
    stderr_thread.join();
    CloseHandle(h_stdout_r);
    CloseHandle(h_stderr_r);

    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD exit_code = 0;
    GetExitCodeProcess(pi.hProcess, &exit_code);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);

    bool ok = (exit_code == 0);
    if (ok) {
        on_progress(100);
        on_output("[DONE] Flash successful!");
    } else {
        on_output("[ERROR] esptool exited with code " + std::to_string(exit_code));
    }
    return ok;
}

#endif
