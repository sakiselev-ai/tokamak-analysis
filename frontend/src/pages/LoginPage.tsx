import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

export default function LoginPage() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const { login, register, isLoading, error } = useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isRegister) {
      await register(email, password, fullName);
    } else {
      await login(email, password);
    }
    if (useAuthStore.getState().isAuthenticated) {
      navigate('/');
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
      }}
    >
      <div
        style={{
          background: '#fff',
          padding: 40,
          borderRadius: 12,
          boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
          width: 400,
        }}
      >
        <h1 style={{ textAlign: 'center', marginBottom: 8, color: '#1a1a2e' }}>Tokamak Analysis</h1>
        <p style={{ textAlign: 'center', color: '#666', marginBottom: 24, fontSize: 14 }}>
          НИЯУ МИФИ — ИИ-система анализа данных токамаков
        </p>

        <form onSubmit={handleSubmit}>
          {isRegister && (
            <input
              type="text"
              placeholder="Полное имя"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              style={{
                width: '100%',
                padding: '10px 12px',
                marginBottom: 12,
                border: '1px solid #ddd',
                borderRadius: 4,
                fontSize: 14,
                boxSizing: 'border-box',
              }}
            />
          )}
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            style={{
              width: '100%',
              padding: '10px 12px',
              marginBottom: 12,
              border: '1px solid #ddd',
              borderRadius: 4,
              fontSize: 14,
              boxSizing: 'border-box',
            }}
          />
          <input
            type="password"
            placeholder="Пароль"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            style={{
              width: '100%',
              padding: '10px 12px',
              marginBottom: 16,
              border: '1px solid #ddd',
              borderRadius: 4,
              fontSize: 14,
              boxSizing: 'border-box',
            }}
          />

          {error && <p style={{ color: '#e74c3c', fontSize: 14, marginBottom: 12 }}>{error}</p>}

          <button
            type="submit"
            disabled={isLoading}
            style={{
              width: '100%',
              padding: '10px',
              background: '#1a1a2e',
              color: '#fff',
              border: 'none',
              borderRadius: 4,
              fontSize: 16,
              cursor: isLoading ? 'not-allowed' : 'pointer',
              marginBottom: 12,
            }}
          >
            {isLoading ? 'Загрузка...' : isRegister ? 'Зарегистрироваться' : 'Войти'}
          </button>
        </form>

        <button
          onClick={() => setIsRegister(!isRegister)}
          style={{
            width: '100%',
            background: 'none',
            border: 'none',
            color: '#0f3460',
            cursor: 'pointer',
            fontSize: 14,
          }}
        >
          {isRegister ? 'Уже есть аккаунт? Войти' : 'Нет аккаунта? Зарегистрироваться'}
        </button>
      </div>
    </div>
  );
}
