import { useState } from 'react';
import api from '../api/client';
import type { Experiment } from '../types';

interface Props {
  onLoaded: (experiment: Experiment) => void;
}

export default function ShotLoader({ onLoaded }: Props) {
  const [shotId, setShotId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLoad = async () => {
    if (!shotId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.post('/experiments/load', {
        shot_id: parseInt(shotId),
        source: 'mast',
      });
      onLoaded(res.data);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Ошибка загрузки';
      setError(msg);
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
        marginBottom: 20,
      }}
    >
      <h3 style={{ margin: '0 0 12px' }}>Загрузка данных выстрела</h3>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <input
          type="number"
          value={shotId}
          onChange={(e) => setShotId(e.target.value)}
          placeholder="Shot ID (например, 30420)"
          style={{
            padding: '8px 12px',
            border: '1px solid #ddd',
            borderRadius: 4,
            fontSize: 14,
            width: 250,
          }}
          onKeyDown={(e) => e.key === 'Enter' && handleLoad()}
        />
        <button
          onClick={handleLoad}
          disabled={loading || !shotId.trim()}
          style={{
            padding: '8px 20px',
            background: loading ? '#999' : '#1a1a2e',
            color: '#fff',
            border: 'none',
            borderRadius: 4,
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: 14,
          }}
        >
          {loading ? 'Загрузка...' : 'Загрузить'}
        </button>
      </div>
      {error && <p style={{ color: '#e74c3c', marginTop: 8, fontSize: 14 }}>{error}</p>}
    </div>
  );
}
