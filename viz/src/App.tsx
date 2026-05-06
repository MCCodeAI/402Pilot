import DisclaimerBanner from "./components/DisclaimerBanner";
import Header from "./components/Header";
import Explainer from "./sections/Explainer";
import Simulation from "./sections/Simulation";
import Results from "./sections/Results";
import "./styles/app.css";

export default function App() {
  return (
    <div className="app">
      <Header />
      <DisclaimerBanner />
      <main>
        <Explainer />
        <Simulation />
        <Results />
      </main>
      <footer className="footer">
        <div className="container">
          <p>
            402Pilot — Interactive Explainer · companion to the paper
            "Learning What to Pay For in Agent Micropayment Markets."
          </p>
          <p className="footer-meta">
            Method: <strong>PA-DCT</strong> (Payment-Aware Discounted
            Contextual Thompson sampling). Code:{" "}
            <a href="https://github.com/MCCodeAI/402Pilot">
              github.com/MCCodeAI/402Pilot
            </a>
            .
          </p>
        </div>
      </footer>
    </div>
  );
}
