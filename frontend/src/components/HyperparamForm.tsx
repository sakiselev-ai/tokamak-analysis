import { useState } from 'react';

interface HyperparamField {
  key: string;
  label: string;
  description: string;
  type: 'number' | 'select';
  default: number | string;
  options?: { value: string; label: string }[];
  min?: number;
  max?: number;
  step?: number;
}

const RF_FIELDS: HyperparamField[] = [
  { key: 'n_estimators', label: 'n_estimators', description: 'Количество деревьев в лесу', type: 'number', default: 200, min: 10, max: 2000, step: 10 },
  { key: 'max_depth', label: 'max_depth', description: 'Максимальная глубина дерева', type: 'number', default: 15, min: 1, max: 100, step: 1 },
  { key: 'min_samples_split', label: 'min_samples_split', description: 'Мин. образцов для разделения узла', type: 'number', default: 5, min: 2, max: 50, step: 1 },
  { key: 'class_weight', label: 'class_weight', description: 'Веса классов', type: 'select', default: 'balanced', options: [
    { value: 'balanced', label: 'balanced' },
    { value: 'balanced_subsample', label: 'balanced_subsample' },
    { value: 'none', label: 'None' },
  ]},
];

const LSTM_FIELDS: HyperparamField[] = [
  { key: 'hidden_size', label: 'hidden_size', description: 'Размер скрытого слоя', type: 'number', default: 128, min: 16, max: 1024, step: 16 },
  { key: 'num_layers', label: 'num_layers', description: 'Количество слоёв LSTM', type: 'number', default: 2, min: 1, max: 8, step: 1 },
  { key: 'dropout', label: 'dropout', description: 'Коэффициент dropout', type: 'number', default: 0.3, min: 0, max: 0.9, step: 0.05 },
  { key: 'attention_heads', label: 'attention_heads', description: 'Количество голов внимания', type: 'number', default: 4, min: 1, max: 16, step: 1 },
  { key: 'learning_rate', label: 'learning_rate', description: 'Скорость обучения', type: 'number', default: 0.001, min: 0.00001, max: 0.1, step: 0.0001 },
  { key: 'epochs', label: 'epochs', description: 'Количество эпох', type: 'number', default: 50, min: 1, max: 500, step: 1 },
  { key: 'batch_size', label: 'batch_size', description: 'Размер батча', type: 'number', default: 32, min: 1, max: 512, step: 1 },
];

const TRANSFORMER_FIELDS: HyperparamField[] = [
  { key: 'd_model', label: 'd_model', description: 'Размерность модели', type: 'number', default: 64, min: 16, max: 1024, step: 16 },
  { key: 'num_heads', label: 'num_heads', description: 'Количество голов внимания', type: 'number', default: 4, min: 1, max: 32, step: 1 },
  { key: 'num_layers', label: 'num_layers', description: 'Количество слоёв трансформера', type: 'number', default: 3, min: 1, max: 12, step: 1 },
  { key: 'dim_feedforward', label: 'dim_feedforward', description: 'Размерность feedforward слоя', type: 'number', default: 128, min: 32, max: 2048, step: 32 },
  { key: 'learning_rate', label: 'learning_rate', description: 'Скорость обучения', type: 'number', default: 0.0005, min: 0.00001, max: 0.1, step: 0.0001 },
  { key: 'epochs', label: 'epochs', description: 'Количество эпох', type: 'number', default: 100, min: 1, max: 500, step: 1 },
];

const FIELD_MAP: Record<string, HyperparamField[]> = {
  random_forest: RF_FIELDS,
  lstm_attention: LSTM_FIELDS,
  transformer: TRANSFORMER_FIELDS,
};

interface Props {
  modelType: string;
  onChange: (params: Record<string, unknown>) => void;
}

export default function HyperparamForm({ modelType, onChange }: Props) {
  const [collapsed, setCollapsed] = useState(true);
  const fields = FIELD_MAP[modelType] || [];

  const defaults: Record<string, unknown> = {};
  fields.forEach((f) => { defaults[f.key] = f.default; });

  const [values, setValues] = useState<Record<string, unknown>>(defaults);

  const handleChange = (key: string, val: unknown) => {
    const next = { ...values, [key]: val };
    setValues(next);
    onChange(next);
  };

  // Reset when model type changes
  const currentKeys = fields.map((f) => f.key).join(',');
  const valKeys = Object.keys(values).join(',');
  if (currentKeys !== valKeys) {
    const d: Record<string, unknown> = {};
    fields.forEach((f) => { d[f.key] = f.default; });
    setValues(d);
    onChange(d);
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div
        className="flex-between"
        style={{ cursor: 'pointer' }}
        onClick={() => setCollapsed(!collapsed)}
      >
        <h4 style={{ margin: 0 }}>
          Гиперпараметры
          <span className="text-muted text-sm" style={{ fontWeight: 400, marginLeft: 8 }}>
            ({fields.length} параметров)
          </span>
        </h4>
        <span style={{ fontSize: '1.2rem', color: 'var(--color-text-muted)' }}>
          {collapsed ? '\u25B6' : '\u25BC'}
        </span>
      </div>

      {!collapsed && (
        <div className="grid-2 mt-md" style={{ gap: 12 }}>
          {fields.map((field) => (
            <div className="form-group" key={field.key} style={{ marginBottom: 8 }}>
              <label>
                <code className="font-mono text-sm">{field.label}</code>
              </label>
              <span className="form-hint" style={{ marginTop: 0, marginBottom: 4, display: 'block' }}>
                {field.description}
              </span>
              {field.type === 'select' ? (
                <select
                  className="form-select"
                  value={String(values[field.key] ?? field.default)}
                  onChange={(e) => handleChange(field.key, e.target.value)}
                >
                  {field.options?.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              ) : (
                <input
                  type="number"
                  className="form-input"
                  value={values[field.key] as number ?? field.default}
                  min={field.min}
                  max={field.max}
                  step={field.step}
                  onChange={(e) => handleChange(field.key, parseFloat(e.target.value))}
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
