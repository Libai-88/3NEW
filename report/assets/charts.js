/* Report charts - coating model optimization
   ECharts only; colors derived from CSS variables.
   Ids consumed by coating-model-optimization.html:
     chart-pca / chart-proto / chart-ceiling / chart-ext */
(function () {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var good = style.getPropertyValue('--good').trim();
  var bad = style.getPropertyValue('--bad').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var axis = { axisLine: { lineStyle: { color: rule } }, axisLabel: { color: muted }, splitLine: { lineStyle: { color: rule } } };
  var colmap = { 1: '#9aa7bd', 2: '#4cc9f0', 3: '#f4a261', 4: '#ff8fa3' };
  var grid = { left: 52, right: 24, top: 34, bottom: 44 };

  /* ---------- Fig 5-1: protocol comparison (R2, ET model) ---------- */
  var protoDom = document.getElementById('chart-proto');
  if (protoDom) {
    var proto = echarts.init(protoDom, null, { renderer: 'svg' });
    proto.setOption({
      animation: false, tooltip: { trigger: 'axis', appendToBody: true },
      legend: { top: 0, textStyle: { color: ink } },
      grid: grid,
      xAxis: Object.assign({ type: 'category', data: ['协议A\n乐观上界', '协议B\nGroupKFold', '协议C\nLeaveRegimeOut'] }, axis),
      yAxis: Object.assign({ type: 'value', name: 'R²', max: 0.6, min: -0.8 }, axis),
      series: [
        { name: 'MEK(log)', type: 'bar', data: [0.547, 0.437, -0.70], color: accent, label: { show: true, position: 'top', color: ink } },
        { name: 'T弯', type: 'bar', data: [0.481, 0.286, -0.06], color: accent2, label: { show: true, position: 'top', color: ink } }
      ]
    });
    window.addEventListener('resize', function () { proto.resize(); });
  }

  /* ---------- Fig 5-2: R2 ladder, honest vs target ---------- */
  var ceilDom = document.getElementById('chart-ceiling');
  if (ceilDom) {
    var ceil = echarts.init(ceilDom, null, { renderer: 'svg' });
    ceil.setOption({
      animation: false, tooltip: { trigger: 'axis', appendToBody: true },
      grid: grid,
      xAxis: Object.assign({ type: 'value', name: 'R²', max: 0.9, min: -0.1 }, axis),
      yAxis: Object.assign({ type: 'category', inverse: true, data: ['目标 R²≥0.85', '协议C 跨工艺迁移', '协议B GroupKFold(诚实)', '协议A 随机CV(上界)'] }, axis),
      series: [{
        type: 'bar', barWidth: '55%', label: { show: true, position: 'right', color: ink },
        itemStyle: { color: function (p) { return [accent, bad, accent2, good][p.dataIndex]; } },
        data: [0.85, -0.70, 0.437, 0.547]
      }]
    });
    window.addEventListener('resize', function () { ceil.resize(); });
  }

  /* ---------- Fig 6-1: PolySol external generalization ---------- */
  var extDom = document.getElementById('chart-ext');
  if (extDom) {
    var ext = echarts.init(extDom, null, { renderer: 'svg' });
    ext.setOption({
      animation: false, tooltip: { trigger: 'axis', appendToBody: true },
      legend: { top: 0, textStyle: { color: ink } },
      grid: grid,
      xAxis: Object.assign({ type: 'category', data: ['逻辑回归', '随机森林', 'ExtraTrees'] }, axis),
      yAxis: Object.assign({ type: 'value', name: '准确率', max: 0.9, min: 0.7 }, axis),
      series: [
        { name: '随机CV acc', type: 'bar', data: [0.790, 0.820, 0.800], color: accent },
        { name: '按聚合物 GroupKFold acc', type: 'bar', data: [0.790, 0.806, 0.802], color: accent2 }
      ]
    });
    window.addEventListener('resize', function () { ext.resize(); });
  }

  /* ---------- Fig 3-1: PCA scatter (data injected via __PCA_JSON__) ---------- */
  var pcaDom = document.getElementById('chart-pca');
  var pcaJson = window.__PCA_JSON__ || null;
  if (pcaDom && pcaJson) {
    var pts2 = pcaJson.pts2; // [x, y, grade]
    var byGrade = {};
    var series = [];
    [1, 2, 3, 4].forEach(function (g) {
      var data = pts2.filter(function (p) { return p[2] === g; })
        .map(function (p) { return [p[0], p[1]]; });
      if (data.length) {
        byGrade[g] = data;
        series.push({ name: '水煮等级 ' + g, type: 'scatter', data: data, symbolSize: 11, itemStyle: { color: colmap[g] } });
      } else {
        series.push({ name: '水煮等级 ' + g, type: 'scatter', data: [], symbolSize: 11, itemStyle: { color: colmap[g] } });
      }
    });
    var pca = echarts.init(pcaDom, null, { renderer: 'svg' });
    pca.setOption({
      animation: false, tooltip: { appendToBody: true, formatter: function (p) { return p.seriesName + '<br>PC1=' + p.value[0] + ' PC2=' + p.value[1]; } },
      legend: { top: 0, textStyle: { color: ink } },
      grid: grid,
      xAxis: Object.assign({ type: 'value', name: 'PC1（方差21.3%）' }, axis),
      yAxis: Object.assign({ type: 'value', name: 'PC2（方差15.5%）' }, axis),
      series: series
    });
    window.addEventListener('resize', function () { pca.resize(); });
  }
})();