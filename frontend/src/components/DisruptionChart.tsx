import Plot from 'react-plotly.js';

interface Props {
  timestamps: number[];
  probabilities: number[];
  threshold: number;
  warningTimeMs?: number;
}

export default function DisruptionChart({ timestamps, probabilities, threshold, warningTimeMs }: Props) {
  if (timestamps.length === 0) {
    return <p style={{ color: '#999' }}>Нет данных для отображения</p>;
  }

  // Main probability trace
  const mainTrace: Plotly.Data = {
    x: timestamps,
    y: probabilities,
    type: 'scatter',
    mode: 'lines',
    name: 'Вероятность срыва',
    line: { color: '#2980b9', width: 2 },
    hovertemplate: 'p=%{y:.3f}<br>t=%{x:.4f}s<extra></extra>',
  };

  // Warning zone: probability > threshold filled in red
  const warningY = probabilities.map((p) => (p > threshold ? p : null));
  const warningTrace: Plotly.Data = {
    x: timestamps,
    y: warningY,
    type: 'scatter',
    mode: 'lines',
    name: 'Зона предупреждения',
    fill: 'tozeroy',
    fillcolor: 'rgba(231, 76, 60, 0.2)',
    line: { color: 'rgba(231, 76, 60, 0.6)', width: 0 },
    hoverinfo: 'skip',
    showlegend: true,
    connectgaps: false,
  };

  // Threshold line
  const thresholdTrace: Plotly.Data = {
    x: [timestamps[0], timestamps[timestamps.length - 1]],
    y: [threshold, threshold],
    type: 'scatter',
    mode: 'lines',
    name: `Порог (${threshold})`,
    line: { color: '#e74c3c', width: 2, dash: 'dash' },
    hoverinfo: 'skip',
  };

  const annotations: Partial<Plotly.Layout>['annotations'] = [];
  const shapes: Partial<Plotly.Layout>['shapes'] = [];

  if (warningTimeMs != null) {
    // Convert ms to seconds for the annotation position
    const warningTimeSec = warningTimeMs / 1000;
    // Find the closest timestamp to place the annotation
    const lastTimestamp = timestamps[timestamps.length - 1];
    const annotationX = lastTimestamp - warningTimeSec;

    shapes.push({
      type: 'line',
      x0: annotationX,
      x1: annotationX,
      y0: 0,
      y1: 1,
      line: { color: '#f39c12', width: 2, dash: 'dot' },
    });

    annotations.push({
      x: annotationX,
      y: 1.05,
      xref: 'x',
      yref: 'y',
      text: `Предупреждение: ${warningTimeMs.toFixed(0)} мс`,
      showarrow: true,
      arrowhead: 2,
      arrowcolor: '#f39c12',
      ax: 0,
      ay: -30,
      font: { color: '#f39c12', size: 12 },
    });
  }

  return (
    <div
      style={{
        background: '#fff',
        padding: 16,
        borderRadius: 8,
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
        marginTop: 16,
      }}
    >
      <Plot
        data={[warningTrace, mainTrace, thresholdTrace]}
        layout={{
          title: 'Вероятность срыва плазмы',
          xaxis: { title: 'Время (с)' },
          yaxis: { title: 'Вероятность', range: [0, 1.1] },
          hovermode: 'x unified',
          height: 400,
          margin: { l: 60, r: 30, t: 50, b: 50 },
          legend: { orientation: 'h', y: -0.2 },
          annotations,
          shapes,
        }}
        config={{
          responsive: true,
          displayModeBar: true,
          modeBarButtonsToRemove: ['lasso2d', 'select2d'],
        }}
        style={{ width: '100%' }}
      />
    </div>
  );
}
