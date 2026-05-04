import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

export default function LoginPage() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const { login, register, isLoading, error } = useAuthStore();
  const navigate = useNavigate();

  const validationErrors: Record<string, string> = {};
  if (touched.email && !email.trim()) {
    validationErrors.email = 'Email обязателен';
  } else if (touched.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    validationErrors.email = 'Некорректный формат email';
  }
  if (touched.password && password.length < 8) {
    validationErrors.password = 'Минимум 8 символов';
  }
  if (isRegister && touched.fullName && !fullName.trim()) {
    validationErrors.fullName = 'Имя обязательно';
  }

  const isFormValid =
    email.trim() &&
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) &&
    password.length >= 8 &&
    (!isRegister || fullName.trim());

  const handleBlur = (field: string) => {
    setTouched((prev) => ({ ...prev, [field]: true }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTouched({ email: true, password: true, fullName: true });
    if (!isFormValid) return;

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
    <div className="login-wrapper">
      <div className="login-card">
        <h1 className="login-title">{'\u269B'} Tokamak Analysis</h1>
        <p className="login-subtitle">
          НИЯУ МИФИ — ИИ-система анализа данных токамаков
        </p>

        <form onSubmit={handleSubmit}>
          {isRegister && (
            <div className="form-group">
              <label>Полное имя</label>
              <input
                type="text"
                className={`form-input${validationErrors.fullName ? ' is-error' : ''}`}
                placeholder="Иванов Иван Иванович"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                onBlur={() => handleBlur('fullName')}
              />
              {validationErrors.fullName && (
                <div className="form-error">{validationErrors.fullName}</div>
              )}
            </div>
          )}

          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              className={`form-input${validationErrors.email ? ' is-error' : ''}`}
              placeholder="user@mephi.ru"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onBlur={() => handleBlur('email')}
            />
            {validationErrors.email && (
              <div className="form-error">{validationErrors.email}</div>
            )}
          </div>

          <div className="form-group">
            <label>Пароль</label>
            <div className="input-group">
              <input
                type={showPassword ? 'text' : 'password'}
                className={`form-input${validationErrors.password ? ' is-error' : ''}`}
                placeholder="Минимум 8 символов"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onBlur={() => handleBlur('password')}
              />
              <button
                type="button"
                className="input-group-append"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
                title={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
              >
                {showPassword ? '\u25C9' : '\u25CE'}
              </button>
            </div>
            {validationErrors.password && (
              <div className="form-error">{validationErrors.password}</div>
            )}
            {!validationErrors.password && touched.password && password.length >= 8 && (
              <div className="form-hint text-success">{'\u2713'} Пароль достаточно длинный</div>
            )}
          </div>

          {error && (
            <div className="mb-md text-danger text-sm">{error}</div>
          )}

          <button
            type="submit"
            className="btn btn-primary btn-lg w-full mb-md"
            disabled={isLoading}
          >
            {isLoading && <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />}
            {isLoading
              ? 'Загрузка...'
              : isRegister
              ? 'Зарегистрироваться'
              : 'Войти'}
          </button>
        </form>

        <button
          className="btn btn-ghost w-full text-sm"
          onClick={() => {
            setIsRegister(!isRegister);
            setTouched({});
          }}
        >
          {isRegister ? 'Уже есть аккаунт? Войти' : 'Нет аккаунта? Зарегистрироваться'}
        </button>
      </div>
    </div>
  );
}
