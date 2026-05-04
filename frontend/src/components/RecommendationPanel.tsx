import type { Recommendation } from '../types';

interface Props {
  recommendations: Recommendation[];
}

const PRIORITY_STYLES: Record<string, { bg: string; border: string; badge: string }> = {
  high: { bg: '#fee2e2', border: '#ef4444', badge: 'badge-danger' },
  medium: { bg: '#fef3c7', border: '#f59e0b', badge: 'badge-warning' },
  low: { bg: '#d1fae5', border: '#10b981', badge: 'badge-success' },
};

const PRIORITY_LABELS: Record<string, string> = {
  high: 'Высокий',
  medium: 'Средний',
  low: 'Низкий',
};

export default function RecommendationPanel({ recommendations }: Props) {
  if (!recommendations || recommendations.length === 0) return null;

  return (
    <div className="card mt-md">
      <h3 className="mb-sm">Рекомендации</h3>
      <div className="flex-col gap-sm">
        {recommendations.map((rec, idx) => {
          const style = PRIORITY_STYLES[rec.priority] || PRIORITY_STYLES.low;
          const isEmergency = rec.priority === 'high';

          return (
            <div
              key={idx}
              style={{
                background: style.bg,
                borderLeft: `4px solid ${style.border}`,
                borderRadius: 'var(--radius-sm)',
                padding: 16,
                animation: isEmergency ? 'pulse-border 2s infinite' : undefined,
              }}
            >
              <div className="flex-between mb-xs">
                <strong style={{ fontSize: '0.9375rem' }}>{rec.action}</strong>
                <span className={`badge ${style.badge}`}>
                  {PRIORITY_LABELS[rec.priority]}
                </span>
              </div>
              <p className="text-sm mb-xs" style={{ color: 'var(--color-text-secondary)' }}>
                {rec.description}
              </p>
              <div className="text-sm" style={{ marginTop: 8 }}>
                <strong>Действие:</strong> {rec.suggested_action}
              </div>
              {rec.timeframe_ms > 0 && (
                <div className="text-xs text-muted" style={{ marginTop: 4 }}>
                  Временное окно: {rec.timeframe_ms.toFixed(1)} мс
                </div>
              )}
              {rec.parameter && (
                <div className="text-xs text-muted" style={{ marginTop: 2 }}>
                  Параметр: <code className="font-mono">{rec.parameter}</code>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
