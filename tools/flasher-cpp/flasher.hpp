#pragma once
#include <functional>
#include <string>

struct FlashConfig {
    std::string port;
    std::string firmware_path;
    int baud = 460800;
    bool erase = false;
};

enum class FlashState { Idle, Flashing, Success, Failed };

/// Launch esptool as a subprocess. Calls on_output for every line of
/// stdout/stderr, and on_progress for percentage updates (0-100).
/// Returns true on success (exit code 0).
bool run_esptool(
    const FlashConfig& cfg,
    std::function<void(const std::string&)> on_output,
    std::function<void(int)> on_progress
);
