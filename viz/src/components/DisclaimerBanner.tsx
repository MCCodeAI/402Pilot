import styles from "./DisclaimerBanner.module.css";

/**
 * Persistent disclaimer banner under the header.
 *
 * Required by `docs/code_structure.md`: makes the experimental boundary
 * explicit so reviewers do not mistake replayed runs for live transactions.
 */
export default function DisclaimerBanner() {
  return (
    <div className={styles.banner}>
      <div className="container">
        <span className={styles.tag}>scope</span>
        <span className={styles.text}>
          Experiments: 10,000 rounds × 30 seeds × 3 scenarios, fully replayed
          from fixtures. Mock wallet. x402 settlement boundary preserved at
          the executor layer; no public testnet.
        </span>
      </div>
    </div>
  );
}
