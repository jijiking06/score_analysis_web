/* 学生详情页：雷达图 + 各科成绩与班级平均对比 */
(function () {
    "use strict";

    const node = document.getElementById("student-data");
    if (!node) return;
    const view = JSON.parse(node.textContent);

    const FONT = '"PingFang SC","Microsoft YaHei","Segoe UI",system-ui,sans-serif';
    const AXIS = "#94a3b8";
    const SPLIT = "#eef2f7";
    const charts = [];

    echarts.registerTheme("score", {
        textStyle: { fontFamily: FONT },
        tooltip: { backgroundColor: "#0f172a", borderWidth: 0, textStyle: { color: "#fff", fontSize: 12.5 } },
    });

    /* ---------- 雷达图 ---------- */
    const radarItems = view.radar || [];
    if (radarItems.length >= 3) {
        const maxScore = Math.max(100, ...radarItems.map(r => Math.max(r.score, r.class_avg || 0)));
        const radarChart = echarts.init(document.getElementById("chart-radar"), "score");
        radarChart.setOption({
            tooltip: { trigger: "item" },
            legend: {
                bottom: 0, icon: "circle", itemWidth: 9, itemHeight: 9,
                textStyle: { color: "#475569", fontSize: 12.5 },
            },
            radar: {
                center: ["50%", "46%"],
                radius: "64%",
                indicator: radarItems.map(r => ({ name: r.subject, max: maxScore })),
                axisName: { color: "#475569", fontSize: 11.5 },
                splitLine: { lineStyle: { color: "#e8edf6" } },
                splitArea: { areaStyle: { color: ["#fbfcff", "#f4f7ff"] } },
                axisLine: { lineStyle: { color: "#e8edf6" } },
            },
            series: [{
                type: "radar",
                symbolSize: 6,
                data: [
                    {
                        value: radarItems.map(r => r.score),
                        name: view.student.name,
                        areaStyle: { color: "rgba(79,70,229,.22)" },
                        lineStyle: { color: "#4f46e5", width: 2 },
                        itemStyle: { color: "#4f46e5" },
                    },
                    {
                        value: radarItems.map(r => r.class_avg),
                        name: "班级平均",
                        areaStyle: { color: "rgba(14,165,233,.12)" },
                        lineStyle: { color: "#0ea5e9", width: 2, type: "dashed" },
                        itemStyle: { color: "#0ea5e9" },
                    },
                ],
            }],
        });
        charts.push(radarChart);
    }

    /* ---------- 各科对比条形图 ---------- */
    const rows = (view.subject_rows || []).slice().reverse(); // 升序，便于从下往上阅读
    if (rows.length) {
        const compareChart = echarts.init(document.getElementById("chart-compare"), "score");
        compareChart.setOption({
            tooltip: {
                trigger: "axis",
                axisPointer: { type: "shadow", shadowStyle: { color: "rgba(99,102,241,.08)" } },
            },
            legend: {
                bottom: 0, icon: "circle", itemWidth: 9, itemHeight: 9,
                textStyle: { color: "#475569", fontSize: 12.5 },
            },
            grid: { left: 130, right: 30, top: 16, bottom: 56 },
            xAxis: {
                type: "value", max: 100,
                axisLine: { lineStyle: { color: SPLIT } },
                axisTick: { show: false },
                axisLabel: { color: AXIS, fontSize: 12 },
                splitLine: { lineStyle: { color: SPLIT } },
            },
            yAxis: {
                type: "category",
                data: rows.map(r => r.subject),
                axisLine: { lineStyle: { color: SPLIT } },
                axisTick: { show: false },
                axisLabel: { color: "#334155", fontSize: 11.5 },
            },
            dataZoom: [
                { type: "inside", yAxisIndex: 0, start: 0, end: rows.length > 14 ? 55 : 100 },
                {
                    type: "slider", yAxisIndex: 0, width: 14, right: 6,
                    borderColor: "transparent", backgroundColor: "#f1f5f9",
                    fillerColor: "rgba(99,102,241,.18)", handleStyle: { color: "#4f46e5" },
                    start: 0, end: rows.length > 14 ? 55 : 100,
                },
            ],
            series: [
                {
                    name: view.student.name,
                    type: "bar",
                    barMaxWidth: 12,
                    data: rows.map(r => r.score),
                    itemStyle: { borderRadius: [0, 5, 5, 0], color: "#4f46e5" },
                },
                {
                    name: "班级平均",
                    type: "bar",
                    barMaxWidth: 12,
                    data: rows.map(r => r.class_avg),
                    itemStyle: { borderRadius: [0, 5, 5, 0], color: "#c7d2fe" },
                },
            ],
        });
        charts.push(compareChart);
    }

    window.addEventListener("resize", () => charts.forEach(c => c.resize()));
})();
