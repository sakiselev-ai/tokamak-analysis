import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Plot from 'react-plotly.js';
import api from '../api/client';
import ShotLoader from '../components/ShotLoader';
import type { Experiment, MLModel } from '../types';

export default function DashboardPage() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [totalExperiments, setTotalExperiments] = useState(0);
  const [models, setModels] = useState<MLModel[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    api
      .get('/experiments/?limit=200')
      .then((res) => {
        setExperiments(res.data.experiments);
        setTotalExperiments(res.data.total ?? res.data.experiments.length);
      })
      .catch(() => {})
      .finally(() => setLoading(false));

    api
      .get('/models/')
      .then((res) => setModels(res.data))
      .catch(() => {});
  }, []);

  const handleLoaded = (exp: Experiment) => {
    setExperiments((prev) => [exp, ...prev]);
    navigate(`/experiment/${exp.id}`);
  };

  const preprocessedCount = experiments.filter((e) => e.status === 'preprocessed').length;
  const totalSignals = experiments.reduce(
    (sum, e) => sum + ((e.metadata_json?.signal_count as number) || 0),
    0
  );

  const statusBadge = (status: string) => {
    const cls =
      status === 'preprocessed'
        ? 'badge-success'
        : status === 'error'
        ? 'badge-danger'
        : 'badge-warning';
    return <span className={`badge ${cls}`}>{status}</span>;
  };

  return (
    <div>
      <h2 className="mb-lg">Dashboard</h2>

      {/* Summary Stats */}
      <div className="grid-3 mb-lg">
        <div className="stat-card">
          <div className="stat-icon stat-icon-primary">{'\u26A1'}</div>
          <div>
            <div className="stat-value">{totalExperiments}</div>
            <div className="stat-label">Экспериментов</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon stat-icon-success">{'\u2713'}</div>
          <div>
            <div className="stat-value">{preprocessedCount}</div>
            <div className="stat-label">Обработано</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon stat-icon-warning">{'\u223F'}</div>
          <div>
            <div className="stat-value">{totalSignals}</div>
            <div className="stat-label">Сигналов</div>
          </div>
        </div>
      </div>

      <ShotLoader onLoaded={handleLoaded} />

      {/* Model Comparison */}
      {models.length > 0 && (
        <div className="card mb-lg">
          <div className="card-header">
            <h3>Сравнение моделей</h3>
          </div>

          <table className="table" style={{ marginBottom: 20 }}>
            <thead>
              <tr>
                <th>Модель</th>
                <th>Тип</th>
                <th>Accuracy</th>
                <th>F1</th>
                <th>AUC</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m) => (
                <tr key={m.id}>
                  <td className="font-semibold">{m.name}</td>
                  <td>
                    <span className="badge badge-info">{m.model_type}</span>
                  </td>
                  <td>{m.metrics_json?.accuracy != null ? m.metrics_json.accuracy.toFixed(4) : '\u2014'}</td>
                  <td>{m.metrics_json?.f1 != null ? m.metrics_json.f1.toFixed(4) : '\u2014'}</td>
                  <td>{(m.metrics_json?.auc_roc ?? m.metrics_json?.auc) != null ? (m.metrics_json.auc_roc ?? m.metrics_json.auc).toFixed(4) : '\u2014'}</td>
                  <td>
                    <span className={`badge ${m.is_active ? 'badge-success' : 'badge-neutral'}`}>
                      {m.is_active ? 'Активна' : 'Неактивна'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* AUC bar chart */}
          {models.some((m) => m.metrics_json?.auc != null) && (
            <Plot
              data={[
                {
                  x: models.filter((m) => m.metrics_json?.auc != null).map((m) => m.name),
                  y: models.filter((m) => m.metrics_json?.auc != null).map((m) => m.metrics_json!.auc),
                  type: 'bar',
                  marker: {
                    color: models
                      .filter((m) => m.metrics_json?.auc != null)
                      .map((m) => (m.is_active ? '#2ecc71' : '#3498db')),
                  },
                  hovertemplate: '%{x}<br>AUC: %{y:.4f}<extra></extra>',
                },
              ]}
              layout={{
                title: 'Сравнение AUC моделей',
                yaxis: { title: 'AUC', range: [0, 1] },
                height: 350,
                margin: { l: 60, r: 30, t: 50, b: 80 },
              }}
              config={{ responsive: true, displayModeBar: false }}
              style={{ width: '100%' }}
            />
          )}
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <h3>Загруженные эксперименты</h3>
        </div>

        {loading ? (
          <div className="loading-overlay">
            <span className="spinner spinner-lg" />
            Загрузка данных...
          </div>
        ) : experiments.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">{'\u269B'}</div>
            <div className="empty-state-text">Нет загруженных экспериментов</div>
            <div className="empty-state-hint">
              Загрузите данные выстрела, указав Shot ID выше
            </div>
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Shot ID</th>
                <th>Источник</th>
                <th>Статус</th>
                <th>Дата</th>
                <th>Сигналов</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {experiments.map((exp) => (
                <tr key={exp.id}>
                  <td className="font-semibold">{exp.shot_id}</td>
                  <td>
                    <span className="badge badge-info">{exp.source.toUpperCase()}</span>
                  </td>
                  <td>{statusBadge(exp.status)}</td>
                  <td className="text-sm text-secondary">
                    {new Date(exp.loaded_at).toLocaleString('ru')}
                  </td>
                  <td>{(exp.metadata_json?.signal_count as number) ?? '\u2014'}</td>
                  <td>
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => navigate(`/experiment/${exp.id}`)}
                    >
                      Открыть
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
