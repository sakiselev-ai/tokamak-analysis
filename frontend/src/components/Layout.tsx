import { Link, Outlet, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

export default function Layout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header
        style={{
          background: '#1a1a2e',
          color: '#fff',
          padding: '12px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <Link to="/" style={{ color: '#fff', textDecoration: 'none', fontSize: 18, fontWeight: 700 }}>
            Tokamak Analysis
          </Link>
          <nav style={{ display: 'flex', gap: 16 }}>
            <Link to="/" style={{ color: '#ccc', textDecoration: 'none' }}>
              Dashboard
            </Link>
            <Link to="/training" style={{ color: '#ccc', textDecoration: 'none' }}>
              Training
            </Link>
          </nav>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ color: '#aaa', fontSize: 14 }}>
            {user?.full_name} ({user?.role})
          </span>
          <button
            onClick={handleLogout}
            style={{
              background: 'transparent',
              border: '1px solid #666',
              color: '#ccc',
              padding: '4px 12px',
              borderRadius: 4,
              cursor: 'pointer',
            }}
          >
            Выйти
          </button>
        </div>
      </header>
      <main style={{ flex: 1, padding: 24, background: '#f5f5f5' }}>
        <Outlet />
      </main>
    </div>
  );
}
