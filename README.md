# 学生综测成绩分析系统

基于 **Flask + SQLite + Pandas + ECharts** 的 Web 成绩分析平台：上传一份 Excel / CSV 成绩单，
自动生成 KPI 指标、交互式图表、班级排名与个人成绩诊断。

## 功能

**数据总览**

- KPI 卡片：学生总数、平均分、最高/最低分、及格率、优秀率
- 分数段占比环形图（优秀 / 良好 / 中等 / 及格 / 不及格）
- 综测成绩分布直方图（10 分一档）
- 综测排名前十横向柱状图（点击可跳转学生详情）
- 各科目平均分柱状图（可横向缩放查看全部课程）
- 成绩总表：支持姓名 / 学号搜索、分页浏览

**学生查询与个人详情**

- 姓名或学号模糊查询
- 个人成绩首页：综测总分、班级排名、超过同学的百分比
- 核心科目雷达图（本人 vs 班级平均）
- 各科成绩与班级平均对比条形图
- 单科成绩明细表（成绩、班级平均、与平均差、等级）
- 最强 / 最弱科目、高于班级平均的科目数

**数据管理**

- 上传 `.xlsx` / `.xls` / `.csv`，自动识别学号、姓名、科目与综测列
- 支持「覆盖导入」与「追加导入」两种模式
- 一键导出 CSV（含 BOM，Excel 打开不乱码）
- 一键清空数据

## 技术栈

| 层次 | 技术 |
| --- | --- |
| 后端 | Python 3、Flask |
| 存储 | SQLite |
| 数据处理 | Pandas、openpyxl |
| 前端 | 原生 HTML / CSS / JavaScript |
| 可视化 | ECharts（已离线内置于 `static/vendor/`） |

## 快速开始

```bash
pip install -r requirements.txt
python app.py
```

浏览器打开 <http://127.0.0.1:5000>。

## 成绩单格式

第一行为表头，至少包含「学号」「姓名」两列，最后一列建议为「综测」：

| 学号 | 姓名 | 高等数学 | 大学英语 | 程序设计 | 综测 |
| --- | --- | --- | --- | --- | --- |
| 20245101303 | 张三 | 92 | 88 | 95 | 91.5 |

列名识别规则：

- 含「学号 / 学籍号 / 编号」的列 → 学号
- 含「姓名」的列 → 姓名
- 含「综测 / 总分 / 综合成绩」的列 → 综测（找不到时取最后一列）
- 其余非派生列（学分、绩点、选修课等会自动排除）→ 单科成绩

## 目录结构

```
score_analysis_web/
├── app.py                     # Flask 后端：路由、解析、统计
├── score.db                   # SQLite 数据库
├── requirements.txt
├── static/
│   ├── css/style.css          # 全站样式
│   ├── js/dashboard.js        # 数据总览图表与表格
│   ├── js/student.js          # 学生详情图表
│   └── vendor/echarts.min.js  # 离线 ECharts
└── templates/
    ├── base.html              # 公共布局与导航
    ├── index.html             # 数据总览
    ├── search.html            # 学生查询
    ├── student.html           # 学生详情
    └── upload.html            # 上传数据
```

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/` | 数据总览 |
| GET | `/search?kw=` | 学生查询 |
| GET | `/student/<stu_id>` | 学生详情 |
| GET / POST | `/upload` | 上传成绩单 |
| GET | `/export` | 导出 CSV |
| POST | `/clear` | 清空数据 |
| GET | `/api/dashboard` | 仪表盘 JSON 数据 |
