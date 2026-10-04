/* 数据总览页：ECharts 图表 + 可搜索/分页的排名表 */
(function () {
    "use strict";

    const node = document.getElementById("dash-data");
    if (!node) return;
    const data = JSON.parse(node.textContent);

    const FONT = '"PingFang SC","Microsoft YaHei","Segoe UI",system-ui,sans-serif';
    const AXIS = "#94a3b8";
    const SPLIT = "#eef2f7";
    const charts = [];

    echarts.registerTheme("score", {
        textStyle: { fontFamily: FONT },
        color: ["#6366f1", "#0ea5e9", "#22c55e", "#f59e0b", "#a855f7", "#ef4444"],
        tooltip: { backgroundColor: "#0f172a", borderWidth: 0, textStyle: { color: "#fff", fontSize: 12.5 } },
    });

    function make(id, option) {
        const el = document.getElementById(id);
        if (!el) return null;
        const chart = echarts.init(el, "score");
        chart.setOption(option);
        charts.push(chart);
        return chart;
    }

    function axisBase() {
        return {
            axisLine: { lineStyle: { color: SPLIT } },
            axisTick: { show: false },
            axisLabel: { color: AXIS, fontSize: 12 },
            splitLine: { lineStyle: { color: SPLIT } },
        };
    }

    const baseTooltip = {
        trigger: "axis",
        axisPointer: { type: "shadow", shadowStyle: { color: "rgba(99,102,241,.08)" } },
    };

    /* ---------- 1. 分数段占比 ---------- */
    make("chart-pie", {
        tooltip: { trigger: "item", formatter: "{b}：{c} 人（{d}%）" },
        legend: { bottom: 0, icon: "circle", itemWidth: 9, itemHeight: 9, textStyle: { color: "#475569", fontSize: 12.5 } },
        series: [{
            type: "pie",
            radius: ["48%", "72%"],
            center: ["50%", "45%"],
            avoidLabelOverlap: true,
            itemStyle: { borderColor: "#fff", borderWidth: 3, borderRadius: 6 },
            label: { formatter: "{d}%", color: "#334155", fontSize: 12.5, fontWeight: 600 },
            labelLine: { length: 8, length2: 8 },
            data: data.bands.map(b => ({
                name: b.name,
                value: b.value,
                itemStyle: { color: b.color },
            })),
        }],
    });

    /* ---------- 2. 成绩分布直方图 ---------- */
    make("chart-hist", {
        tooltip: Object.assign({}, baseTooltip, { formatter: "{b} 分：{c} 人" }),
        grid: { left: 46, right: 20, top: 24, bottom: 34 },
        xAxis: Object.assign({ type: "category", data: data.histogram.bins }, axisBase(), {
            splitLine: { show: false },
        }),
        yAxis: Object.assign({ type: "value", name: "人数", nameTextStyle: { color: AXIS } }, axisBase()),
        series: [{
            type: "bar",
            barMaxWidth: 44,
            data: data.histogram.counts,
            itemStyle: {
                borderRadius: [6, 6, 0, 0],
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: "#818cf8" },
                    { offset: 1, color: "#4f46e5" },
                ]),
            },
            label: { show: true, position: "top", color: "#475569", fontSize: 12 },
        }],
    });

    /* ---------- 3. 综测前十名 ---------- */
    const top = data.top;
    const topChart = make("chart-top", {
        tooltip: Object.assign({}, baseTooltip, {
            formatter: p => `${top[p.dataIndex].name}（${top[p.dataIndex].stu_id}）<br/>综测：${p.value} 分`,
        }),
        grid: { left: 110, right: 60, top: 16, bottom: 20 },
        xAxis: Object.assign({ type: "value", max: 100 }, axisBase()),
        yAxis: Object.assign({
            type: "category",
            inverse: true,
            data: top.map(t => t.name),
            axisLine: { lineStyle: { color: SPLIT } },
            axisTick: { show: false },
            axisLabel: { color: "#334155", fontSize: 13, fontWeight: 600 },
        }, { splitLine: { show: false } }),
        series: [{
            type: "bar",
            barMaxWidth: 22,
            data: top.map(t => t.zongce),
            itemStyle: {
                borderRadius: [0, 8, 8, 0],
                color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                    { offset: 0, color: "#a5b4fc" },
                    { offset: 1, color: "#4f46e5" },
                ]),
            },
            label: { show: true, position: "right", formatter: "{c}", color: "#4f46e5", fontWeight: 600, fontSize: 12.5 },
        }],
    });
    if (topChart) {
        topChart.getZr().setCursorStyle("pointer");
        topChart.on("click", p => {
            const stu = top[p.dataIndex];
            if (stu) window.location.href = "/student/" + encodeURIComponent(stu.stu_id);
        });
    }

    /* ---------- 4. 各科目平均分 ---------- */
    const subjects = data.subjects;
    make("chart-subject", {
        tooltip: Object.assign({}, baseTooltip, {
            formatter: p => {
                const s = subjects[p.dataIndex];
                return `${s.subject}<br/>平均分：${s.avg}<br/>及格率：${s.pass_rate}%`
                    + `<br/>最高 ${s.max} / 最低 ${s.min}（${s.count} 人）`;
            },
        }),
        grid: { left: 50, right: 24, top: 24, bottom: 76 },
        xAxis: Object.assign({
            type: "category",
            data: subjects.map(s => s.subject),
            axisLabel: { color: AXIS, fontSize: 11, interval: 0, rotate: 40 },
        }, { axisLine: { lineStyle: { color: SPLIT } }, axisTick: { show: false }, splitLine: { show: false } }),
        yAxis: Object.assign({ type: "value", max: 100, name: "平均分", nameTextStyle: { color: AXIS } }, axisBase()),
        dataZoom: [
            { type: "inside", start: 0, end: subjects.length > 18 ? 45 : 100 },
            {
                type: "slider", height: 16, bottom: 12,
                borderColor: "transparent",
                backgroundColor: "#f1f5f9",
                fillerColor: "rgba(99,102,241,.18)",
                handleStyle: { color: "#4f46e5" },
                start: 0,
                end: subjects.length > 18 ? 45 : 100,
            },
        ],
        series: [{
            type: "bar",
            barMaxWidth: 26,
            data: subjects.map(s => ({
                value: s.avg,
                itemStyle: {
                    borderRadius: [6, 6, 0, 0],
                    color: s.avg >= 85 ? "#22c55e" : s.avg >= 70 ? "#6366f1" : s.avg >= 60 ? "#f59e0b" : "#ef4444",
                },
            })),
        }],
    });

    /* ---------- 排名表：搜索 + 分页 ---------- */
    const PAGE_SIZE = 12;
    const rows = data.ranking;
    const tbody = document.querySelector("#rank-table tbody");
    const info = document.getElementById("table-info");
    const searchInput = document.getElementById("table-search");
    const prevBtn = document.getElementById("page-prev");
    const nextBtn = document.getElementById("page-next");

    let filtered = rows.slice();
    let page = 1;

    function medal(rank) {
        return rank === 1 ? "🥇" : rank === 2 ? "🥈" : rank === 3 ? "🥉" : rank;
    }

    function fmt(v) {
        return (v === null || v === undefined) ? "—" : Number(v).toFixed(2);
    }

    function render() {
        const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
        page = Math.min(page, pages);
        const slice = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

        tbody.innerHTML = slice.map(s => {
            const rankCls = s.rank <= 3 ? "rank-medal" : "";
            return `<tr>
                <td class="center rank-cell ${rankCls}">${medal(s.rank)}</td>
                <td>${escapeHtml(s.stu_id)}</td>
                <td><a class="name-link" href="/student/${encodeURIComponent(s.stu_id)}">${escapeHtml(s.name)}</a></td>
                <td class="num score-pill">${fmt(s.zongce)}</td>
                <td class="center"><span class="badge" style="--c:${s.grade_color}">${s.grade}</span></td>
                <td class="center"><a class="btn ghost small" href="/student/${encodeURIComponent(s.stu_id)}">查看</a></td>
            </tr>`;
        }).join("") || `<tr><td colspan="6"><div class="empty">没有匹配的学生</div></td></tr>`;

        info.textContent = `共 ${filtered.length} 人 · 第 ${page}/${pages} 页`;
        prevBtn.disabled = page <= 1;
        nextBtn.disabled = page >= pages;
        prevBtn.style.opacity = page <= 1 ? .5 : 1;
        nextBtn.style.opacity = page >= pages ? .5 : 1;
    }

    function escapeHtml(text) {
        return String(text).replace(/[&<>"']/g, c => (
            { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
        ));
    }

    if (searchInput) {
        searchInput.addEventListener("input", () => {
            const kw = searchInput.value.trim().toLowerCase();
            filtered = !kw ? rows.slice()
                : rows.filter(s => s.name.toLowerCase().includes(kw) || s.stu_id.toLowerCase().includes(kw));
            page = 1;
            render();
        });
    }
    if (prevBtn) prevBtn.addEventListener("click", () => { page -= 1; render(); });
    if (nextBtn) nextBtn.addEventListener("click", () => { page += 1; render(); });

    render();

    window.addEventListener("resize", () => charts.forEach(c => c.resize()));
})();
