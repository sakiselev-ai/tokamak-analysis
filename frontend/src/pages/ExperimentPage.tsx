import { useEffect, useState, useMemo, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import api from '../api/client';
import TimeSeriesChart from '../components/TimeSeriesChart';
import PredictionPanel from '../components/PredictionPanel';
import DisruptionChart from '../components/DisruptionChart';
import RecommendationPanel from '../components/RecommendationPanel';
import ExportButton from '../components/ExportButton';
import type { Experiment, TimeSeries, Recommendation, DisruptionResult } from '../types';

export default function ExperimentPage() {
  const { id } = useParams<{ id: string }>();
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [timeseries, setTimeseries] = useState<TimeSeries[]>([]);
  const [selectedParams, setSelectedParams] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [disruptionResult, setDisruptionResult] = useState<DisruptionResult | null>(null);

  const handleDisruptionResult = useCallback((result: DisruptionResult) => {
    setDisruptionResult(result);
  }, []);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api.get(`/experiments/${id}`),
      api.get(`/experiments/${id}/timeseries`),
    ])
      .then(([expRes, tsRes]) => {
        setExperiment(expRes.data);
        setTimeseries(tsRes.data);
        setSelectedParams(
          tsRes.data.slice(0, 4).map((ts: TimeSeries) => ts.parameter_name)
        );
        setLoading(false);
        // Fetch recommendations if available
        api.get(`/experiments/${id}/recommendations`)
          .then((recRes) => setRecommendations(recRes.data))
          .catch(() => {});
      })
      .catch(() => setLoading(false));
  }, [id]);

  const filteredSignals = useMemo(() => {
    if (!search.trim()) return timeseries;
    const q = search.toLowerCase();
    return timeseries.filter(
      (ts) =>
        ts.parameter_name.toLowerCase().includes(q) ||
        (ts.units && ts.units.toLowerCase().includes(q)) ||
        (ts.description && ts.description.toLowerCase().includes(q))
    );
  }, [timeseries, search]);

  if (loading) {
    return (
      <div className="loading-overlay">
        <span className="spinner spinner-lg" />
        Загрузка эксперимента...
      </div>
    );
  }

  if (!experiment) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">{'\u2717'}</div>
        <div className="empty-state-text">Эксперимент не найден</div>
      </div>
    );
  }

  const toggleParam = (name: string) => {
    setSelectedParams((prev) =>
      prev.includes(name) ? prev.filter((p) => p !== name) : [...prev, name]
    );
  };

  const selectAll = () => {
    setSelectedParams(filteredSignals.map((ts) => ts.parameter_name));
  };

  const deselectAll = () => {
    setSelectedParams([]);
  };

  const statusCls =
    experiment.status === 'preprocessed'
      ? 'badge-success'
      : experiment.status === 'error'
      ? 'badge-danger'
      : 'badge-warning';

  return (
    <div>
      <div className="flex-between mb-lg flex-wrap gap-sm">
        <div>
          <h2>
            Выстрел #{experiment.shot_id}
          </h2>
          <div className="flex items-center gap-sm mt-xs">
            <span className="badge badge-info">{experiment.source.toUpperCase()}</span>
            <span className={`badge ${statusCls}`}>{experiment.status}</span>
            <span className="text-sm text-muted">
              {new Date(experiment.loaded_at).toLocaleString('ru')}
            </span>
          </div>
        </div>
      </div>

      <div className="experiment-layout">
        {/* Signal Selector Sidebar */}
        <div className="signal-sidebar">
          <div className="card">
            <h4 className="mb-sm">
              Параметры
              <span className="text-muted text-sm" style={{ fontWeight: 400, marginLeft: 6 }}>
                ({timeseries.length})
              </span>
            </h4>

            <div className="signal-search">
              <input
                type="text"
                className="form-input"
                placeholder="Поиск сигналов..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

            <div className="flex gap-sm mb-sm">
              <button className="btn btn-ghost btn-sm" onClick={selectAll}>
                Все
              </button>
              <button className="btn btn-ghost btn-sm" onClick={deselectAll}>
                Сбросить
              </button>
              <span className="text-xs text-muted" style={{ marginLeft: 'auto', alignSelf: 'center' }}>
                {selectedParams.length} выбрано
              </span>
            </div>

            <div className="signal-list">
              {filteredSignals.length === 0 ? (
                <div className="text-sm text-muted p-sm">Сигналы не найдены</div>
              ) : (
                filteredSignals.map((ts) => (
                  <label key={ts.parameter_name}>
                    <input
                      type="checkbox"
                      checked={selectedParams.includes(ts.parameter_name)}
                      onChange={() => toggleParam(ts.parameter_name)}
                    />
                    <span className="truncate">{ts.parameter_name}</span>
                    {ts.units && <span className="signal-units">{ts.units}</span>}
                  </label>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Main content */}
        <div className="experiment-main">
          <div className="card mb-md">
            <TimeSeriesChart
              data={timeseries}
              selectedParams={selectedParams}
              title={`Shot #${experiment.shot_id} \u2014 Временные ряды`}
            />
          </div>

          <PredictionPanel experimentId={experiment.id} onDisruptionResult={handleDisruptionResult} />

          {disruptionResult && (
            <DisruptionChart
              timestamps={disruptionResult.timestamps}
              probabilities={disruptionResult.probabilities}
              threshold={0.7}
              warningTimeMs={disruptionResult.warning_time_ms ?? undefined}
            />
          )}

          <RecommendationPanel recommendations={recommendations} />

          <div className="export-actions">
            <ExportButton experimentId={experiment.id} />
          </div>
        </div>
      </div>
    </div>
  );
}
