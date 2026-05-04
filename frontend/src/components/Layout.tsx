import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

export default function Layout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="app-layout">

      <header className="app-header">
        <div className="flex items-center gap-lg">
          <Link to="/" className="app-logo">
            <span>{'\u269B'}</span>
            Tokamak Analysis
          </Link>
          <nav className="app-nav">
            <NavLink to="/" end>
              <span>{'\u25A3'}</span> Dashboard
            </NavLink>
            <NavLink to="/training">
              <span>{'\u2699'}</span> Training
            </NavLink>
          </nav>
        </div>
        <div className="app-header-right">
          <span className="app-user-info">
            {user?.full_name} ({user?.role})
          </span>
          <button className="btn btn-outline btn-sm" onClick={handleLogout}
            style={{ color: 'rgba(255,255,255,0.7)', borderColor: 'rgba(255,255,255,0.25)' }}>
            Выйти
          </button>
        </div>
      </header>

      <div className="app-body">
        <aside className="app-sidebar">
          <div className="sidebar-section">
            <div className="sidebar-section-title">Навигация</div>
            <nav className="sidebar-nav">
              <NavLink to="/" end>
                <span className="sidebar-icon">{'\u25A3'}</span>
                Dashboard
              </NavLink>
              <NavLink to="/training">
                <span className="sidebar-icon">{'\u2699'}</span>
                Обучение
              </NavLink>
            </nav>
          </div>

          <div className="sidebar-section">
            <div className="sidebar-section-title">Анализ</div>
            <nav className="sidebar-nav">
              <NavLink to="/" end>
                <span className="sidebar-icon">{'\u26A1'}</span>
                Эксперименты
              </NavLink>
            </nav>
          </div>

          <div className="sidebar-section">
            <div className="sidebar-section-title">Аккаунт</div>
            <nav className="sidebar-nav">
              <a href="#" onClick={(e) => { e.preventDefault(); handleLogout(); }}>
                <span className="sidebar-icon">{'\u2192'}</span>
                Выйти
              </a>
            </nav>
          </div>
        </aside>

        <main className="app-main">
          <Outlet />
        </main>
      </div>

      <footer className="app-footer">
        &copy; НИЯУ МИФИ 2026 — Платформа анализа данных токамаков
      </footer>
    </div>
  );
}
