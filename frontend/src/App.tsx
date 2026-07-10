import { useEffect, useState } from 'react';
import { getHealth } from './api';
import './App.css';

function App() {
  const [backendUp, setBackendUp] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function checkHealth() {
      try {
        await getHealth();
        if (!cancelled) setBackendUp(true);
      } catch {
        if (!cancelled) setBackendUp(false);
      }
    }

    checkHealth();
    const interval = setInterval(checkHealth, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="kiosk">
      <span
        className={`status-dot ${backendUp ? 'status-dot--up' : 'status-dot--down'}`}
        aria-label={backendUp ? 'Backend connected' : 'Backend unreachable'}
      />

      <section className="content-area">
        <div className="placeholder-illustration" role="img" aria-label="Mentor waiting to talk">
          🌼
        </div>
      </section>

      <section className="talk-area">
        <p className="status-line">ready</p>
        <button type="button" className="talk-button" aria-label="Hold to talk">
          🎤
        </button>
      </section>
    </div>
  );
}

export default App;
