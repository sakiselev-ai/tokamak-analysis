import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import ShotLoader from '../components/ShotLoader';
import type { Experiment } from '../types';

export default function DashboardPage() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    api
      .get('/experiments/')
      .then((res) => setExperiments(res.data.experiments))
      .catch(() => {})
      .finally(() => setLoading(false));
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
            <div className="stat-value">{experiments.length}</div>
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
