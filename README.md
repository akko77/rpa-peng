# AutoWorkflow — Phase 2

网页自动化工作流构建器。详细设计见 `TECH_DOC.md`。

## Phase 2 新增

- ✅ **图像匹配 `find_image`**：opencv 多尺度模板匹配，支持模板组（first_hit / best_score 两种策略）
- ✅ **模板库 UI**：右栏「模板库」标签，框选屏幕区域 → 自动保存 PNG → 关联到模板组
- ✅ **数据源驱动循环**：CSV / Excel(xlsx) / JSON / 内联文本，右栏「数据源」标签配置
- ✅ **过滤器双模式**：可视化规则表 + Python 表达式（simpleeval），「试算」按钮预览过滤效果
- ✅ **控制流**：`if`（条件分支）、`loop_data`（嵌套循环）、`break`、`continue`
- ✅ **嵌套步骤树**：左栏步骤列表升级为树形，可展开 if 的 then/else、loop_data 的 body
- ✅ **`focus_window`**：按窗口标题正则匹配切换前台窗口（pywin32）
- ✅ **`wait until_image`**：等待图片出现，带超时和轮询间隔
- ✅ **位置类型 `template`**：click 等步骤可直接引用模板组，运行时找到中心点击
- ✅ **变量插值扩展**：`${found}`、`${match_pos}`、`${match_score}`、`${match_box}` 可在后续步骤使用

## Phase 1 已具备（不变）

- 主窗口三栏布局，步骤编辑表单
- 坐标拾取浮层（F8）
- 基础步骤：click / type_text / paste / hotkey / wait / scroll / set_variable / log
- 暂停 / 单步 / 停止 / 断点 / on_success / on_failure 跳转
- 工作流 JSON 加载/保存
- 日志面板（按级别过滤）
- 变量插值（`${var}` / `${item.field}`）

## Phase 3+ 待办

- ⏳ 录制器（Pause 键 + 工具条）
- ⏳ 工作流嵌套调用 `call_workflow`
- ⏳ 断点续跑（`.run/<workflow>_state.json`）
- ⏳ 失败重试策略
- ⏳ 运行时悬浮控制条
- ⏳ JSON Schema 校验
- ⏳ 业务扩展插件点（Excel/截图等）

## 环境

- Windows 10/11（64 位）
- Python 3.10+
- 无系统 DPI 缩放（设置 → 显示 → 100%）
- 不需要管理员权限

## 安装

```powershell
cd auto_workflow
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 运行

```powershell
python -m app.main
```

## 快捷键

| 键 | 行为 |
|---|---|
| **F8** | 坐标拾取浮层中：抓取当前鼠标位置 |
| **Esc** | 拾取/框选浮层：取消 |
| **F5** | 运行工作流 |
| **Shift+F5** | 停止 |
| **F6** | 暂停/继续 |
| **F9** | 切换当前步骤的断点 |
| **F10** | 单步执行 |
| Ctrl+N/O/S | 新建/打开/保存 |

## Phase 2 试跑流程

1. **创建模板**：右栏 → 模板库 → 「+ 新建组 (框选)」→ 在屏幕上框选目标元素（例如一个按钮的图标）→ 给组取名
2. **配置数据源**：右栏 → 数据源 → 勾选「启用顶层数据循环」→ 选 inline，每行写一个条目；或选 CSV/Excel 路径
3. **（可选）配置过滤器**：在数据源标签的「过滤器」区域，可视化模式添加规则，或切到「表达式」直接写 Python
4. **试算过滤**：点击「试算」预览过滤后前 5 项
5. **编排步骤**：
   - 用 `find_image` 步骤引用刚创建的模板组
   - 用 `if` 步骤判断 `${found}` 是否为真，展开 then/else 分支
   - 在 then 分支添加 `click`，position 选「模板」→ 填入模板组名 → 运行时自动点击模板中心
6. **运行**：F5

### 示例工作流

`workflows/example_phase2_collect.awf.json` — 完整复现原 `collect_auto.py` 等价流程（数据源 + find_image + if 分支 + 滚动 + 模板点击）。运行前需要在模板库里创建对应的三个模板组（`kexinbaike` / `chengli` / `trend_icon`）。

## 数据源 item 访问

| 数据源 | item 类型 | 引用方式 |
|---|---|---|
| CSV / Excel（不设 column） | dict | `${item.列名}` |
| CSV / Excel（设了 column） | scalar | `${item}` |
| JSON 数组（元素是 object） | dict | `${item.field}` |
| JSON 数组（元素是 scalar） | scalar | `${item}` |
| 内联文本 | str | `${item}` |

## 过滤器表达式语法（simpleeval 子集）

```
item.industry == "科技"
item.revenue > 1000 and "深圳" in item.address
not item.name.startswith("测试")
len(item.tags) > 0
```

可用函数：`len`、`str`、`int`、`float`、`bool`、`lower`、`upper`、`strip`。

## 已知限制

- 录制器还未实现（Phase 4）
- 工作流之间不能互相调用（call_workflow 是 Phase 4）
- 断点续跑还未实现（Phase 3）
- `failure_policy = retry` 尚未实现
