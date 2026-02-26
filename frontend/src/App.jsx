import { Routes, Route, Link } from "react-router-dom";
import SurveyPage from "./pages/SurveyPage";
import AdminPage from "./pages/AdminPage";

function App() {
  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-content">
          <Link to="/" className="logo">
            <h1>Pew Research Center</h1>
          </Link>
          <nav className="header-nav">
            <Link to="/">Survey</Link>
            <Link to="/admin">Admin</Link>
          </nav>
        </div>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<SurveyPage />} />
          <Route path="/admin" element={<AdminPage />} />
        </Routes>
      </main>
      <footer className="app-footer">
        <p>&copy; 2026 Pew Research Center. The Lowkey Team - Proof of Concept.</p>
      </footer>
    </div>
  );
}

export default App;
