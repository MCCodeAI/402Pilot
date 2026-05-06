export default function Header() {
  return (
    <header className="header">
      <div className="container header-inner">
        <div className="brand">
          <span className="brand-name">402Pilot</span>
          <span className="brand-sub">Interactive Explainer</span>
        </div>
        <nav className="nav">
          <a href="#explainer">Explainer</a>
          <a href="#simulation">Simulation</a>
          <a href="#results">Results</a>
        </nav>
      </div>
    </header>
  );
}
