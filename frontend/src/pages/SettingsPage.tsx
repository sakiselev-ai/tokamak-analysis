import { useState } from 'react';
import type { UserSettings } from '../types';

export default function SettingsPage() {
  const [settings, setSettings] = useState<UserSettings>({
    disruption_threshold: 0.7,
    notification_enabled: true,
  });
  const [saved, setSaved] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const handleThresholdChange = (val: number) => {
    setSettings((s) => ({ ...s, disruption_threshold: val }));
    setSaved(false);
  };

  const handleNotificationToggle = () => {
    setSettings((s) => ({ ...s, notification_enabled: !s.notification_enabled }));
    setSaved(false);
  };

  const handleSave = () => {
    // Persist to localStorage for now
    localStorage.setItem('user_settings', JSON.stringify(settings));
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const handleExportData = () => {
    // Trigger data export download
    window.open('/api/v1/users/me/export', '_blank');
  };

  const handleDeleteAccount = () => {
    setShowDeleteConfirm(false);
    // Would call DELETE /api/v1/users/me
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    window.location.href = '/login';
  };

  return (
    <div>
      <h2 className="mb-lg">Настройки</h2>

      {/* Disruption threshold */}
      <div className="card mb-md">
        <h3 className="mb-sm">Порог предсказания срывов</h3>
        <p className="text-sm text-secondary mb-md">
          Порог вероятности, при превышении которого выдаётся предупреждение о возможном срыве плазмы.
        </p>
        <div className="form-group" style={{ maxWidth: 400 }}>
          <label>
            Порог: <strong>{settings.disruption_threshold.toFixed(2)}</strong>
          </label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={settings.disruption_threshold}
            onChange={(e) => handleThresholdChange(parseFloat(e.target.value))}
            style={{ width: '100%', marginTop: 4 }}
          />
          <div className="flex-between text-xs text-muted" style={{ marginTop: 4 }}>
            <span>0.0 (чувствительный)</span>
            <span>1.0 (строгий)</span>
          </div>
        </div>
      </div>

      {/* Notifications */}
      <div className="card mb-md">
        <h3 className="mb-sm">Уведомления</h3>
        <label className="flex items-center gap-sm" style={{ cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={settings.notification_enabled}
            onChange={handleNotificationToggle}
            style={{ width: 18, height: 18 }}
          />
          <div>
            <div className="font-semibold">Включить уведомления</div>
            <div className="text-xs text-muted">
              Получать уведомления о завершении обучения и результатах анализа
            </div>
          </div>
        </label>
      </div>

      {/* Save button */}
      <div className="flex items-center gap-sm mb-lg">
        <button className="btn btn-primary" onClick={handleSave}>
          Сохранить настройки
        </button>
        {saved && (
          <span className="text-sm text-success">Настройки сохранены</span>
        )}
      </div>

      {/* Account section */}
      <div className="card mb-md">
        <h3 className="mb-sm">Аккаунт</h3>

        <div className="flex gap-sm mb-md">
          <button className="btn btn-outline" onClick={handleExportData}>
            Экспорт данных
          </button>
          <button
            className="btn btn-danger"
            onClick={() => setShowDeleteConfirm(true)}
          >
            Удалить аккаунт
          </button>
        </div>

        {showDeleteConfirm && (
          <div
            style={{
              padding: 16,
              background: '#fee2e2',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-danger)',
            }}
          >
            <p className="font-semibold mb-sm" style={{ color: 'var(--color-danger)' }}>
              Вы уверены, что хотите удалить аккаунт?
            </p>
            <p className="text-sm text-secondary mb-md">
              Это действие необратимо. Все ваши данные, модели и результаты будут удалены.
            </p>
            <div className="flex gap-sm">
              <button className="btn btn-danger" onClick={handleDeleteAccount}>
                Да, удалить
              </button>
              <button className="btn btn-outline" onClick={() => setShowDeleteConfirm(false)}>
                Отмена
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Privacy */}
      <div className="card">
        <h3 className="mb-sm">Конфиденциальность</h3>
        <a
          href="/privacy"
          className="text-sm"
          target="_blank"
          rel="noopener noreferrer"
        >
          Политика конфиденциальности
        </a>
      </div>
    </div>
  );
}
