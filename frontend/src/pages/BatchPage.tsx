import { useState } from 'react';
import api from '../api/client';
import type { Experiment, BatchLoadResult, ClassifyResult, DisruptionResult } from '../types';

interface BatchPredictionResult {
  experiment_id: number;
  shot_id: number;
  result?: ClassifyResult | DisruptionResult;
  error?: string;
}

export default function BatchPage() {
  const [shotInput, setShotInput] = useState('');
  const [loadingBatch, setLoadingBatch] = useState(false);
  const [loadResult, setLoadResult] = useState<BatchLoadResult | null>(null);
  const [loadedExperiments, setLoadedExperiments] = useState<Experiment[]>([]);
  const [loadProgress, setLoadProgress] = useState<{ loaded: number; total: number } | null>(null);

  const [predicting, setPredicting] = useState(false);
  const [predictionResults, setPredictionResults] = useState<BatchPredictionResult[]>([]);
  const [predictionType, setPredictionType] = useState<string | null>(null);

  const parseShotIds = (input: string): number[] => {
    const ids: number[] = [];
    const lines = input.split(/[\n,]/).map((s) => s.trim()).filter(Boolean);
    for (const part of lines) {
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
    return [...new Set(ids)];
  };

  const handleLoadAll = async () => {
    const ids = parseShotIds(shotInput);
    if (ids.length === 0) return;

    setLoadingBatch(true);
    setLoadResult(null);
    setLoadProgress({ loaded: 0, total: ids.length });
    setPredictionResults([]);
    setPredictionType(null);

    try {
      const res = await api.post('/experiments/batch-load', { shot_ids: ids });
      const result: BatchLoadResult = res.data;
      setLoadResult(result);
      setLoadedExperiments(result.experiments);
      setLoadProgress({ loaded: result.total_loaded, total: ids.length });
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Ошибка пакетной загрузки';
      setLoadResult({
        experiments: [],
        failed: ids.map((id) => ({ shot_id: id, error: detail })),
        total_loaded: 0,
      });
      setLoadProgress({ loaded: 0, total: ids.length });
    } finally {
      setLoadingBatch(false);
    }
  };

  const handleBatchPredict = async (type: 'classify' | 'disruption') => {
    if (loadedExperiments.length === 0) return;
    setPredicting(true);
    setPredictionResults([]);
    setPredictionType(type === 'classify' ? 'Классификация' : 'Предсказание срывов');

    const results: BatchPredictionResult[] = [];
    for (const exp of loadedExperiments) {
      try {
        const endpoint = type === 'classify' ? '/predictions/classify' : '/predictions/disruption';
        const payload: Record<string, unknown> = { experiment_id: exp.id };
        if (type === 'disruption') payload.threshold = 0.7;
        const res = await api.post(endpoint, payload);
        results.push({ experiment_id: exp.id, shot_id: exp.shot_id, result: res.data });
      } catch (err: unknown) {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Ошибка';
        results.push({ experiment_id: exp.id, shot_id: exp.shot_id, error: detail });
      }
      setPredictionResults([...results]);
    }

    setPredicting(false);
  };

  const successCount = predictionResults.filter((r) => r.result).length;
  const failCount = predictionResults.filter((r) => r.error).length;

  return (
    <div>
      <h2 className="mb-lg">Пакетная обработка</h2>

      {/* Input */}
      <div className="card mb-md">
        <h3 className="mb-sm">Загрузка экспериментов</h3>
        <div className="form-group">
          <label>Shot IDs</label>
          <textarea
            className="form-input"
            rows={5}
            placeholder={'Введите Shot IDs, по одному на строку или через запятую:\n30420\n30421\n30425-30430'}
            value={shotInput}
            onChange={(e) => setShotInput(e.target.value)}
            style={{ resize: 'vertical' }}
          />
          <span className="form-hint">
            Поддерживаются диапазоны (30420-30450) и запятые. Всего: {parseShotIds(shotInput).length} ID.
          </span>
        </div>
        <button
          className="btn btn-primary"
          onClick={handleLoadAll}
          disabled={loadingBatch || parseShotIds(shotInput).length === 0}
        >
          {loadingBatch ? (
            <>
              <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
              Загрузка...
            </>
          ) : (
            'Загрузить все'
          )}
        </button>
      </div>

      {/* Progress */}
      {loadProgress && (
        <div className="card mb-md">
          <h4 className="mb-sm">Прогресс загрузки</h4>
          <div style={{
            height: 10,
            background: 'var(--color-border)',
            borderRadius: 'var(--radius-full)',
            overflow: 'hidden',
            marginBottom: 8,
          }}>
            <div style={{
              height: '100%',
              width: `${loadProgress.total > 0 ? (loadProgress.loaded / loadProgress.total * 100) : 0}%`,
              background: 'var(--color-success)',
              borderRadius: 'var(--radius-full)',
              transition: 'width 0.3s',
            }} />
          </div>
          <span className="text-sm text-secondary">
            {loadProgress.loaded} / {loadProgress.total} загружено
          </span>
        </div>
      )}

      {/* Load results table */}
      {loadResult && (
        <div className="card mb-md">
          <h4 className="mb-sm">Результаты загрузки</h4>

          {loadResult.experiments.length > 0 && (
            <div style={{ overflowX: 'auto', marginBottom: 16 }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Shot ID</th>
                    <th>Статус</th>
                    <th>Источник</th>
                    <th>Дата</th>
                  </tr>
                </thead>
                <tbody>
                  {loadResult.experiments.map((exp) => (
                    <tr key={exp.id}>
                      <td className="font-mono">{exp.shot_id}</td>
                      <td><span className="badge badge-success">Загружено</span></td>
                      <td>{exp.source}</td>
                      <td className="text-sm text-secondary">
                        {new Date(exp.loaded_at).toLocaleString('ru')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {loadResult.failed.length > 0 && (
            <div style={{ overflowX: 'auto' }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Shot ID</th>
                    <th>Статус</th>
                    <th>Ошибка</th>
                  </tr>
                </thead>
                <tbody>
                  {loadResult.failed.map((f, i) => (
                    <tr key={i}>
                      <td className="font-mono">{f.shot_id}</td>
                      <td><span className="badge badge-danger">Ошибка</span></td>
                      <td className="text-sm text-danger">{f.error}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Batch prediction buttons */}
      {loadedExperiments.length > 0 && (
        <div className="card mb-md">
          <h4 className="mb-sm">Пакетный ML-анализ</h4>
          <p className="text-sm text-secondary mb-md">
            Загружено экспериментов: {loadedExperiments.length}
          </p>
          <div className="flex gap-sm">
            <button
              className="btn btn-success"
              onClick={() => handleBatchPredict('classify')}
              disabled={predicting}
            >
              {predicting && predictionType === 'Классификация' ? (
                <>
                  <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                  Классификация...
                </>
              ) : (
                'Пакетная классификация'
              )}
            </button>
            <button
              className="btn btn-danger"
              onClick={() => handleBatchPredict('disruption')}
              disabled={predicting}
            >
              {predicting && predictionType === 'Предсказание срывов' ? (
                <>
                  <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                  Предсказание...
                </>
              ) : (
                'Пакетное предсказание срывов'
              )}
            </button>
          </div>
        </div>
      )}

      {/* Prediction results */}
      {predictionResults.length > 0 && (
        <div className="card">
          <div className="flex-between mb-sm">
            <h4 style={{ margin: 0 }}>Результаты: {predictionType}</h4>
            <div className="flex gap-sm">
              <span className="badge badge-success">Успешно: {successCount}</span>
              {failCount > 0 && <span className="badge badge-danger">Ошибки: {failCount}</span>}
            </div>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Shot ID</th>
                  <th>Статус</th>
                  <th>Результат</th>
                </tr>
              </thead>
              <tbody>
                {predictionResults.map((pr, i) => (
                  <tr key={i}>
                    <td className="font-mono">{pr.shot_id}</td>
                    <td>
                      {pr.error ? (
                        <span className="badge badge-danger">Ошибка</span>
                      ) : (
                        <span className="badge badge-success">Успешно</span>
                      )}
                    </td>
                    <td className="text-sm">
                      {pr.error ? (
                        <span className="text-danger">{pr.error}</span>
                      ) : pr.result ? (
                        <code className="font-mono text-xs">
                          {JSON.stringify(pr.result).slice(0, 120)}
                        </code>
                      ) : '\u2014'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {predicting && (
            <div className="flex items-center gap-sm mt-sm text-muted">
              <span className="spinner" />
              Обработка {predictionResults.length} / {loadedExperiments.length}...
            </div>
          )}
        </div>
      )}
    </div>
  );
}
