import Plot from 'react-plotly.js';
import type { TimeSeries } from '../types';

interface Props {
  data: TimeSeries[];
  title?: string;
  selectedParams?: string[];
}

export default function TimeSeriesChart({ data, title, selectedParams }: Props) {
  const filtered = selectedParams
    ? data.filter((ts) => selectedParams.includes(ts.parameter_name))
    : data;

  if (filtered.length === 0) {
    return <p style={{ color: '#999' }}>Нет данных для отображения</p>;
  }

  const traces = filtered.map((ts) => ({
    x: ts.timestamps,
    y: ts.values,
    type: 'scatter' as const,
    mode: 'lines' as const,
    name: `${ts.parameter_name}${ts.units ? ` (${ts.units})` : ''}`,
    hovertemplate: `%{y:.4f}<br>t=%{x:.4f}s<extra>${ts.parameter_name}</extra>`,
  }));

  return (
    <div
      style={{
        background: '#fff',
        padding: 16,
        borderRadius: 8,
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
      }}
    >
      <Plot
        data={traces}
        layout={{
          title: title || 'Временные ряды параметров плазмы',
          xaxis: { title: 'Время (с)' },
          yaxis: { title: 'Значение (нормализованное)' },
          hovermode: 'x unified',
          height: 500,
          margin: { l: 60, r: 30, t: 50, b: 50 },
          legend: { orientation: 'h', y: -0.2 },
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
