# 代码风格指南

## 基本规范

- 使用 **Python 3.8+** 语法特性
- 严格遵循 **PEP 8** 规范
- 使用 **4个空格** 缩进 (不使用Tab)
- 每行代码不超过 **120** 个字符

## 命名约定

- 类名：`CamelCase` (首字母大写驼峰式)
- 函数/方法名：`lower_case_with_underscores` (小写加下划线)
- 变量名：`lower_case_with_underscores`
- 常量名：`ALL_CAPS_WITH_UNDERSCORES`
- 私有成员：`_single_leading_underscore`
- 避免使用单个字符变量名(除简单循环变量)

## 代码组织

### 导入顺序

1. 标准库导入 (按字母顺序)
2. 第三方库导入 (按字母顺序)
3. 本地应用/库导入 (按字母顺序)
4. 每组导入用空行分隔

示例：
```python
import os
import sys
from pathlib import Path

import psutil
from flask import Flask

from . import database_process
from .logging_utils import get_logger
```

### 类定义

- 类之间用 **两个空行** 分隔
- 方法之间用 **一个空行** 分隔
- 公共方法在前，私有方法在后
- 使用类型注解

示例：
```python
class ProcessManager:
    """模块进程管理类"""
    
    def __init__(self, config: dict) -> None:
        self._config = config
        self.processes: dict = {}
        
    def start_module(self, module: str) -> bool:
        """启动指定模块"""
        ...
        
    def _setup_logging(self, module: str) -> logging.Logger:
        """设置模块日志(内部方法)"""
        ...
```

## 文档规范

- 模块级文档字符串：描述模块功能和主要接口
- 类文档字符串：描述类职责和主要方法
- 函数文档字符串：
  - 一句话功能描述
  - Args: 参数说明
  - Returns: 返回值说明
  - Raises: 可能抛出的异常

## 异常处理

- 避免捕获过于宽泛的异常
- 记录完整的异常堆栈
- 资源操作使用上下文管理器(with语句)
- 自定义异常类继承自项目基础异常类

示例：
```python
try:
    with open(config_file) as f:
        config = json.load(f)
except FileNotFoundError as e:
    logger.error(f"配置文件不存在: {config_file}")
    raise
except json.JSONDecodeError as e:
    logger.error(f"配置文件格式错误: {str(e)}")
    raise
```

## 日志规范

- 使用模块级logger (`logging.getLogger(__name__)`)
- 日志消息首字母小写，不加结束标点
- 关键操作必须记录日志
- 错误日志包含足够上下文信息

示例：
```python
logger.debug("connecting to database %s", db_url)
logger.info("module %s initialized", module_name)
logger.warning("high memory usage detected: %dMB", usage)
logger.error("failed to start module %s: %s", module, str(e))
```
