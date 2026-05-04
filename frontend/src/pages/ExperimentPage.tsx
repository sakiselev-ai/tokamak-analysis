import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import api from '../api/client';
import TimeSeriesChart from '../components/TimeSeriesChart';
import PredictionPanel from '../components/PredictionPanel';
import type { Experiment, TimeSeries } from '../types';

export default function ExperimentPage() {
  const { id } = useParams<{ id: string }>();
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [timeseries, setTimeseries] = useState<TimeSeries[]>([]);
  const [selectedParams, setSelectedParams] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api.get(`/experiments/${id}`),
      api.get(`/experiments/${id}/timeseries`),
    ]).then(([expRes, tsRes]) => {
      setExperiment(expRes.data);
      setTimeseries(tsRes.data);
      // Select first 4 signals by default
      setSelectedParams(tsRes.data.slice(0, 4).map((ts: TimeSeries) => ts.parameter_name));
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [id]);

  if (loading) return <p>Загрузка...</p>;
  if (!experiment) return <p>Эксперимент не найден</p>;

  const toggleParam = (name: string) => {
    setSelectedParams((prev) =>
      prev.includes(name) ? prev.filter((p) => p !== name) : [...prev, name]
    );
  };

  return (
    <div>
      <h2 style={{ marginBottom: 8 }}>
        Выстрел #{experiment.shot_id}
        <span style={{ fontSize: 14, fontWeight: 400, color: '#666', marginLeft: 12 }}>
          {experiment.source.toUpperCase()} | {experiment.status}
        </span>
      </h2>

      <div style={{ display: 'flex', gap: 20, marginTop: 16 }}>
        {/* Signal selector */}
        <div
          style={{
            width: 250,
            background: '#fff',
            padding: 16,
            borderRadius: 8,
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            maxHeight: 500,
            overflowY: 'auto',
          }}
        >
          <h4 style={{ margin: '0 0 8px' }}>Параметры ({timeseries.length})</h4>
          {timeseries.map((ts) => (
            <label
              key={ts.parameter_name}
              style={{ display: 'block', padding: '4px 0', fontSize: 13, cursor: 'pointer' }}
            >
              <input
                type="checkbox"
                checked={selectedParams.includes(ts.parameter_name)}
                onChange={() => toggleParam(ts.parameter_name)}
                style={{ marginRight: 6 }}
              />
              {ts.parameter_name}
              {ts.units && <span style={{ color: '#999' }}> ({ts.units})</span>}
            </label>
          ))}
        </div>

        {/* Chart */}
        <div style={{ flex: 1 }}>
          <TimeSeriesChart
            data={timeseries}
            selectedParams={selectedParams}
            title={`Shot #${experiment.shot_id} — Временные ряды`}
          />
          <PredictionPanel experimentId={experiment.id} />

          {/* Export */}
          <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
            <a
              href={`/api/v1/experiments/${experiment.id}/export?format=csv`}
              style={{
                padding: '8px 16px',
                background: '#3498db',
                color: '#fff',
                textDecoration: 'none',
                borderRadius: 4,
                fontSize: 14,
              }}
            >
              Экспорт CSV
            </a>
            <a
              href={`/api/v1/experiments/${experiment.id}/export?format=json`}
              style={{
                padding: '8px 16px',
                background: '#9b59b6',
                color: '#fff',
                textDecoration: 'none',
                borderRadius: 4,
                fontSize: 14,
              }}
            >
              Экспорт JSON
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
