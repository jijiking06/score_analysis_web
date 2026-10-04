# -*- coding: utf-8 -*-
"""学生综测成绩分析系统 —— Flask 后端。

功能一览：
    * Excel / CSV 成绩单上传解析（自动识别学号、姓名、科目、综测列）
    * 数据总览仪表盘：KPI 指标 + 交互式图表（ECharts）
    * 学生成绩查询 / 学生个人成绩详情（雷达图 + 与班级均值对比）
    * 成绩表导出 CSV、一键清空数据
"""
from __future__ import annotations

import io
import json
import math
import os
import sqlite3
from collections import defaultdict
from datetime import datetime

import pandas as pd
from flask import (Flask, Response, flash, jsonify, redirect, render_template,
                   request, url_for)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "score.db")

app = Flask(__name__)
app.config.update(
    SECRET_KEY="student-score-analysis-secret-key",
    MAX_CONTENT_LENGTH=32 * 1024 * 1024,  # 上传文件最大 32MB
)

# --------------------------------------------------------------------------- #
# 分数段与等级
# --------------------------------------------------------------------------- #
# (名称, 下限(含), 上限(不含), 颜色)
GRADE_BANDS = [
    ("优秀", 90, float("inf"), "#22c55e"),
    ("良好", 80, 90, "#3b82f6"),
    ("中等", 70, 80, "#f59e0b"),
    ("及格", 60, 70, "#a855f7"),
    ("不及格", float("-inf"), 60, "#ef4444"),
]


def grade_of(score):
    """根据综测分数返回 (等级名, 颜色)。"""
    if score is None:
        return "未知", "#94a3b8"
    for name, low, high, color in GRADE_BANDS:
        if low <= score < high:
            return name, color
    return "未知", "#94a3b8"


PASS_LINE = 60       # 及格线
EXCELLENT_LINE = 90  # 优秀线


# --------------------------------------------------------------------------- #
# 数据库
# --------------------------------------------------------------------------- #
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS student_score (
                stu_id     TEXT PRIMARY KEY,
                name       TEXT,
                zongce     REAL,
                data_json  TEXT
            )
            """
        )
        # 兼容旧库：补齐后加的字段
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(student_score)")}
        for col, ddl in (("extra_json", "TEXT"),
                         ("subject_count", "INTEGER"),
                         ("updated_at", "TEXT")):
            if col not in existing:
                conn.execute(f"ALTER TABLE student_score ADD COLUMN {col} {ddl}")

        conn.execute(
            "CREATE TABLE IF NOT EXISTS dataset_meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        conn.commit()


def set_meta(**kwargs):
    with get_conn() as conn:
        for key, value in kwargs.items():
            conn.execute(
                "INSERT OR REPLACE INTO dataset_meta (key, value) VALUES (?, ?)",
                (key, str(value)),
            )
        conn.commit()


def get_meta(key, default=""):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM dataset_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


# --------------------------------------------------------------------------- #
# 解析工具
# --------------------------------------------------------------------------- #
def to_float(value):
    """安全地把单元格转成 float，无法转换时返回 None。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        num = float(value)
        return None if math.isnan(num) or math.isinf(num) else num
    text = str(value).strip()
    if text in {"", "-", "--", "—", "/", "None", "nan", "NaN", "NULL", "null"}:
        return None
    text = text.replace("分", "").strip()
    try:
        num = float(text)
    except ValueError:
        return None
    return None if math.isnan(num) or math.isinf(num) else num


def clean_id(value):
    """清洗学号：去掉 Excel 读出来的 ".0" 尾巴。"""
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        if value.is_integer():
            return str(int(value))
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def _loads(raw):
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


# 用于识别列的关键字
ID_KEYS = ("学号", "学籍号", "考号", "考生号", "编号", "id")
NAME_KEYS = ("姓名", "名字", "学生姓名")
ZONGCE_KEYS = ("综测", "综合测评", "综合成绩", "总成绩", "总分")
# 这些列属于“派生指标”，不计入单科成绩
DERIVED_KEYWORDS = (
    "综测", "总分", "总成绩", "综合成绩", "综合测评",
    "不带选修", "选修课", "带选修", "选修成绩", "必修成绩", "限选成绩",
    "学分", "绩点", "扣分", "排名", "名次", "平均分",
)


def detect_columns(columns):
    """从表头中推断出学号列、姓名列、综测列的下标。"""
    normalized = [str(c).strip() for c in columns]
    lower = [c.lower() for c in normalized]

    def first_match(keys, use_lower=False):
        source = lower if use_lower else normalized
        for idx, col in enumerate(source):
            for key in keys:
                if key in col:
                    return idx
        return None

    id_idx = first_match(ID_KEYS, use_lower=True)
    name_idx = first_match(NAME_KEYS)
    zongce_idx = first_match(ZONGCE_KEYS)
    if zongce_idx is None:
        zongce_idx = len(normalized) - 1  # 兜底：最后一列当作综测

    if id_idx is None:
        id_idx = 0
    if name_idx is None:
        name_idx = 1 if len(normalized) > 1 else 0
    return id_idx, name_idx, zongce_idx


def is_derived(header):
    return any(key in header for key in DERIVED_KEYWORDS)


def import_records(df, source_name, mode="replace"):
    """把 DataFrame 写进数据库，返回导入统计信息。"""
    df = df.dropna(how="all")
    if df.empty:
        raise ValueError("文件中没有可用的数据行")

    columns = [str(c).strip() for c in df.columns]
    df.columns = columns
    id_idx, name_idx, zongce_idx = detect_columns(columns)

    id_col, name_col, zongce_col = columns[id_idx], columns[name_idx], columns[zongce_idx]
    subject_cols = [
        c for i, c in enumerate(columns)
        if i not in (id_idx, name_idx, zongce_idx) and not is_derived(c)
    ]
    if not subject_cols:  # 极端情况：把所有非主列都当科目
        subject_cols = [c for i, c in enumerate(columns)
                        if i not in (id_idx, name_idx, zongce_idx)]
    extra_cols = [
        c for i, c in enumerate(columns)
        if i not in (id_idx, name_idx, zongce_idx) and c not in subject_cols
    ]

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows, skipped = [], 0
    for seq, (_, row) in enumerate(df.iterrows(), start=1):
        name = str(row[name_col]).strip() if pd.notna(row[name_col]) else ""
        if name == "" or name.lower() == "nan":
            skipped += 1
            continue
        sid = clean_id(row[id_col])
        if sid == "":  # 学号缺失时用姓名+序号兜底，避免主键冲突
            sid = f"{name}-{seq}"

        subjects = {}
        for col in subject_cols:
            val = to_float(row[col])
            if val is not None:
                subjects[col] = val
        extra = {}
        for col in extra_cols:
            val = to_float(row[col])
            if val is not None:
                extra[col] = val

        rows.append(
            (sid, name, to_float(row[zongce_col]),
             json.dumps(subjects, ensure_ascii=False),
             json.dumps(extra, ensure_ascii=False),
             len(subjects), now)
        )

    if not rows:
        raise ValueError("未解析到有效学生记录（请检查表头是否包含“姓名”）")

    with get_conn() as conn:
        if mode == "replace":
            conn.execute("DELETE FROM student_score")
        conn.executemany(
            """INSERT OR REPLACE INTO student_score
               (stu_id, name, zongce, data_json, extra_json, subject_count, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.commit()

    set_meta(source_file=source_name, updated_at=now,
             subject_count=len(subject_cols), last_import=len(rows))

    return {
        "count": len(rows),
        "skipped": skipped,
        "subjects": len(subject_cols),
        "subject_names": subject_cols,
        "extra_names": extra_cols,
        "source": source_name,
        "mode": mode,
    }


# --------------------------------------------------------------------------- #
# 数据读取与统计
# --------------------------------------------------------------------------- #
def load_students():
    """读取全部学生并按综测分降序排名。"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT stu_id, name, zongce, data_json, extra_json FROM student_score"
        ).fetchall()

    students = []
    for row in rows:
        # 旧版本把所有列都当成科目存进 data_json，这里统一把派生指标分离出来
        subjects, derived = {}, {}
        for key, value in _loads(row["data_json"]).items():
            (derived if is_derived(key) else subjects)[key] = value
        derived.update(_loads(row["extra_json"]))
        students.append({
            "stu_id": clean_id(row["stu_id"]),
            "name": row["name"] or "",
            "zongce": row["zongce"],
            "subjects": subjects,
            "extra": derived,
        })

    students.sort(key=lambda s: (s["zongce"] is None, -(s["zongce"] or 0.0)))
    for rank, stu in enumerate(students, start=1):
        stu["rank"] = rank
        stu["grade"], stu["grade_color"] = grade_of(stu["zongce"])
    return students


def subject_statistics(students):
    """统计每门课程：人数、均分、最高、最低、及格率。"""
    buckets = defaultdict(list)
    for stu in students:
        for subject, score in stu["subjects"].items():
            if score is not None:
                buckets[subject].append(score)

    total = max(len(students), 1)
    stats = []
    for subject, values in buckets.items():
        series = pd.Series(values, dtype="float64")
        stats.append({
            "subject": subject,
            "count": len(values),
            "coverage": round(len(values) / total * 100, 1),
            "avg": round(float(series.mean()), 2),
            "max": round(float(series.max()), 2),
            "min": round(float(series.min()), 2),
            "pass_rate": round(float((series >= PASS_LINE).mean() * 100), 1),
            "std": round(float(series.std(ddof=0)), 2),
        })
    stats.sort(key=lambda s: s["avg"])
    return stats


def build_dashboard():
    """汇总首页仪表盘需要的所有数据。"""
    students = load_students()
    scores = [s["zongce"] for s in students if s["zongce"] is not None]
    subjects = subject_statistics(students)

    dash = {
        "count": len(students),
        "source": get_meta("source_file", ""),
        "updated_at": get_meta("updated_at", ""),
        "subject_count": len(subjects),
        "subjects": subjects,
        "ranking": students,
        "has_data": bool(scores),
        "pass_line": PASS_LINE,
        "excellent_line": EXCELLENT_LINE,
    }
    if not scores:
        dash.update(avg=None, max=None, min=None, median=None, std=None,
                    pass_rate=None, excellent_rate=None, bands=[],
                    histogram={"bins": [], "counts": []}, top=[])
        return dash

    series = pd.Series(scores, dtype="float64")
    dash.update(
        avg=round(float(series.mean()), 2),
        max=round(float(series.max()), 2),
        min=round(float(series.min()), 2),
        median=round(float(series.median()), 2),
        std=round(float(series.std(ddof=0)), 2),
        pass_rate=round(float((series >= PASS_LINE).mean() * 100), 1),
        excellent_rate=round(float((series >= EXCELLENT_LINE).mean() * 100), 1),
    )

    # 分数段分布
    bands = []
    for name, low, high, color in GRADE_BANDS:
        n = int(sum(1 for v in scores if low <= v < high))
        bands.append({"name": name, "value": n, "color": color,
                      "percent": round(n / len(scores) * 100, 1)})
    dash["bands"] = bands

    # 直方图（10 分一档）
    start = int(math.floor(min(scores) / 10) * 10)
    stop = int(math.ceil(max(scores) / 10) * 10)
    bins, counts, edge = [], [], start
    while edge < stop:
        bins.append(f"{edge}-{edge + 10}")
        counts.append(int(sum(1 for v in scores if edge <= v < edge + 10)))
        edge += 10
    dash["histogram"] = {"bins": bins, "counts": counts}

    # 前十名
    dash["top"] = [
        {"rank": s["rank"], "name": s["name"], "stu_id": s["stu_id"], "zongce": s["zongce"]}
        for s in students[:10]
    ]
    return dash


def build_student_view(stu_id):
    """构造学生详情页所需数据。"""
    students = load_students()
    target = next((s for s in students if s["stu_id"] == clean_id(stu_id)), None)
    if target is None:
        return None

    scores = [s["zongce"] for s in students if s["zongce"] is not None]
    class_avg = round(float(pd.Series(scores).mean()), 2) if scores else None

    stats = {item["subject"]: item for item in subject_statistics(students)}
    subject_rows = []
    for subject, score in sorted(target["subjects"].items(), key=lambda kv: -(kv[1] or 0)):
        info = stats.get(subject, {})
        subject_rows.append({
            "subject": subject,
            "score": score,
            "class_avg": info.get("avg"),
            "diff": round(score - info["avg"], 2) if info.get("avg") is not None else None,
            "grade": grade_of(score)[0],
        })

    # 雷达图：取覆盖率最高的前 8 门课
    top_subjects = [s["subject"] for s in
                    sorted(stats.values(), key=lambda x: (-x["coverage"], x["avg"]))[:8]]
    radar = [
        {"subject": subject,
         "score": target["subjects"][subject],
         "class_avg": stats[subject]["avg"]}
        for subject in top_subjects if subject in target["subjects"]
    ]

    better = sum(1 for r in subject_rows if r["diff"] is not None and r["diff"] > 0)
    compared = sum(1 for r in subject_rows if r["diff"] is not None)

    return {
        "student": target,
        "class_avg": class_avg,
        "class_size": len(students),
        "percentile": round((1 - (target["rank"] - 1) / len(students)) * 100, 1) if students else None,
        "subject_rows": subject_rows,
        "radar": radar,
        "above_avg_count": better,
        "compared_count": compared,
        "best": subject_rows[0] if subject_rows else None,
        "worst": subject_rows[-1] if subject_rows else None,
    }


# --------------------------------------------------------------------------- #
# 路由
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    return render_template("index.html", dash=build_dashboard())


def _read_upload(file_storage):
    """把上传的文件读取为 DataFrame。"""
    filename = file_storage.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    raw = file_storage.read()
    if ext == ".csv":
        text = None
        for encoding in ("utf-8-sig", "gbk", "utf-8"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ValueError("无法识别 CSV 文件编码，请另存为 UTF-8 或 GBK")
        return pd.read_csv(io.StringIO(text), dtype=str), ext
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(io.BytesIO(raw), sheet_name=0), ext
    raise ValueError("仅支持 .xlsx / .xls / .csv 格式的文件")


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename:
            flash("请先选择要上传的成绩文件", "error")
            return redirect(url_for("upload"))

        mode = "append" if request.form.get("mode") == "append" else "replace"
        try:
            df, _ = _read_upload(file)
            info = import_records(df, file.filename, mode=mode)
        except Exception as exc:  # noqa: BLE001 - 错误信息直接展示给用户
            flash(f"上传失败：{exc}", "error")
            return redirect(url_for("upload"))

        action = "追加导入" if mode == "append" else "覆盖导入"
        message = f"{action}成功：{info['count']} 名学生、{info['subjects']} 门课程"
        if info["skipped"]:
            message += f"（跳过 {info['skipped']} 行空记录）"
        flash(message, "success")
        return redirect(url_for("index"))

    return render_template(
        "upload.html",
        source=get_meta("source_file", ""),
        updated_at=get_meta("updated_at", ""),
        student_total=len(load_students()),
    )


@app.route("/search")
def search():
    keyword = request.args.get("kw", "").strip()
    results = []
    if keyword:
        lowered = keyword.lower()
        results = [stu for stu in load_students()
                   if lowered in stu["name"].lower() or lowered in stu["stu_id"].lower()]
    return render_template("search.html", keyword=keyword, results=results,
                           searched=bool(keyword))


@app.route("/student/<stu_id>")
def student_detail(stu_id):
    view = build_student_view(stu_id)
    if view is None:
        flash(f"未找到学号为 {stu_id} 的学生", "error")
        return redirect(url_for("search"))
    return render_template("student.html", view=view)


@app.route("/export")
def export_csv():
    students = load_students()
    if not students:
        flash("暂无可导出的数据", "error")
        return redirect(url_for("index"))

    subject_columns = []
    for stu in students:
        for subject in stu["subjects"]:
            if subject not in subject_columns:
                subject_columns.append(subject)

    records = []
    for stu in students:
        row = {"排名": stu["rank"], "学号": stu["stu_id"], "姓名": stu["name"],
               "综测": stu["zongce"], "等级": stu["grade"]}
        for subject in subject_columns:
            row[subject] = stu["subjects"].get(subject, "")
        records.append(row)

    csv_text = pd.DataFrame(records).to_csv(index=False)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return Response(
        "\ufeff" + csv_text,  # BOM，保证 Excel 打开不乱码
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=score_export_{stamp}.csv"},
    )


@app.route("/clear", methods=["POST"])
def clear_data():
    with get_conn() as conn:
        conn.execute("DELETE FROM student_score")
        conn.commit()
    set_meta(source_file="", updated_at="", last_import=0)
    flash("已清空全部成绩数据", "success")
    return redirect(url_for("index"))


@app.route("/api/dashboard")
def api_dashboard():
    """返回仪表盘数据的 JSON 接口。"""
    return jsonify(build_dashboard())


@app.errorhandler(413)
def too_large(_):
    flash("文件过大，请上传 32MB 以内的文件", "error")
    return redirect(url_for("upload"))


init_db()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
