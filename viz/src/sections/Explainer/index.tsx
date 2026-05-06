import { useEffect, useState } from "react";
import HiddenTwinTest from "./HiddenTwinTest";
import FlowDiagram from "./FlowDiagram";
import RewardDecompose from "./RewardDecompose";
import LambdaChart from "./LambdaChart";
import NuPanel from "./NuPanel";
import DevnetDemo from "./DevnetDemo";
import { loadPosteriors } from "../../data/loaders";
import type { PosteriorSnapshot } from "../../data/types";
import styles from "./Explainer.module.css";

export default function Explainer() {
  const [posteriors, setPosteriors] = useState<PosteriorSnapshot[] | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPosteriors("S1", 0)
      .then(setPosteriors)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <section id="explainer" className="section">
      <div className="container">
        <div className="section-eyebrow">§1 — Explainer</div>
        <h1>Why PA-DCT works</h1>
        <p className="lede">
          Five providers. Three of them charge the same and run on the same
          base model. One is helpful, one is adversarial (fluent but wrong),
          one is flaky (40% timeout). A rule-based router cannot tell them
          apart. PA-DCT learns the difference from reward feedback alone.
        </p>

        <div className={styles.heroBlock}>
          {error && (
            <div className={styles.error}>
              Failed to load posteriors fixture: {error}
            </div>
          )}
          {!error && (
            <HiddenTwinTest snapshots={posteriors} />
          )}
        </div>

        <FlowDiagram />
        <RewardDecompose />
        <LambdaChart />
        <NuPanel />
        <DevnetDemo />
      </div>
    </section>
  );
}
