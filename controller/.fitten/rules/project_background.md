# 项目背景信息

这是一个多模块的Python项目，主要功能包括：

- **Web服务**：使用Flask框架提供Web服务
- **数据库处理**：包含数据库操作模块
- **游戏逻辑**：包含游戏处理模块
- **MQTT通信**：实现MQTT协议通信功能
- **日志系统**：有专门的日志记录模块

项目结构：
- 主程序入口：main.py
- 核心模块：
  - flask_app.py (Flask应用)
  - database_process.py (数据库处理)
  - game_process.py (游戏逻辑)
  - mqtt_process.py (MQTT通信)
  - logging_utils.py (日志工具)
  
资源目录：
- /resource/ 包含静态文件、模板和数据库文件
- /log/ 存放各模块的日志文件

这是一个控制器类项目，整合了多种功能模块，适合使用AI进行协同开发。
