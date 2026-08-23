/**
 * Atmosphere layers: static grain + static scanlines + static vignette,
 * optional slow hero sweep. Purely presentational — aria-hidden, sits at
 * z-0 below content. Parent must be `.mkt-layered` so children render above.
 */
export function NoiseLayer({ sweep = false }: { sweep?: boolean }) {
  return (
    <div aria-hidden="true" className="mkt-noise">
      <span className="mkt-noise__grain" />
      <span className="mkt-noise__scanlines" />
      <span className="mkt-noise__vignette" />
      {sweep && <span className="mkt-noise__sweep" />}
    </div>
  );
}
