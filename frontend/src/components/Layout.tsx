import { NavLink, Outlet } from "react-router-dom";

export function Layout() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-mark">LM</div>
        <div>
          <div className="brand-title">Local Meeting Notes</div>
          <div className="brand-subtitle">Private transcription workspace</div>
        </div>
        <nav className="topnav" aria-label="Primary navigation">
          <NavLink to="/" end>Meetings</NavLink>
          <NavLink className="button button-small" to="/new">New meeting</NavLink>
        </nav>
      </header>
      <div className="privacy-banner"><span className="status-dot" /> Local processing only · Audio and transcripts stay on this computer</div>
      <main className="page-wrap"><Outlet /></main>
    </div>
  );
}
