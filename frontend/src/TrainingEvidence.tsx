import report from '../../examples/ml/uci-beijing-training-report.json';

export default function TrainingEvidence(){
  const scores=report.metrics.test;
  return <details className="training-evidence"><summary>Completed local training evaluation</summary>
    <p>Real Beijing history · {report.input_records.toLocaleString()} records. Test cohort: {scores.persistence.overall.sample_count.toLocaleString()} next-hour samples.</p>
    <table><caption>Held-out error, µg/m³</caption><thead><tr><th scope="col">Model</th><th scope="col">MAE</th><th scope="col">RMSE</th></tr></thead><tbody>
      <tr><th scope="row">Persistence</th><td>{scores.persistence.overall.mae.toFixed(2)}</td><td>{scores.persistence.overall.rmse.toFixed(2)}</td></tr>
      <tr><th scope="row">Random Forest</th><td>{scores.random_forest.overall.mae.toFixed(2)}</td><td>{scores.random_forest.overall.rmse.toFixed(2)}</td></tr>
      <tr><th scope="row">Gradient boosting</th><td>{scores.hist_gradient_boosting.overall.mae.toFixed(2)}</td><td>{scores.hist_gradient_boosting.overall.rmse.toFixed(2)}</td></tr>
    </tbody></table>
    <p>Experimental local CPU result. No SageMaker training job has run. This model is excluded from Delhi navigation; source availability delays and Delhi performance are unvalidated.</p>
    <a href={report.dataset_source} target="_blank" rel="noreferrer">UCI source · CC BY 4.0</a>
  </details>;
}
