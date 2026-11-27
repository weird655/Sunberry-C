# Sigil-C 暴力测试作战手册
## 给 Gemini 的 Adversarial Testing Prompt

> 目标仓库：`C:\Users\Admin\WorkBuddy AI\2026-11-12-00-51-06\Sigil-C`  
> 当前版本：`1.30.0`  
> 当前提交：`d9c2e76`  
> 当前测试：`272 / 96 layers`  
> 当前覆盖率：`95%`（303 / 5617 未覆盖，coverage 整数口径）  
> 目标平台：Windows x64，Python 3.14，gcc（MSYS2 UCRT64）  
> 任务：**暴力找 bug，不是继续加功能，也不是刷覆盖率。**

---

# 0. 给 Gemini 的启动指令（复制这一段）

```text
你是 Sigil-C 的对抗测试工程师。

请先完整读取本文件：
ADVERSARIAL_TESTING_GEMINI.md

目标：在提交 d9c2e76 上暴力测试 Sigil-C，找真实缺陷。
不要先改源码；先测，保留最小复现，再报告。
不要用 # pragma: no cover 刷覆盖率。
不要为了“让测试通过”改断言。
不要碰 DFHack/DFCN/DFAI。

工作目录：
C:\Users\Admin\WorkBuddy AI\2026-11-12-00-51-06\Sigil-C

基线必须先跑：
1. git rev-parse HEAD
2. python test_matrix.py
3. python tools/check.py --coverage
4. python tools/fuzz.py --iterations 1000 --seed 20261127
5. python tools/propgen.py --count 300 --seed 20261127
6. python tools/runcheck.py --count 300 --seed 20261127
7. python tools/difftest.py

第一轮只做：
A. 基线复现
B. 1000 个 mutation fuzz
C. 100 个 CLI/多文件/诊断用例
D. 输出报告

发现 bug 时：
- 先最小化
- 保存输入 + 命令 + 输出
- 不要猜原因
- 不要直接大改架构
- 报告后再等我确认修复方案

所有临时文件放：
artifacts/adversarial/<date>/
不要覆盖仓库、存档、用户文件。
```

---

# 1. 测试目标

## 1.1 找什么

按严重度：

```text
P0：崩溃 / Python traceback / 卡死 / 生成物损坏 / 非零退出但无诊断
P1：错误 C / C 编译失败 / 运行结果错 / UB / 内存越界
P2：错误诊断（行号/列号/文件错、JSON/LSP 错、错误信息误导）
P3：CLI/文档/可用性问题
```

## 1.2 不找什么

- 不找“我觉得应该支持但文档说不支持”的功能。
- 不把已知限制当 bug：
  - 跨文件 `vN` 不导出
  - TNX 非 GCC/Clang 只有单线程 fallback
  - 覆盖率 95% 不等于正确率
- 不测 DFHack/DFCN/DFAI。
- 不测不存在的 API。
- 不为了覆盖率加无效测试。

## 1.3 核心不变量

```text
1. 编译器不能抛未捕获异常（除明确的 ParseError/SemanticError/LexerError）
2. 错误必须带文件:行:列；不能只给 traceback
3. 合法输入生成的 C 必须能过：
   gcc -std=c99 -Wall -Wextra -Werror -pedantic
4. 同一输入两次生成必须字节一致（除临时路径/时间戳）
5. JSON 诊断 line/column 不能是 0（除非真的无法定位）
6. LSP 诊断 range 必须和错误行一致
7. 多文件 --build 的错误行号必须是原文件行号
8. 深嵌套必须给“nesting too deep”，不能 RecursionError
9. 任何 fuzz 输入不能 hang（单例超时 10s）
10. 失败用例必须可复现
```

---

# 2. 基线

## 2.1 工作区

```text
C:\Users\Admin\WorkBuddy AI\2026-11-12-00-51-06\Sigil-C
```

先确认：

```powershell
git status --short
git rev-parse HEAD
git log --oneline -3
```

期望：

```text
worktree clean
HEAD = d9c2e76
```

## 2.2 全量测试

```powershell
$env:PYTHONUTF8 = "1"
python test_matrix.py
```

期望：

```text
=== ALL 272/272 TESTS IN 96-LAYER MATRIX PASSED! ===
```

## 2.3 质量门 + 覆盖率

```powershell
python tools/check.py --coverage
```

期望：

```text
All checks passed.
TOTAL ... 95%
```

## 2.4 已有 fuzz / 差分

```powershell
python tools/fuzz.py --iterations 1000 --seed 20261127
python tools/propgen.py --count 300 --seed 20261127
python tools/runcheck.py --count 300 --seed 20261127
python tools/difftest.py
```

期望：

```text
fuzz: ... only expected errors
propgen: ... passed
runcheck: ... agree
difftest: ... agree
```

如果基线任何一项失败，**先停**，报告失败，不要继续 fuzz。

---

# 3. 测试资产

## 3.1 临时目录

```text
artifacts/adversarial/20261127/
  baseline/
  fuzz/
  parser/
  cli/
  project/
  lsp/
  vn/
  tnx/
  crashes/
  hangs/
  wrong-c/
```

## 3.2 失败保存格式

每个失败一个目录：

```text
crashes/<case-id>/
  input.sigil
  command.txt
  stdout.txt
  stderr.txt
  exit.txt
  generated.c          # 如果有
  gcc.txt              # 如果编译过
  notes.md
```

`notes.md`：

```text
case id:
severity:
commit:
command:
expected:
actual:
repro:
suspected area:
```

---

# 4. Lexer 暴力测试

## 4.1 字符/字面量

覆盖：

- 空文件
- 只有注释
- 未闭合 `/*`
- 未闭合字符串/字符
- `\0`、`\x`、八进制转义
- `\x` 超长、八进制越界
- 数字：`0x`、`0b`、`0x1p`、`1e`、`1.2.3`、`09`、`0778`
- 超长数字/标识符
- Unicode、BOM、CRLF、NUL
- 非法 token

## 4.2 mutation

从 `examples/tutorial/*.sigil`、`golden.sigil` 取种子，做：

```text
删 1 字符
插 1 字符
替换 1 字符
截断
复制一行
交换两行
插入随机字节
插入 NUL
插入 BOM
CRLF 化
```

每个输入：

- 超时 10s
- 捕获所有 stdout/stderr
- 只允许 LexerError/ParseError/SemanticError
- 不允许 traceback
- 不允许 hang

## 4.3 量

```text
至少 1000 例
至少 50 个 crash 候选
```

---

# 5. Parser / 语义暴力测试

## 5.1 语法变异

- 深括号：60 / 70 / 400 / 500
- 深 block：400 / 500
- 超长标识符：5k / 50k
- 超长表达式链：`1+1+...`
- 空结构体/空枚举/空 union
- 重复字段/参数/标签/case
- 错误类型组合
- 未声明标识符批量（一次 4 个）
- 非法 attribute 参数

## 5.2 语义边界

- const 赋值
- 数组越界常量
- 指针来源/逃逸
- `v.` 参数
- 位域宽度
- 函数指针
- varargs
- 多文件原型冲突
- 包/封锁/地雷

## 5.3 期望

```text
合法输入 → 生成 C → gcc 通过
非法输入 → 干净诊断，不崩
```

---

# 6. vN / TNX 专项

## 6.1 vN

```sigil
v1 { v/ 5 v/ u1 v/ 5 ; }
vA { v/ 300 v/ u2 v/ 300 ; }
```

测试：

- 1/2/3 位十六进制名
- 4 位名字拒绝
- 容量 `u1/u2/u4/u8`
- 字面量最窄宽度
- 变量类型宽度
- 溢出 / 冗余 / 不支持类型
- 重复
- 赋值拒绝
- `p@` 拒绝
- 外部函数读
- `!vN!` 读
- `!vN!` 写拒绝
- 文件级返回值必须常量
- 局部返回值可变量
- 跨文件读：已知不支持，不要报成新 bug

## 6.2 TNX

```sigil
s@ v. handler(v.) { }
T3A { width 8; payload !handler!; next T3B; locked; }
T3B { width 8; payload !handler!; locked; }
```

测试：

- T0A–T9F
- width 8 / 4 / 0
- payload 函数 / 指针 / 数组
- next 同优先级 / 跨优先级 / 自指 / 环 / 缺失
- locked 必填
- 重复字段/容器
- 队列优先级/seq 顺序
- push 满/重复
- pop 空
- `sigil_tnx_execute`
- `link/queued`
- 双线程 producer/consumer
- 非 GCC/Clang fallback（可编译，不保证并发）
- 不是 lock-free，不要报成 bug

---

# 7. CLI / 诊断暴力测试

## 7.1 文件

- 不存在
- 空文件
- 只有空白
- 只有注释
- 2 万行
- 二进制垃圾
- NUL
- 非 UTF-8
- 只读文件/目录
- 奇怪路径（空格/中文/超长）

## 7.2 参数

```text
--check
--check --json
--netlist
--netlist-format text/dot/json/mermaid/html/viewer
--emit-prelude
--emit-header
--header
--prelude
--define NAME=VALUE
--build
--build --run
--build --emit-header
--build --netlist
--fmt
--fmt --fmt-check
--fmt --write
--init
--force
--lsp
--asan
--tsan
--trap-trace
--shadow-stack
--no-line
```

重点：

- 互斥参数：`--trap-trace --shadow-stack`
- `--asan/--tsan` 无 `--build`
- `--asan --tsan` 同用
- `--header` + `--build`
- 无效 `--define`
- 无参数
- `--fmt` 路径缺失

## 7.3 多文件

- 错误行号是否原文件行号
- `--build` 前缀原型偏移
- 重复符号
- 命名空间
- 包重复/越界
- plant gate
- 空目录/只有 plant.sigil

期望：

```text
错误：file:line:col
不是：m.sigil:6:16（实际第 4 行）
不是：Python traceback
```

---

# 8. JSON / LSP 专项

## 8.1 JSON

输入 4 个未定义标识符：

```sigil
i4 main(v.) {
    a1;
    a2;
    a3;
    a4;
}
```

`--check --json` 期望：

```json
{"diagnostics": [
  {"line": 2, "column": 5, ...},
  {"line": 3, "column": 5, ...},
  {"line": 4, "column": 5, ...},
  {"line": 5, "column": 5, ...}
]}
```

不能：

```json
[{"line": 0, "column": 0, "message": "a1\na2\na3\na4"}]
```

## 8.2 LSP

`_lsp_diagnostics` 或真实 LSP 客户端：

- 4 条诊断
- range line 1/2/3/4
- 不是全部 line 0

## 8.3 错误

- 单错误 JSON line/col 正确
- 多错误 JSON 展开
- LSP 单错误/多错误
- 未知方法
- 空 document
- 未打开 document 的 completion/symbol

---

# 9. 生成 C / 差分 / Sanitizer

## 9.1 编译

合法程序：

```powershell
gcc -std=c99 -Wall -Wextra -Werror -pedantic out.c -o out.exe
```

再加：

```powershell
-fsanitize=address,undefined -fno-omit-frame-pointer -g
```

如果环境无 ASan/UBSan，记录并跳过，不要报编译器 bug。

## 9.2 差分

- `tools/difftest.py`
- `tools/runcheck.py`
- 随机合法程序 → gcc + 运行 → 与 Python 参考对比

## 9.3 不变量

- 生成 C 不含未定义宏
- `#line` 行号不越界/不为负
- 同一输入两次输出一致
- `--no-line` 只影响 `#line`
- header 与 source 声明一致

---

# 10. 性能 / 资源

## 10.1 压力

```text
2 万行
5000 字符标识符
400 层 block
70 层括号
1000 个 vN/TNX
```

## 10.2 观察

```text
耗时
峰值内存
递归深度
是否 hang
```

## 10.3 期望

- 深嵌套：干净 `nesting too deep`
- 大文件：可完成，或明确资源错误
- 不允许 RecursionError traceback

---

# 11. Fuzz 策略

## 11.1 种子

- `golden.sigil`
- `examples/tutorial/*.sigil`
- `examples/*.sigil`
- 本次新增 vN/TNX 示例
- 多文件项目

## 11.2 变异

```text
token 级：插入/删除/替换
行级：删除/复制/交换/截断
字符级：随机字节/NUL/BOM/Unicode
结构级：括号/大括号不配对
```

## 11.3 预算

```text
第一轮：1000 mutation，单例 10s
第二轮：300 grammar，单例 10s
第三轮：100 CLI/project，单例 30s
```

## 11.4 去重

按：

```text
异常类型 + 最后一行 + 关键错误消息
```

聚类；同一根因只报一次最小复现。

---

# 12. 最小化 / 报告

## 12.1 最小化

- 删行
- 删 token
- 缩短标识符
- 简化表达式
- 保留触发条件

## 12.2 报告模板

```markdown
## Finding: <short title>

- Severity: P0/P1/P2/P3
- Commit: d9c2e76
- Command:
- Input:
- Expected:
- Actual:
- Repro:
- Suspected area:
- Evidence:
- Is it a known limitation? yes/no
```

## 12.3 不要做的事

- 不要“顺手修一下”然后隐藏失败。
- 不要改测试期望来变绿。
- 不要用 `# pragma: no cover`。
- 不要把已知限制当新 bug。
- 不要没复现就报。

---

# 13. 第一轮交付

Gemini 第一轮只交：

```text
1. 基线结果
2. 1000 mutation 的统计
3. 所有 P0/P1 的最小复现
4. 已知限制确认
5. 下一轮建议
```

不要交：

```text
- 全量重构
- 未验证的修复
- 覆盖率报告当质量证明
```

---

# 14. 一句话

> **覆盖率是地图，不是领土。**  
> 这轮的任务是找地图上没画的坑：崩溃、错误 C、错行号、错 JSON、错 LSP、卡死、UB。

---

# 15. 参考

- 仓库：`C:\Users\Admin\WorkBuddy AI\2026-11-12-00-51-06\Sigil-C`
- 测试矩阵：`test_matrix.py`
- 一键检查：`tools/check.py`
- Fuzz：`tools/fuzz.py`
- 属性测试：`tools/propgen.py`
- 差分：`tools/difftest.py`
- 运行语义：`tools/runcheck.py`
- 基准：`tools/bench.py`
- 目标提交：`d9c2e76`
- 版本：`1.30.0`
- 测试：`272 / 96`
- 覆盖率：`95%`（303 / 5617 未覆盖）

> 以上数字是当前工具口径，不是正确率保证。
