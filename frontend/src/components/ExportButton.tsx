import { useState, useRef, useEffect } from 'react';

interface Props {
  experimentId: number;
}

export default function ExportButton({ experimentId }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleExport = (format: 'csv' | 'json') => {
    const token = localStorage.getItem('access_token');
    const url = `/api/v1/experiments/${experimentId}/export?format=${format}`;

    // Use a hidden link with auth header workaround via fetch + blob
    fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((res) => res.blob())
      .then((blob) => {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `experiment_${experimentId}.${format}`;
        a.click();
        URL.revokeObjectURL(a.href);
      })
      .catch(() => {
        // Fallback: direct navigation
        window.open(url, '_blank');
      });

    setOpen(false);
  };

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        className="btn btn-primary btn-sm"
        onClick={() => setOpen((v) => !v)}
        style={{ background: '#3498db' }}
      >
        Экспорт
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: 4,
            background: '#fff',
            border: '1px solid var(--color-border, #ddd)',
            borderRadius: 6,
            boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
            zIndex: 100,
            minWidth: 140,
            overflow: 'hidden',
          }}
        >
          <button
            onClick={() => handleExport('csv')}
            style={{
              display: 'block',
              width: '100%',
              padding: '10px 16px',
              border: 'none',
              background: 'none',
              textAlign: 'left',
              cursor: 'pointer',
              fontSize: 14,
            }}
            onMouseOver={(e) => (e.currentTarget.style.background = '#f5f5f5')}
            onMouseOut={(e) => (e.currentTarget.style.background = 'none')}
          >
            CSV
          </button>
          <button
            onClick={() => handleExport('json')}
            style={{
              display: 'block',
              width: '100%',
              padding: '10px 16px',
              border: 'none',
              background: 'none',
              textAlign: 'left',
              cursor: 'pointer',
              fontSize: 14,
            }}
            onMouseOver={(e) => (e.currentTarget.style.background = '#f5f5f5')}
            onMouseOut={(e) => (e.currentTarget.style.background = 'none')}
          >
            JSON
          </button>
        </div>
      )}
    </div>
  );
}
