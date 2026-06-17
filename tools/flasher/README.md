# Cluster Firmware Flasher

Cluster 项目的 ESP8266 固件烧录工具，用于将编译好的 .bin 固件烧录到 NodeMCU v2 设备。

## 使用方式

### 开发运行

```bash
make flasher-dev
```

### 编译为独立可执行文件

```bash
make flasher
```

编译产物位于 `build/dist/flasher.dist/cluster-flasher`。

## 操作步骤

1. 用 USB 数据线连接 ESP8266 设备
2. 点击「刷新」检测串口，在下拉框中选择对应端口
3. 点击「浏览」选择要烧录的 `.bin` 固件文件
4. 选择波特率（默认 460800）
5. 根据需要勾选「全片擦除」
6. 点击「开始烧录」，观察进度和日志
7. 等待提示「烧录成功」

## 注意事项

- **Linux**：需要将用户加入 `dialout` 组以获得串口权限：
  ```bash
  sudo usermod -aG dialout $USER
  # 重新登录后生效
  ```
- **ESP8266 未进入烧录模式**：部分开发板需要按住 FLASH 按钮后按 RST 键进入烧录模式
- 固件文件为通过 PlatformIO 编译产生的 `.bin` 文件，通常位于 `mcu/src/{节点}/.pio/build/nodemcuv2/firmware.bin`

## 依赖

- Python >= 3.12
- esptool >= 4.8
- pyserial >= 3.5
- PySide6 (Nuitka 编译时自动处理)
