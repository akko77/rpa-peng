# AutoWorkflow — 网页自动化工作流构建器

**版本**: 0.1 (设计阶段)
**日期**: 2026-05-18
**基于**: `collect_auto.py` 重构

---

## 1. 项目概览

### 1.1 项目背景

原脚本 `collect_auto.py` 通过 pyautogui 实现了一个"读取公司名 → 网页搜索 → 截图趋势图 → 写回 Excel"的自动化流程。痛点：

- 屏幕坐标、模板图片名硬编码散落在代码各处
- 业务逻辑（Excel 读写、截图归档、进度恢复）与自动化逻辑（点击、查找、循环）深度耦合
- 每个新的自动化任务都要复制一份脚本，重新调坐标、改图片、调试
- 模板图片靠目录约定，多模板轮询用 `for template in templates` 列表手写

### 1.2 重构目标

把"网页自动化"抽象成**可视化的工作流构建工具**：

- 一套工具，多套流程，工作流以 JSON 存档
- 通过 GUI 拾取屏幕坐标、框选模板，告别坐标硬编码
- 步骤化编排，每步显式声明成功/失败跳转
- 支持数据源驱动循环 + 过滤
- 工作流可嵌套调用（子流程）
- 提供"录制鼠标键盘 → 自动生成步骤草稿"以加速编排
- 单步调试、断点、暂停/恢复、断点续跑
- 业务逻辑（Excel、截图归档等）**剥离出去**；如有需要后续作为插件式扩展点接入

### 1.3 项目名 / 工作目录

工作名 **AutoWorkflow**，工作目录 `auto_workflow/`。最终名可定。

---

## 2. 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| GUI 框架 | **PySide6** (Qt for Python, LGPL) | 与已有 PySide6 项目经验一致；对屏幕坐标、全局热键、窗口控制支持直接 |
| 自动化引擎 | pyautogui + pyperclip | 沿用原脚本生态，平滑迁移 |
| 图像匹配 | **opencv-python** + Pillow | 替代 `pyautogui.locateOnScreen`，支持多尺度匹配，置信度更稳定 |
| 全局热键 / 鼠键监听（录制） | **pynput** | 不需要管理员权限，跨平台 API 一致 |
| 表达式求值（过滤） | **simpleeval** | 安全的 Python 表达式子集，避免 `eval()` 风险 |
| Windows 窗口控制 | **pywin32** | 实现 `focus_window` 步骤（按窗口标题切换前台窗口） |
| 工作流存储 | JSON | 文本可 diff、可版本控制 |
| JSON Schema 校验 | jsonschema | 加载工作流时校验结构 |
| 日志 | Python `logging` + GUI 实时面板 | 沿用原脚本风格 |

**目标平台**: Windows（不考虑跨平台），无 DPI 缩放场景，不需要管理员权限运行。

---

## 3. 模块结构

```
auto_workflow/
├── app/
│   ├── main.py                       # 应用入口
│   ├── ui/
│   │   ├── main_window.py            # 主窗口（三栏布局）
│   │   ├── step_list_panel.py        # 左栏：步骤列表（拖拽排序、断点、禁用）
│   │   ├── step_editor_panel.py      # 中栏：步骤参数编辑器（按类型切换表单）
│   │   ├── side_tabs/
│   │   │   ├── template_library.py   # 右栏 Tab：模板库
│   │   │   ├── data_source_panel.py  # 右栏 Tab：数据源 + 过滤器
│   │   │   ├── variable_panel.py     # 右栏 Tab：变量监视
│   │   │   └── settings_panel.py     # 右栏 Tab：工作流设置
│   │   ├── overlays/
│   │   │   ├── position_picker.py    # 屏幕坐标拾取浮层（F8）
│   │   │   ├── region_picker.py      # 屏幕区域框选浮层
│   │   │   └── recorder_overlay.py   # 录制时的红点指示条
│   │   ├── dialogs/
│   │   │   ├── recorder_toolbar.py   # 录制暂停时的工具条（Pause 触发）
│   │   │   ├── filter_builder.py     # 数据源过滤的可视化构建器 + 表达式模式
│   │   │   └── window_picker.py      # focus_window 步骤的窗口选择器
│   │   ├── run_control.py            # 运行时悬浮控制条（暂停/继续/停止）
│   │   └── log_panel.py              # 底部日志面板
│   ├── core/
│   │   ├── workflow.py               # Workflow 数据模型
│   │   ├── step.py                   # Step 基类与子类
│   │   ├── executor.py               # 执行引擎（暂停/单步/断点）
│   │   ├── context.py                # 运行时上下文（变量、迭代器、当前 item）
│   │   ├── interpolator.py           # ${var} / ${item.field} 变量插值
│   │   ├── matcher.py                # opencv 图像匹配封装（first_hit / best_score）
│   │   ├── checkpoint.py             # 断点续跑状态管理
│   │   ├── filter_evaluator.py       # simpleeval 包装
│   │   └── validators.py             # 工作流静态校验（含递归检测）
│   ├── actions/                      # 各步骤动作实现（一个文件一种步骤）
│   │   ├── base.py                   # ActionBase
│   │   ├── click.py
│   │   ├── type_text.py
│   │   ├── paste.py
│   │   ├── hotkey.py
│   │   ├── wait.py
│   │   ├── scroll.py
│   │   ├── find_image.py
│   │   ├── focus_window.py
│   │   ├── set_variable.py
│   │   ├── log.py
│   │   ├── loop_data.py
│   │   ├── conditional.py
│   │   ├── break_continue.py
│   │   └── call_workflow.py
│   ├── recorder/
│   │   ├── recorder.py               # pynput 监听 + 事件合并
│   │   ├── event_aggregator.py       # 连续按键合并、停顿检测
│   │   └── synthesizer.py            # 事件流 → Step 草稿列表
│   └── persistence/
│       ├── workflow_io.py            # 工作流加载/保存
│       ├── schema.py                 # JSON Schema 定义
│       └── template_io.py            # 模板图片库读写
├── workflows/                        # 用户工作流文件（*.awf.json）
├── templates/                        # 模板图片库
│   └── <group_name>/
│       ├── v1.png
│       ├── v2.png
│       └── meta.json
├── .run/                             # 运行时状态
│   └── <workflow_name>_state.json
├── logs/
├── tests/
└── requirements.txt
```

---

## 4. 核心数据模型

使用 `dataclasses` 定义，配合 `dataclasses-json` 或自实现的序列化。

```python
# core/workflow.py
@dataclass
class Workflow:
    name: str
    description: str = ""
    version: str = "0.1"
    data_source: Optional[DataSource] = None     # 顶层数据源（子流程禁止）
    variables: Dict[str, Any] = field(default_factory=dict)
    settings: WorkflowSettings = field(default_factory=WorkflowSettings)
    steps: List[Step] = field(default_factory=list)
    templates: Dict[str, TemplateGroup] = field(default_factory=dict)

@dataclass
class WorkflowSettings:
    short_pause_sec: int = 360
    short_pause_every: int = 5
    long_pause_sec: int = 1800
    long_pause_every: int = 15
    default_step_timeout: float = 10.0
    failure_policy: str = "continue"             # continue | abort | retry
    retry_max: int = 2
    record_merge_threshold_sec: float = 1.5      # 录制时连续输入合并阈值
    record_idle_to_wait_sec: float = 1.5         # 录制时停顿自动插 wait 的阈值

@dataclass
class DataSource:
    type: str                                    # csv | xlsx | json | inline
    path: Optional[str] = None
    sheet: Optional[str] = None                  # for xlsx
    column: Optional[str] = None                 # 只取一列时使用
    inline_items: Optional[List[Any]] = None     # for inline
    start_index: int = 0
    end_index: Optional[int] = None
    skip_empty: bool = True
    filter: Optional[Filter] = None

@dataclass
class Filter:
    mode: str                                    # visual | expression
    expression: Optional[str] = None             # for expression mode
    rules: Optional[List[FilterRule]] = None     # for visual mode
    combinator: str = "and"                      # for visual: and | or

@dataclass
class FilterRule:
    field: str
    operator: str                                # == != > >= < <= contains startswith endswith in not_in
    value: Any

@dataclass
class TemplateGroup:
    name: str
    variants: List[TemplateVariant]
    default_region: Optional[Tuple[int, int, int, int]] = None
    match_strategy: str = "first_hit"            # first_hit | best_score
    default_confidence: float = 0.7

@dataclass
class TemplateVariant:
    file: str                                    # 相对 templates/ 的路径
    confidence: float = 0.7
    added_at: str = ""
    note: str = ""

# core/step.py
@dataclass
class Step:
    id: str                                      # 短 uuid 或自增字符串
    type: str                                    # click / type_text / find_image / ...
    name: str                                    # 用户起的可读名
    enabled: bool = True
    breakpoint: bool = False
    params: Dict[str, Any] = field(default_factory=dict)
    on_success: Optional[str] = None             # 目标 step id；None=按顺序
    on_failure: Optional[str] = None             # None=按 failure_policy
    timeout: Optional[float] = None              # 覆盖 settings.default_step_timeout
```

---

## 5. 步骤类型完整清单

| 类型 | 主要参数 | 失败语义 |
|---|---|---|
| `click` | `position`: 坐标对象（见下）; `button`: left/right/middle; `clicks`: 1/2 | 找不到模板视为失败 |
| `type_text` | `text` (支持 `${var}` 插值); `interval`: 每键间隔 | 键盘异常 |
| `paste` | `text` (支持插值) | 剪贴板异常 |
| `hotkey` | `keys`: 如 `ctrl+a` / `ctrl+shift+t` | - |
| `wait` | `mode`: fixed/until_image; `seconds` / `template`/`region`/`timeout` | until_image 超时为失败 |
| `scroll` | `direction`: up/down; `amount`: 滚轮单位; `at_position`: 可选 | - |
| `find_image` | `template`: 组名; `region` (可选覆盖组默认); `confidence` (可选覆盖) | 未找到为失败；结果写 `${found}`、`${match_pos}`、`${match_score}` |
| `focus_window` | `title_pattern`: 正则; `exact`: bool; `class_name` (可选) | 找不到窗口为失败 |
| `set_variable` | `name`; `value` (支持表达式) | - |
| `log` | `message` (支持插值); `level`: info/warn/error | - |
| `loop_data` | `source` (内嵌的 DataSource 或继承顶层); `item_var`: 变量名; `body`: List[Step] | 子步骤异常按内部策略 |
| `if` | `condition` (表达式); `then`: List[Step]; `else`: List[Step] | - |
| `break` / `continue` | - | 控制流，不会"失败" |
| `call_workflow` | `path`; `input`: dict 映射; `output`: dict 映射 | 子流程整体失败 |

### 5.1 `position` 对象的三种形态

`click`、`scroll`、`paste` 等需要落点的步骤，`position` 字段统一支持三种：

```json
// 形态 A：固定坐标
{"position": {"type": "fixed", "x": 690, "y": 148}}

// 形态 B：动态模板（运行时通过 find_image 找到）
{"position": {"type": "template", "template": "search_box", "anchor": "center"}}

// 形态 C：引用变量
{"position": {"type": "variable", "var": "match_pos"}}
```

这样一个 `click` 步骤就涵盖了原脚本里"点固定坐标"和"找到图标后点击中心"两种用法。

### 5.2 失败跳转规则

每个步骤：
1. 执行成功 → 跳到 `on_success`（None 则顺序下一步）
2. 执行失败 → 跳到 `on_failure`（None 则走 `settings.failure_policy`）
3. `failure_policy = continue`：记日志，跳下一步
4. `failure_policy = abort`：整个工作流终止
5. `failure_policy = retry`：在原步骤重试 `retry_max` 次，仍失败转为按 continue 处理

---

## 6. 录制功能

### 6.1 录制机制

使用 **pynput** 全局监听鼠标和键盘事件，实时聚合后生成步骤草稿。

**事件处理规则**：

| 原始事件 | 处理 |
|---|---|
| 鼠标移动 | 忽略 |
| 鼠标单击 | 立即生成 `click` 步骤（含坐标，无模板） |
| 鼠标双击 | 单个 `click` 步骤，`clicks=2` |
| 鼠标右键 | `click` 步骤，`button=right` |
| 鼠标滚轮 | `scroll` 步骤（合并连续同向滚动） |
| 普通按键 | 加入"输入缓冲区" |
| 输入缓冲区停顿超过阈值 | 缓冲区内容封装成 `type_text` 步骤 |
| 修饰键组合（Ctrl+X 等） | 先 flush 输入缓冲区，再生成 `hotkey` 步骤 |
| 任意操作间隔超过 `record_idle_to_wait_sec` | 自动插入一个 `wait` 步骤 |

**连续输入合并阈值**：默认 1.5 秒，写在 `settings.record_merge_threshold_sec`，用户可在设置面板修改。

### 6.2 录制控制

**唯一打断键：`Pause` 键**（避开 F12 等浏览器/网页占用的键，避开 IME 冲突的 Ctrl+Alt+x 组合）。

录制流程：
1. 主窗口点【开始录制】→ 弹出小对话框，选择**录制结果处理模式**：
   - 追加到末尾（默认）
   - 插入到当前选中位置
   - 覆盖当前步骤列表
2. 主窗口最小化 → 屏幕右下角出现红点指示条（显示时长 + 已录步骤数）
3. 用户实际操作目标网页
4. 任意时候按 **Pause** → 录制暂停，屏幕中央弹出工具条：
   - 【标记模板】：进入框选模式，框选后自动生成 `find_image` 步骤插入到当前位置
   - 【标记循环开始/结束】：插入循环边界占位（结束录制后由 synthesizer 转换为 `loop_data` 结构）
   - 【插入变量/日志】：弹小输入框，生成 `set_variable` 或 `log` 步骤
   - 【继续录制】：关闭工具条，恢复监听
   - 【结束录制】：关闭工具条，结束录制
5. 录制结束 → 录制器将事件流交给 `synthesizer` → 生成 Step 草稿列表 → 按用户选择的模式合并到工作流
6. 用户在主窗口 review 草稿，修改/合并/补参数

### 6.3 录制限制（明确不支持）

- 拖拽（按住鼠标移动）：MVP 阶段不录制为单一步骤，会被记为"按下+松开"两次 click（用户后续如有需要可手工编辑）
- 鼠标悬停触发（hover）：无法可靠检测，用户需要手工补 `wait` 步骤

---

## 7. 屏幕拾取与区域框选

### 7.1 坐标拾取（F8）

- 入口：步骤编辑器中需要坐标的字段旁的【拾取位置】按钮
- 触发后主窗口最小化 → 屏幕显示半透明十字辅助线 + 实时坐标 HUD
- 按 **F8** 抓取当前鼠标位置；按 **Esc** 取消
- 抓取后主窗口恢复，坐标自动填回字段
- 字段旁的【验证】按钮：临时弹一个红点高亮该坐标 1 秒钟，便于确认

### 7.2 区域框选（无独立快捷键，按钮触发）

- 入口：`find_image` 步骤的【框选模板】按钮；或模板库的【新建模板】按钮；或录制工具条的【标记模板】
- 触发后主窗口最小化 → 屏幕进入全屏半透明遮罩
- 鼠标拖拽矩形（实时显示宽高与起点坐标）
- 释放后弹窗：
  - 模板组名（自动建议或用户输入）
  - 如果组已存在 → 询问"新增到此组作为新 variant" 或 "替换某个 variant"
  - 备注（可选）
- 保存到 `templates/<group_name>/v<N>.png`，更新 `meta.json`

---

## 8. 工作流嵌套（call_workflow）

### 8.1 参数传递

```json
{
  "id": "s_login",
  "type": "call_workflow",
  "name": "执行登录",
  "params": {
    "path": "workflows/sub_login.awf.json",
    "input":  {"username": "${current_user}", "password": "${pwd}"},
    "output": {"session_token": "token", "user_id": "uid"}
  }
}
```

- **input**：父变量映射到子流程的变量空间（key=子流程变量名，value=父端表达式）
- **output**：子流程结束时把它的某些变量回写到父变量（key=父变量名，value=子流程变量名）
- **变量隔离**：子流程默认看不到父变量，必须通过 input 显式传递
- **数据源**：子流程**不允许**有顶层 `data_source`（加载时校验）；需要嵌套循环用 `loop_data` 步骤
- **失败传播**：子流程整体作为一个步骤，失败按父流程的 `on_failure` 和 `failure_policy` 处理

### 8.2 禁止递归

加载工作流时进行**静态校验**（`validators.py`）：

- 构建工作流引用图：节点 = 工作流文件路径，边 = call_workflow 引用
- DFS 检测是否存在环
- 若存在直接/间接递归 → 加载失败，明确报错

---

## 9. 数据源与过滤

### 9.1 支持的格式

| type | 配置 | item 类型 | 访问方式 |
|---|---|---|---|
| `csv` | `path`, `column?` | dict / str | `${item.col_name}` 或 `${item}` |
| `xlsx` | `path`, `sheet?`, `column?` | dict / str | 同上 |
| `json` | `path` (数组或对象) | 元素类型 | `${item}` 或 `${item.field}` |
| `inline` | `inline_items` (列表) | 元素类型 | 同上 |

**通用选项**：
- `start_index`：从第 N 项开始（断点续跑或手工跳过）
- `end_index`：结束索引（可选）
- `skip_empty`：跳过空行/空项

### 9.2 过滤器

**双模式设计**：

**A. 可视化模式（默认，给非开发者用户）**：
UI 是一行行的条件，每行 `[字段下拉] [操作符下拉] [值输入]`，最后一个组合方式选择器（`and` / `or`）。

```json
"filter": {
  "mode": "visual",
  "combinator": "and",
  "rules": [
    {"field": "industry", "operator": "==", "value": "制造业"},
    {"field": "revenue", "operator": ">", "value": 1000},
    {"field": "name", "operator": "contains", "value": "科技"}
  ]
}
```

可视化模式支持的操作符：`==`、`!=`、`>`、`>=`、`<`、`<=`、`contains`、`startswith`、`endswith`、`in`、`not_in`。

**B. 表达式模式（高级，给开发者）**：
直接用 `simpleeval` 求值的 Python 表达式子集。

```json
"filter": {
  "mode": "expression",
  "expression": "item.industry == \"制造业\" and item.revenue > 1000 and \"科技\" in item.name"
}
```

允许：比较、`and/or/not`、`in/not in`、字符串方法（startswith/endswith/lower/upper/strip/replace）、`len()`、算术运算。
禁止：import、函数定义、文件 IO、循环、属性赋值。

**UI 切换**：过滤器面板上方有 [可视化] / [表达式] 切换 Tab。从可视化切到表达式时，自动把可视化规则翻译成等价表达式（一次性，之后用户编辑表达式不会反向同步回去）；从表达式切到可视化时，弹窗提示"无法自动转换，切换将清空当前表达式，是否继续？"。

**试算按钮**：点击后用数据源的前 5 项跑一遍过滤器，预览哪些通过、哪些被滤掉。

---

## 10. 模板组（应对多模板轮询）

### 10.1 存储结构

```
templates/
└── canbaorenshu/
    ├── v1.png
    ├── v2.png
    └── meta.json
```

`meta.json`：

```json
{
  "name": "canbaorenshu",
  "default_region": null,
  "default_confidence": 0.7,
  "match_strategy": "first_hit",
  "variants": [
    {"file": "v1.png", "confidence": 0.7, "added_at": "2026-05-18", "note": "标准版"},
    {"file": "v2.png", "confidence": 0.7, "added_at": "2026-05-18", "note": "带数字标记版"}
  ]
}
```

### 10.2 匹配策略

`find_image` 步骤引用模板组名，引擎按 `match_strategy` 处理：

- **`first_hit`（默认）**：按 variants 顺序逐个尝试，第一个置信度 ≥ 阈值的命中即返回
  - 速度快，适用于"几个 variant 是同一目标的不同呈现"
- **`best_score`**：所有 variant 都跑一遍模板匹配，返回置信度最高的那个
  - 速度慢但更稳，适用于"variant 之间差异大、容易误匹配低相似度目标"

### 10.3 模板库 UI

右栏 Tab：
- 模板组列表（按名字排序）
- 点击组 → 显示所有 variant 缩略图
- 支持新增 variant（弹出区域框选）、删除 variant、调整 variant 顺序（影响 first_hit 顺序）
- 显示"被哪些步骤引用"，方便重命名/删除前确认影响

---

## 11. 执行引擎

### 11.1 执行状态机

```
       ┌────────┐
       │ Idle   │
       └───┬────┘
           │ run
           ▼
       ┌────────┐  pause   ┌─────────┐
   ┌──▶│Running │─────────▶│ Paused  │
   │   └───┬────┘          └────┬────┘
   │       │                    │ resume
   │       │ step done          ▼
   │       │             (back to Running)
   │       ▼
   │   ┌────────┐
   │   │NextStep│────break/stop───▶ ┌────────┐
   │   └───┬────┘                   │Stopped │
   │       │                        └────────┘
   │       ▼
   │   (next step decision)
   │       │
   └───────┘
```

执行器跑在独立 QThread 里，主线程负责 UI。线程间通过 Qt 信号通信（不要直接共享可变状态）。

### 11.2 暂停 / 单步 / 断点

- **暂停**：执行器在每步开始前检查 `pause_event`，若被设置则阻塞等待
- **单步**：等同于"运行一步后自动暂停"
- **断点**：步骤的 `breakpoint=True`，执行到该步骤开始前自动暂停
- **停止**：设置 `stop_event`，下次步骤检查时立即终止
- 运行时悬浮控制条提供这些按钮

### 11.3 变量插值

`interpolator.py` 实现：

- `${var}` → 从当前 context 取变量
- `${item}` → 当前循环项
- `${item.field}` → 当前循环项的字段（字典访问）
- `${env.PATH}` → 环境变量（可选支持）
- 在所有支持插值的字段（`type_text.text`、`paste.text`、`log.message`、`set_variable.value` 等）上调用

### 11.4 断点续跑

- 运行开始时检查 `.run/<workflow_name>_state.json` 是否存在
- 存在 → 询问用户是否从上次中断处恢复
- 运行中每完成一个数据循环项就更新 state 文件（迭代索引、当前 step id、变量快照）
- 正常运行完毕 → 删除 state 文件

---

## 12. 快捷键总表

| 键 | 上下文 | 行为 |
|---|---|---|
| **F8** | 拾取浮层激活时 | 抓取当前鼠标位置 |
| **Esc** | 拾取/框选浮层激活时 | 取消，返回主窗口 |
| **Pause** | 录制激活时 | 暂停录制，弹出工具条 |
| **Ctrl+S** | 主窗口 | 保存工作流 |
| **Ctrl+O** | 主窗口 | 打开工作流 |
| **Ctrl+N** | 主窗口 | 新建工作流 |
| **F5** | 主窗口 | 运行（试运行一次）|
| **Shift+F5** | 主窗口 | 正式运行（含数据循环）|
| **F10** | 主窗口 | 单步 |
| **F9** | 步骤列表 | 切换当前步骤的断点标记 |
| **Delete** | 步骤列表 | 删除选中步骤 |
| **Ctrl+D** | 步骤列表 | 复制选中步骤 |

注：F5/F9/F10 仅在主窗口聚焦时生效，不会冲突浏览器（pynput 不监听这些；这些是 Qt 自身的快捷键）。Pause 通过 pynput 全局监听，仅录制激活时响应。

---

## 13. Windows 专属说明

### 13.1 环境假设

- **Windows 10/11**，64 位
- **无 DPI 缩放**（系统设置 100%）
- **不需要管理员权限**
- 浏览器：Chrome / Edge / 类似的 Chromium 系列（焦点切换通过 pywin32）

### 13.2 IME 注意事项

用户常用中文/日文 IME。录制时：

- 通过 IME 输入的字符会以"合成事件"出现，pynput 的 `on_press` 抓到的是原始按键（如拼音的 `n`、`i`、`h`、`a`、`o` + 空格选词），不是最终的"你好"
- **MVP 策略**：录制时建议用户**关闭 IME**（用英文/直接输入模式）
- 如果用户必须用 IME 输入中文，正确做法是**手工添加 `paste` 步骤**而不是依赖录制
- 工具条上提供一键【插入 paste 步骤】按钮，弹出输入框让用户粘贴中文内容

### 13.3 focus_window 步骤实现要点

使用 `pywin32`：

```python
import win32gui, win32con
import re

def focus_window(title_pattern: str, exact: bool, class_name: Optional[str]) -> bool:
    def callback(hwnd, results):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        if class_name and cls != class_name:
            return
        if exact:
            if title == title_pattern:
                results.append(hwnd)
        else:
            if re.search(title_pattern, title):
                results.append(hwnd)

    results = []
    win32gui.EnumWindows(callback, results)
    if not results:
        return False
    hwnd = results[0]
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    return True
```

UI 上提供"窗口选择器"对话框：列出当前所有可见窗口（标题 + 类名 + 缩略图），用户点选后自动填充 `title_pattern` 和 `class_name`。

---

## 14. 工作流 JSON 示例

以下是原 `collect_auto.py` 等价流程的简化版（移除 Excel/截图业务部分，保留核心自动化）：

```json
{
  "name": "公司搜索-趋势检测",
  "description": "原 collect_auto.py 重构等价流程（去 Excel/截图）",
  "version": "0.1",
  "data_source": {
    "type": "xlsx",
    "path": "company_list.xlsx",
    "column": "name",
    "start_index": 0,
    "skip_empty": true
  },
  "variables": {},
  "settings": {
    "short_pause_sec": 360,
    "short_pause_every": 5,
    "long_pause_sec": 1800,
    "long_pause_every": 15,
    "failure_policy": "continue"
  },
  "templates": {
    "kexinbaike": {
      "default_region": [350, 430, 1200, 450],
      "default_confidence": 0.5,
      "match_strategy": "first_hit",
      "variants": [{"file": "v1.png", "confidence": 0.5}]
    },
    "chengli_nian_xian": {
      "default_region": [350, 430, 120, 50],
      "default_confidence": 0.5,
      "match_strategy": "first_hit",
      "variants": [{"file": "v1.png", "confidence": 0.5}]
    },
    "tab2": {
      "default_region": [450, 5, 500, 40],
      "default_confidence": 0.7,
      "match_strategy": "first_hit",
      "variants": [{"file": "v1.png", "confidence": 0.7}]
    },
    "tab_close_x": {
      "default_region": [100, 0, 400, 30],
      "default_confidence": 0.7,
      "match_strategy": "first_hit",
      "variants": [{"file": "v1.png", "confidence": 0.7}]
    }
  },
  "steps": [
    {"id": "s1", "type": "paste", "name": "粘贴公司名",
     "params": {"text": "${item}"}},

    {"id": "s2", "type": "click", "name": "点击搜索框",
     "params": {"position": {"type": "fixed", "x": 690, "y": 148}}},

    {"id": "s3", "type": "hotkey", "name": "全选",
     "params": {"keys": "ctrl+a"}},

    {"id": "s4", "type": "hotkey", "name": "粘贴",
     "params": {"keys": "ctrl+v"}},

    {"id": "s5", "type": "click", "name": "查找按钮",
     "params": {"position": {"type": "fixed", "x": 980, "y": 152}}},

    {"id": "s6", "type": "wait", "name": "等结果加载",
     "params": {"mode": "fixed", "seconds": 5}},

    {"id": "s7", "type": "find_image", "name": "检测是否可信百科页",
     "params": {"template": "kexinbaike"},
     "on_success": "skip_company"},

    {"id": "s8", "type": "find_image", "name": "检测成立年限标识位置",
     "params": {"template": "chengli_nian_xian"},
     "on_success": "click_alt", "on_failure": "click_default"},

    {"id": "click_alt", "type": "click", "name": "点备用位置",
     "params": {"position": {"type": "fixed", "x": 502, "y": 688}},
     "on_success": "wait_detail"},

    {"id": "click_default", "type": "click", "name": "点默认位置",
     "params": {"position": {"type": "fixed", "x": 521, "y": 563}}},

    {"id": "wait_detail", "type": "wait", "name": "等详情页加载",
     "params": {"mode": "fixed", "seconds": 2}},

    {"id": "close_tab", "type": "find_image", "name": "检测多标签",
     "params": {"template": "tab2"},
     "on_success": "do_close", "on_failure": "scroll_down"},

    {"id": "do_close", "type": "click", "name": "关闭前一标签",
     "params": {"position": {"type": "template", "template": "tab_close_x", "anchor": "center"}}},

    {"id": "scroll_down", "type": "scroll", "name": "向下滚动",
     "params": {"direction": "down", "amount": 700,
                "at_position": {"type": "fixed", "x": 980, "y": 152}}},

    {"id": "skip_company", "type": "log", "name": "跳过该公司",
     "params": {"message": "公司 ${item} 命中可信百科，跳过", "level": "info"}}
  ]
}
```

---

## 15. 文件结构与目录约定

- 工作流文件：`workflows/<name>.awf.json`（后缀 `.awf.json`）
- 模板图片：`templates/<group_name>/v<N>.png` + `meta.json`
- 运行状态：`.run/<workflow_name>_state.json`
- 日志：`logs/<YYYYMMDD>.log`（沿用原脚本日期分文件）

---

## 16. 开发分期

### Phase 1 — MVP（最小可用）

目标：能可视化编排并跑通线性流程（无循环、无嵌套、无录制）。

- 主窗口三栏布局
- 步骤列表（拖拽排序、禁用、删除、复制）
- 步骤参数编辑器（按 type 切换表单）
- **坐标拾取浮层（F8）**
- **区域框选浮层**
- 模板库基础 UI（增删 variant、预览）
- 基础步骤类型：`click`、`type_text`、`paste`、`hotkey`、`wait`、`scroll`、`set_variable`、`log`
- 执行引擎（顺序执行、暂停/单步、停止）
- 工作流 JSON 加载/保存
- 日志面板（实时显示，按级别过滤）

### Phase 2 — 自动化核心能力

目标：能完整复现 `collect_auto.py` 等价流程。

- `find_image` 步骤 + opencv 多尺度匹配
- 模板组 `match_strategy: first_hit / best_score`
- 数据源：CSV / Excel / JSON / inline
- 数据源过滤（可视化 + 表达式双模式）
- `loop_data` 步骤
- `if` 条件分支 + `break` / `continue`
- 变量插值
- `on_success` / `on_failure` 跳转
- `focus_window` 步骤 + 窗口选择器对话框

### Phase 3 — 调试与稳定性

- 断点（`breakpoint=True` 自动暂停）
- 单步运行
- 断点续跑（`.run/` 状态文件）
- 失败重试策略
- 运行时悬浮控制条
- 工作流校验器（递归检测、引用完整性）

### Phase 4 — 录制 + 嵌套

- 录制器（pynput 监听 + 事件聚合 + Step 草稿合成）
- 录制工具条（Pause 触发）
- 录制时插入模板/循环/变量标记
- `call_workflow` 步骤
- 子流程 input/output 映射
- 递归检测的静态校验

### Phase 5（可选）

- 多显示器支持
- 插件式扩展点（让用户/Claude 把 Excel 写入、截图归档等业务逻辑作为自定义步骤接入）
- 工作流模板/示例库
- 远程触发（HTTP 接口启动工作流）

---

## 17. 依赖清单（requirements.txt 预估）

```
PySide6>=6.6
pyautogui>=0.9.54
pyperclip>=1.8.2
opencv-python>=4.9
Pillow>=10.0
pynput>=1.7.6
simpleeval>=0.9.13
pywin32>=306
pandas>=2.0           # CSV/Excel 数据源
openpyxl>=3.1         # Excel 数据源
jsonschema>=4.20
```

---

## 18. 已敲定的关键决策（变更时请更新本节）

| 项 | 决定 |
|---|---|
| GUI 框架 | PySide6 |
| 图像匹配 | opencv-python（替代 pyautogui.locateOnScreen） |
| 多显示器 | 单屏，暂不考虑 |
| DPI 缩放 | 无缩放，不考虑 |
| 管理员权限 | 不需要 |
| 录制 | 需要，Pause 键触发暂停 + 工具条 |
| 工作流嵌套 | 需要，禁止递归（加载时静态校验） |
| 数据源格式 | CSV / Excel / JSON / inline |
| 数据源过滤 | 双模式：可视化（默认）+ 表达式（高级） |
| 模板组 | 支持，`first_hit`（默认）+ `best_score` 两种策略 |
| 录制结果合并模式 | 追加（默认）/ 插入选中 / 覆盖；录制前选择 |
| 连续输入合并阈值 | 默认 1.5s，可在 settings 修改 |
| 拾取快捷键 | F8 |
| 录制打断键 | Pause |
| 业务功能（Excel/截图） | 不在本项目范围；后续作为扩展点 |
| 工作流文件后缀 | `.awf.json` |
| 模板图片格式 | PNG |
| 平台 | 仅 Windows |

---

**文档维护**：每次设计变更或开发完成阶段都需更新对应章节，特别是第 18 节的决策表与第 16 节的分期状态。
