import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import ShotLoader from '../components/ShotLoader';
import type { Experiment } from '../types';

export default function DashboardPage() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    api.get('/experiments/').then((res) => setExperiments(res.data.experiments)).catch(() => {});
  }, []);

  const handleLoaded = (exp: Experiment) => {
    setExperiments((prev) => [exp, ...prev]);
    navigate(`/experiment/${exp.id}`);
  };

  return (
    <div>
      <h2 style={{ marginBottom: 20 }}>Dashboard</h2>
      <ShotLoader onLoaded={handleLoaded} />

      <div
        style={{
          background: '#fff',
          padding: 20,
          borderRadius: 8,
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
        }}
      >
        <h3 style={{ margin: '0 0 12px' }}>Загруженные эксперименты</h3>
        {experiments.length === 0 ? (
          <p style={{ color: '#999' }}>Нет загруженных экспериментов</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #eee', textAlign: 'left' }}>
                <th style={{ padding: 8 }}>Shot ID</th>
                <th style={{ padding: 8 }}>Источник</th>
                <th style={{ padding: 8 }}>Статус</th>
                <th style={{ padding: 8 }}>Дата</th>
                <th style={{ padding: 8 }}>Сигналов</th>
                <th style={{ padding: 8 }}></th>
              </tr>
            </thead>
            <tbody>
              {experiments.map((exp) => (
                <tr key={exp.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: 8, fontWeight: 600 }}>{exp.shot_id}</td>
                  <td style={{ padding: 8 }}>{exp.source.toUpperCase()}</td>
                  <td style={{ padding: 8 }}>
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: 12,
                        fontSize: 12,
                        background:
                          exp.status === 'preprocessed'
                            ? '#d4edda'
                            : exp.status === 'error'
                            ? '#f8d7da'
                            : '#fff3cd',
                        color:
                          exp.status === 'preprocessed'
                            ? '#155724'
                            : exp.status === 'error'
                            ? '#721c24'
                            : '#856404',
                      }}
                    >
                      {exp.status}
                    </span>
                  </td>
                  <td style={{ padding: 8, fontSize: 13, color: '#666' }}>
                    {new Date(exp.loaded_at).toLocaleString('ru')}
                  </td>
                  <td style={{ padding: 8 }}>
                    {exp.metadata_json?.signal_count as number ?? '—'}
                  </td>
                  <td style={{ padding: 8 }}>
                    <button
                      onClick={() => navigate(`/experiment/${exp.id}`)}
                      style={{
                        padding: '4px 12px',
                        background: '#1a1a2e',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 4,
                        cursor: 'pointer',
                        fontSize: 13,
                      }}
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
