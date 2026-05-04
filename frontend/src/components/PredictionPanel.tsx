import { useState } from 'react';
import api from '../api/client';
import type { ClassifyResult, DisruptionResult } from '../types';

interface Props {
  experimentId: number;
}

export default function PredictionPanel({ experimentId }: Props) {
  const [classifyResult, setClassifyResult] = useState<ClassifyResult | null>(null);
  const [disruptionResult, setDisruptionResult] = useState<DisruptionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClassify = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.post('/predictions/classify', { experiment_id: experimentId });
      setClassifyResult(res.data);
    } catch (err: unknown) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Ошибка классификации');
    } finally {
      setLoading(false);
    }
  };

  const handleDisruption = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.post('/predictions/disruption', {
        experiment_id: experimentId,
        threshold: 0.7,
      });
      setDisruptionResult(res.data);
    } catch (err: unknown) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Ошибка предсказания');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        background: '#fff',
        padding: 20,
        borderRadius: 8,
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
        marginTop: 20,
      }}
    >
      <h3 style={{ margin: '0 0 12px' }}>ML-анализ</h3>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button
          onClick={handleClassify}
          disabled={loading}
          style={{
            padding: '8px 16px',
            background: '#2ecc71',
            color: '#fff',
            border: 'none',
            borderRadius: 4,
            cursor: 'pointer',
          }}
        >
          Классифицировать
        </button>
        <button
          onClick={handleDisruption}
          disabled={loading}
          style={{
            padding: '8px 16px',
            background: '#e74c3c',
            color: '#fff',
            border: 'none',
            borderRadius: 4,
            cursor: 'pointer',
          }}
        >
          Предсказать срыв
        </button>
      </div>

      {error && <p style={{ color: '#e74c3c', fontSize: 14 }}>{error}</p>}

      {classifyResult && (
        <div
          style={{
            padding: 12,
            background: classifyResult.label === 'stable' ? '#d4edda' : '#f8d7da',
            borderRadius: 4,
            marginBottom: 12,
          }}
        >
          <strong>Классификация:</strong> {classifyResult.label === 'stable' ? 'Стабильный' : 'Нестабильный'}
          <br />
          <strong>Уверенность:</strong> {(classifyResult.confidence * 100).toFixed(1)}%
          <br />
          <strong>Время инференса:</strong> {classifyResult.inference_time_ms.toFixed(1)} мс
        </div>
      )}

      {disruptionResult && (
        <div
          style={{
            padding: 12,
            background: disruptionResult.warning_issued ? '#f8d7da' : '#d4edda',
            borderRadius: 4,
          }}
        >
          <strong>Предсказание срыва:</strong>{' '}
          {disruptionResult.warning_issued ? 'ПРЕДУПРЕЖДЕНИЕ' : 'Норма'}
          {disruptionResult.warning_time_ms && (
            <>
              <br />
              <strong>Заблаговременность:</strong> {disruptionResult.warning_time_ms.toFixed(1)} мс
            </>
          )}
          <br />
          <strong>Время инференса:</strong> {disruptionResult.inference_time_ms.toFixed(1)} мс
        </div>
      )}
    </div>
  );
}
