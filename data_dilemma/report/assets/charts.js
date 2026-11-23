// assets/charts.js
(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var good = style.getPropertyValue('--good').trim();

  function baseGrid() {
    return { left: 48, right: 24, top: 40, bottom: 44 };
  }
  function baseTooltip() {
    return { trigger: 'axis', appendToBody: true, backgroundColor: bg2, borderColor: rule, textStyle: { color: ink } };
  }

  // --- Chart 1: 噪声降低 → R² 上限 ---
  var c1 = echarts.init(document.getElementById('chart-noise-floor'), null, { renderer: 'svg' });
  c1.setOption({
    animation: false,
    color: [accent],
    tooltip: Object.assign(baseTooltip(), {
      formatter: function(ps) {
        var p = ps[0];
        return '噪声 std=' + p.value[0] + '<br/>R² 上限=' + p.value[1].toFixed(3);
      }
    }),
    grid: baseGrid(),
    xAxis: {
      type: 'value',
      name: '测量噪声 std',
      nameTextStyle: { color: muted },
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { color: muted },
      splitLine: { lineStyle: { color: rule } }
    },
    yAxis: {
      type: 'value',
      name: 'R² 上限',
      min: 0.7,
      max: 1.0,
      nameTextStyle: { color: muted },
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { color: muted },
      splitLine: { lineStyle: { color: rule } }
    },
    series: [{
      type: 'line',
      data: [[1.244, 0.791], [1.1, 0.836], [0.9, 0.891], [0.7, 0.934], [0.62, 0.948], [0.5, 0.966], [0.3, 0.988]],
      smooth: true,
      symbolSize: 8,
      lineStyle: { width: 3 },
      areaStyle: { color: accent + '22' },
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { color: good, type: 'dashed' },
        label: { color: good, formatter: 'R²>0.9 目标线' },
        data: [{ yAxis: 0.9 }]
      },
      markPoint: {
        symbol: 'circle',
        symbolSize: 46,
        label: { color: '#fff', fontSize: 10, formatter: '当前\n0.791' },
        data: [{ coord: [1.244, 0.791] }]
      }
    }]
  });
  window.addEventListener('resize', function() { c1.resize(); });

  // --- Chart 2: 重复测量次数 → R² 上限 ---
  var c2 = echarts.init(document.getElementById('chart-repeat'), null, { renderer: 'svg' });
  c2.setOption({
    animation: false,
    color: [accent],
    tooltip: Object.assign(baseTooltip(), {
      formatter: function(ps) {
        var p = ps[0];
        return '重复测量 ' + p.value[0] + ' 次取均值<br/>有效噪声=' + p.data.eff + '<br/>R² 上限=' + p.value[1].toFixed(3);
      }
    }),
    grid: baseGrid(),
    xAxis: {
      type: 'category',
      name: '重复测量次数 n',
      nameTextStyle: { color: muted },
      data: ['1', '2', '3', '4', '5', '8'],
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { color: muted }
    },
    yAxis: {
      type: 'value',
      name: 'R² 上限',
      min: 0.7,
      max: 1.0,
      nameTextStyle: { color: muted },
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { color: muted },
      splitLine: { lineStyle: { color: rule } }
    },
    series: [{
      type: 'line',
      data: [
        { value: 0.791, eff: 1.244 },
        { value: 0.895, eff: 0.880 },
        { value: 0.930, eff: 0.718 },
        { value: 0.948, eff: 0.622 },
        { value: 0.958, eff: 0.556 },
        { value: 0.974, eff: 0.440 }
      ],
      smooth: true,
      symbolSize: 9,
      lineStyle: { width: 3 },
      areaStyle: { color: accent + '22' },
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { color: good, type: 'dashed' },
        label: { color: good, formatter: 'R²>0.9 目标线' },
        data: [{ yAxis: 0.9 }]
      },
      label: {
        show: true,
        position: 'top',
        color: ink,
        fontSize: 11,
        formatter: function(p) { return p.value.toFixed(3); }
      }
    }]
  });
  window.addEventListener('resize', function() { c2.resize(); });
})();
