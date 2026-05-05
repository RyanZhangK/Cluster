/**
 * Node MCU 4×4矩阵键盘驱动
 * 使用所有支持内部上拉的GPIO引脚，避免外部电阻
 * 作者：基于用户需求定制
 */

#include <Arduino.h>

class MatrixKeypad {
private:
  // 引脚定义 - 使用所有支持内部上拉的GPIO
  int rowPins[4] = {4, 0, 2, 5};    // D2, D3, D4, D1 - 作为输出
  int colPins[4] = {12, 13, 14, 15}; // D6, D7, D5, D8 - 作为输入(内部上拉)
  
  // 键盘映射 - 标准电话键盘布局
  char keyMap[4][4] = {
    {'1', '2', '3', 'A'},
    {'4', '5', '6', 'B'}, 
    {'7', '8', '9', 'C'},
    {'*', '0', '#', 'D'}
  };
  
  // 消抖参数
  unsigned long lastDebounceTime = 0;
  const unsigned long debounceDelay = 20;
  char lastKey = '\0';
  bool keyProcessed = true;

public:
  /**
   * 初始化键盘
   */
  void begin() {
    Serial.println("初始化4×4矩阵键盘...");
    
    // 设置行引脚为输出，初始为HIGH
    for (int i = 0; i < 4; i++) {
      pinMode(rowPins[i], OUTPUT);
      digitalWrite(rowPins[i], HIGH);
      Serial.printf("行%d - GPIO%d 设置为输出\n", i, rowPins[i]);
    }
    
    // 设置列引脚为输入，启用内部上拉
    for (int i = 0; i < 4; i++) {
      pinMode(colPins[i], INPUT_PULLUP);
      Serial.printf("列%d - GPIO%d 设置为输入(上拉)\n", i, colPins[i]);
    }
    
    Serial.println("键盘初始化完成");
    printPinMapping();
  }
  
  /**
   * 扫描键盘并返回按下的键
   * @return 按下的键字符，如无按键返回'\0'
   */
  char getKey() {
    char currentKey = scanKeypad();
    
    // 消抖处理
    if (currentKey != lastKey) {
      lastDebounceTime = millis();
      lastKey = currentKey;
      keyProcessed = false;
    }
    
    if ((millis() - lastDebounceTime) > debounceDelay) {
      if (!keyProcessed && currentKey != '\0') {
        keyProcessed = true;
        return currentKey;
      }
    }
    
    return '\0';
  }
  
  /**
   * 非阻塞扫描 - 立即返回当前按键状态
   * @return 当前检测到的按键(未经消抖)
   */
  char scanImmediate() {
    return scanKeypad();
  }
  
  /**
   * 等待按键释放
   */
  void waitForKeyRelease(char key) {
    while (scanKeypad() == key) {
      delay(10);
    }
  }
  
  /**
   * 读取数字密码(直到#号结束)
   * @param buffer 存储密码的缓冲区
   * @param maxLength 最大长度
   * @return 实际输入的密码长度
   */
  int readPassword(char* buffer, int maxLength) {
    int length = 0;
    Serial.println("请输入密码，以#结束:");
    
    while (length < maxLength - 1) {
      char key = getKey();
      if (key != '\0') {
        if (key == '#') {
          buffer[length] = '\0';
          Serial.println("\n密码输入完成");
          return length;
        } else if (key >= '0' && key <= '9') {
          buffer[length++] = key;
          Serial.print('*'); // 用*号显示密码输入
        } else {
          Serial.println("\n只允许输入数字!");
        }
      }
      delay(10);
    }
    
    buffer[length] = '\0';
    return length;
  }
  
  /**
   * 打印引脚映射信息
   */
  void printPinMapping() {
    Serial.println("\n=== 键盘引脚映射 ===");
    Serial.println("行引脚(输出):");
    for (int i = 0; i < 4; i++) {
      Serial.printf("  行%d -> GPIO%d (D%d)\n", i, rowPins[i], 
                   getDNumber(rowPins[i]));
    }
    
    Serial.println("列引脚(输入上拉):");
    for (int i = 0; i < 4; i++) {
      Serial.printf("  列%d -> GPIO%d (D%d)\n", i, colPins[i], 
                   getDNumber(colPins[i]));
    }
    
    Serial.println("键盘布局:");
    for (int r = 0; r < 4; r++) {
      Serial.printf("  [%c] [%c] [%c] [%c]\n", 
                   keyMap[r][0], keyMap[r][1], keyMap[r][2], keyMap[r][3]);
    }
    Serial.println("===================\n");
  }
  
  /**
   * 调试模式 - 实时显示按键状态
   */
  void debugMode() {
    Serial.println("进入调试模式 - 显示所有按键状态");
    Serial.println("按下任意键开始扫描，按'#'退出调试模式");
    
    // 等待任意按键开始
    while (getKey() == '\0') {
      delay(100);
    }
    
    while (true) {
      // 实时扫描并显示所有行列状态
      for (int r = 0; r < 4; r++) {
        digitalWrite(rowPins[r], LOW);
        for (int c = 0; c < 4; c++) {
          int state = digitalRead(colPins[c]);
          if (state == LOW) {
            Serial.printf("按键按下: 行%d 列%d -> '%c'\n", r, c, keyMap[r][c]);
          }
        }
        digitalWrite(rowPins[r], HIGH);
      }
      
      // 检查是否退出调试模式
      char key = getKey();
      if (key == '#') {
        Serial.println("退出调试模式");
        break;
      }
      
      delay(200); // 扫描间隔
    }
  }

private:
  /**
   * 核心扫描函数 - 逐行扫描检测按键
   */
  char scanKeypad() {
    for (int r = 0; r < 4; r++) {
      // 将当前行拉低
      digitalWrite(rowPins[r], LOW);
      
      // 检查所有列
      for (int c = 0; c < 4; c++) {
        if (digitalRead(colPins[c]) == LOW) {
          // 检测到按键，恢复行状态后返回键值
          digitalWrite(rowPins[r], HIGH);
          return keyMap[r][c];
        }
      }
      
      // 恢复当前行状态
      digitalWrite(rowPins[r], HIGH);
    }
    
    return '\0'; // 无按键
  }
  
  /**
   * 获取GPIO对应的D引脚编号
   */
  int getDNumber(int gpio) {
    switch(gpio) {
      case 0: return 3;
      case 2: return 4;
      case 4: return 2;
      case 5: return 1;
      case 12: return 6;
      case 13: return 7;
      case 14: return 5;
      case 15: return 8;
      default: return -1;
    }
  }
};

// 全局键盘对象
MatrixKeypad keypad;

void setup() {
  Serial.begin(115200);
  delay(1000); // 等待串口初始化
  
  Serial.println("\n=== Node MCU 4×4矩阵键盘驱动 ===");
  
  // 初始化键盘
  keypad.begin();
  
  // 显示使用说明
  Serial.println("使用说明:");
  Serial.println("1. 输入数字进行测试");
  Serial.println("2. 按'*'进入调试模式");
  Serial.println("3. 按'A'开始密码输入演示");
  Serial.println("4. 按'D'显示引脚映射");
  Serial.println("==============================\n");
}

void loop() {
  char key = keypad.getKey();
  
  if (key != '\0') {
    Serial.printf("按键: '%c'\n", key);
    
    // 特殊功能键处理
    switch(key) {
      case '*':
        keypad.debugMode();
        break;
        
      case 'A':
        {
          char password[20];
          int len = keypad.readPassword(password, sizeof(password));
          if (len > 0) {
            Serial.printf("输入的密码长度: %d\n", len);
          }
        }
        break;
        
      case 'D':
        keypad.printPinMapping();
        break;
    }
    
    // 等待按键释放
    keypad.waitForKeyRelease(key);
  }
  
  delay(10); // 主循环延时
}