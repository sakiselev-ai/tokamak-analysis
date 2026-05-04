import { useEffect, useState, useCallback, useRef } from 'react';
import api from '../api/client';
import HyperparamForm from '../components/HyperparamForm';
import type { ModelRun } from '../types';

const MODEL_DESCRIPTIONS: Record<string, { name: string; desc: string }> = {
  random_forest: {
    name: 'Random Forest (baseline)',
    desc: 'Ансамбль решающих деревьев. Быстрое обучение, хорошая интерпретируемость. Подходит для базового анализа и сравнения.',
  },
  lstm_attention: {
    name: 'bi-LSTM + Attention',
    desc: 'Двунаправленная LSTM с механизмом внимания. Хорошо работает с временными рядами, улавливает долгосрочные зависимости.',
  },
  transformer: {
    name: 'Transformer',
    desc: 'Архитектура на основе self-attention. Лучшая производительность на больших данных, параллельное обучение.',
  },
};

const STATUS_BADGE: Record<string, string> = {
  completed: 'badge-success',
  failed: 'badge-danger',
  running: 'badge-info',
  pending: 'badge-warning',
};

const STATUS_LABELS: Record<string, string> = {
  completed: 'Завершено',
  failed: 'Ошибка',
  running: 'Выполняется',
  pending: 'Ожидание',
};

export default function TrainingPage() {
  const [modelType, setModelType] = useState('random_forest');
  const [task, setTask] = useState('classification');
  const [shotIds, setShotIds] = useState('');
  const [hyperparams, setHyperparams] = useState<Record<string, unknown>>({});
  const [runs, setRuns] = useState<ModelRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [messageType, setMessageType] = useState<'success' | 'error'>('success');
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchRuns = useCallback(async () => {
    try {
      const res = await api.get('/models/runs');
      setRuns(res.data);
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  // Auto-refresh while any run is in progress
  useEffect(() => {
    const hasRunning = runs.some((r) => r.status === 'running' || r.status === 'pending');
    if (hasRunning) {
      if (!intervalRef.current) {
        intervalRef.current = setInterval(fetchRuns, 5000);
      }
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [runs, fetchRuns]);

  const parseShotIds = (input: string): number[] => {
    const ids: number[] = [];
    const parts = input.split(',').map((s) => s.trim()).filter(Boolean);
    for (const part of parts) {
      if (part.includes('-')) {
        const [start, end] = part.split('-').map(Number);
        if (!isNaN(start) && !isNaN(end)) {
          for (let i = start; i <= end; i++) ids.push(i);
        }
      } else {
        const n = Number(part);
        if (!isNaN(n)) ids.push(n);
      }
    }
    return ids;
  };

  const handleTrain = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const payload: Record<string, unknown> = {
        model_type: modelType,
        task,
        hyperparameters: hyperparams,
      };
      const ids = parseShotIds(shotIds);
      if (ids.length > 0) {
        payload.shot_ids = ids;
      }
      const res = await api.post('/models/train', payload);
      setMessage(`Обучение запущено (run_id: ${res.data.run_id})`);
      setMessageType('success');
      await fetchRuns();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Ошибка запуска обучения';
      setMessage(detail);
      setMessageType('error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 className="mb-lg">Обучение моделей</h2>

      {/* Model type selector */}
      <div className="card mb-md">
        <h3 className="mb-sm">Тип модели</h3>
        <div className="grid-3" style={{ gap: 12 }}>
          {Object.entries(MODEL_DESCRIPTIONS).map(([key, info]) => (
            <div
              key={key}
              onClick={() => setModelType(key)}
              style={{
                padding: 16,
                borderRadius: 'var(--radius-md)',
                border: `2px solid ${modelType === key ? 'var(--color-accent)' : 'var(--color-border)'}`,
                background: modelType === key ? 'rgba(15, 52, 96, 0.04)' : 'var(--color-surface)',
                cursor: 'pointer',
                transition: 'border-color 0.15s, background 0.15s',
              }}
            >
              <div className="font-semibold mb-xs">{info.name}</div>
              <div className="text-sm text-secondary">{info.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Task selector */}
      <div className="card mb-md">
        <h3 className="mb-sm">Задача</h3>
        <div className="flex gap-md">
          <label className="flex items-center gap-sm" style={{ cursor: 'pointer' }}>
            <input
              type="radio"
              name="task"
              value="classification"
              checked={task === 'classification'}
              onChange={(e) => setTask(e.target.value)}
            />
            <div>
              <div className="font-semibold">Классификация</div>
              <div className="text-xs text-muted">Определение типа плазменного режима</div>
            </div>
          </label>
          <label className="flex items-center gap-sm" style={{ cursor: 'pointer' }}>
            <input
              type="radio"
              name="task"
              value="disruption_prediction"
              checked={task === 'disruption_prediction'}
              onChange={(e) => setTask(e.target.value)}
            />
            <div>
              <div className="font-semibold">Предсказание срывов</div>
              <div className="text-xs text-muted">Раннее предупреждение о дестабилизации плазмы</div>
            </div>
          </label>
        </div>
      </div>

      {/* Hyperparameters */}
      <HyperparamForm modelType={modelType} onChange={setHyperparams} />

      {/* Dataset shot IDs */}
      <div className="card mt-md mb-md">
        <h4 className="mb-sm">Набор данных</h4>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label>Shot IDs</label>
          <input
            type="text"
            className="form-input"
            placeholder="Например: 30420, 30425, 30430-30450"
            value={shotIds}
            onChange={(e) => setShotIds(e.target.value)}
          />
          <span className="form-hint">
            Через запятую или диапазон (30420-30450). Оставьте пустым для использования всех доступных данных.
          </span>
        </div>
      </div>

      {/* Start training */}
      <div className="flex items-center gap-md mb-lg">
        <button
          className="btn btn-primary btn-lg"
          onClick={handleTrain}
          disabled={loading}
        >
          {loading ? (
            <>
              <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
              Запуск...
            </>
          ) : (
            'Начать обучение'
          )}
        </button>
        {message && (
          <span
            className={`text-sm ${messageType === 'error' ? 'text-danger' : 'text-success'}`}
          >
            {message}
          </span>
        )}
      </div>

      {/* Training runs table */}
      <div className="card">
        <div className="flex-between mb-sm">
          <h3 style={{ margin: 0 }}>История запусков</h3>
          <button className="btn btn-ghost btn-sm" onClick={fetchRuns}>
            Обновить
          </button>
        </div>

        {runs.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">{'\u2699'}</div>
            <div className="empty-state-text">Нет запусков обучения</div>
            <div className="empty-state-hint">Настройте параметры и запустите обучение</div>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Статус</th>
                  <th>Прогресс</th>
                  <th>Метрики</th>
                  <th>Начало</th>
                  <th>Завершение</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <td className="font-mono text-sm">{run.id}</td>
                    <td>
                      <span className={`badge ${STATUS_BADGE[run.status] || 'badge-neutral'}`}>
                        {STATUS_LABELS[run.status] || run.status}
                      </span>
                    </td>
                    <td style={{ minWidth: 140 }}>
                      {run.progress != null ? (
                        <div>
                          <div
                            style={{
                              height: 8,
                              background: 'var(--color-border)',
                              borderRadius: 'var(--radius-full)',
                              overflow: 'hidden',
                            }}
                          >
                            <div
                              style={{
                                height: '100%',
                                width: `${Math.min(run.progress * 100, 100)}%`,
                                background: run.status === 'failed' ? 'var(--color-danger)' : 'var(--color-success)',
                                borderRadius: 'var(--radius-full)',
                                transition: 'width 0.3s',
                              }}
                            />
                          </div>
                          <span className="text-xs text-muted" style={{ marginTop: 2, display: 'inline-block' }}>
                            {(run.progress * 100).toFixed(0)}%
                          </span>
                        </div>
                      ) : (
                        <span className="text-muted">&mdash;</span>
                      )}
                    </td>
                    <td>
                      {run.metrics_json ? (
                        <code className="font-mono text-xs">
                          {Object.entries(run.metrics_json)
                            .map(([k, v]) => `${k}: ${typeof v === 'number' ? (v as number).toFixed(4) : v}`)
                            .join(', ')
                            .slice(0, 100)}
                        </code>
                      ) : (
                        <span className="text-muted">&mdash;</span>
                      )}
                    </td>
                    <td className="text-sm text-secondary">
                      {run.started_at ? new Date(run.started_at).toLocaleString('ru') : '\u2014'}
                    </td>
                    <td className="text-sm text-secondary">
                      {run.finished_at ? new Date(run.finished_at).toLocaleString('ru') : '\u2014'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
