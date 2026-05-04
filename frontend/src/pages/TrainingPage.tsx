import { useEffect, useState } from 'react';
import api from '../api/client';
import type { ModelRun } from '../types';

export default function TrainingPage() {
  const [modelType, setModelType] = useState('random_forest');
  const [task, setTask] = useState('classification');
  const [runs, setRuns] = useState<ModelRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    api.get('/models/runs').then((res) => setRuns(res.data)).catch(() => {});
  }, []);

  const handleTrain = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const res = await api.post('/models/train', { model_type: modelType, task });
      setMessage(`Обучение запущено (run_id: ${res.data.run_id})`);
      // Refresh runs
      const runsRes = await api.get('/models/runs');
      setRuns(runsRes.data);
    } catch (err: unknown) {
      setMessage((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Ошибка');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 style={{ marginBottom: 20 }}>Обучение моделей</h2>

      <div
        style={{
          background: '#fff',
          padding: 20,
          borderRadius: 8,
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
          marginBottom: 20,
        }}
      >
        <h3 style={{ margin: '0 0 12px' }}>Запустить обучение</h3>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <select
            value={modelType}
            onChange={(e) => setModelType(e.target.value)}
            style={{ padding: '8px 12px', borderRadius: 4, border: '1px solid #ddd' }}
          >
            <option value="random_forest">Random Forest (baseline)</option>
            <option value="lstm_attention">bi-LSTM + Attention</option>
            <option value="transformer">Transformer</option>
          </select>
          <select
            value={task}
            onChange={(e) => setTask(e.target.value)}
            style={{ padding: '8px 12px', borderRadius: 4, border: '1px solid #ddd' }}
          >
            <option value="classification">Классификация</option>
            <option value="disruption_prediction">Предсказание срывов</option>
          </select>
          <button
            onClick={handleTrain}
            disabled={loading}
            style={{
              padding: '8px 20px',
              background: '#1a1a2e',
              color: '#fff',
              border: 'none',
              borderRadius: 4,
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Запуск...' : 'Обучить'}
          </button>
        </div>
        {message && <p style={{ marginTop: 12, fontSize: 14, color: '#333' }}>{message}</p>}
      </div>

      <div
        style={{
          background: '#fff',
          padding: 20,
          borderRadius: 8,
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
        }}
      >
        <h3 style={{ margin: '0 0 12px' }}>История запусков</h3>
        {runs.length === 0 ? (
          <p style={{ color: '#999' }}>Нет запусков</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #eee', textAlign: 'left' }}>
                <th style={{ padding: 8 }}>ID</th>
                <th style={{ padding: 8 }}>Статус</th>
                <th style={{ padding: 8 }}>Прогресс</th>
                <th style={{ padding: 8 }}>Метрики</th>
                <th style={{ padding: 8 }}>Дата</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: 8 }}>{run.id}</td>
                  <td style={{ padding: 8 }}>
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: 12,
                        fontSize: 12,
                        background:
                          run.status === 'completed' ? '#d4edda' :
                          run.status === 'failed' ? '#f8d7da' :
                          run.status === 'running' ? '#cce5ff' : '#fff3cd',
                      }}
                    >
                      {run.status}
                    </span>
                  </td>
                  <td style={{ padding: 8 }}>
                    {run.progress != null ? `${(run.progress * 100).toFixed(0)}%` : '—'}
                  </td>
                  <td style={{ padding: 8, fontSize: 12, fontFamily: 'monospace' }}>
                    {run.metrics_json ? JSON.stringify(run.metrics_json).slice(0, 80) : '—'}
                  </td>
                  <td style={{ padding: 8, fontSize: 13, color: '#666' }}>
                    {new Date(run.created_at).toLocaleString('ru')}
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
