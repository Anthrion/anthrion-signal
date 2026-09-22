import type { Signal } from './types'
import { isAvailableOpportunity } from './lib'

export function RecommendedApproach({ signal }: { signal: Signal }) {
  const guidance = signal.reviewed_guidance
  if (!guidance || !signal.countries.includes('GB') || !isAvailableOpportunity(signal)) return null
  const paragraphs = (points: typeof guidance.approach) =>
    points.map((point, index) => (
      <p key={index}>
        {point.lot_id && <strong>Lot {point.lot_id.replace(/^LOT[- ]?/i, '')}: </strong>}
        {point.text}
      </p>
    ))
  return (
    <section className="recommended-approach" aria-label="Recommended approach">
      <h3>Recommended approach:</h3>
      {paragraphs(guidance.approach)}
      {!!guidance.problems.length && (
        <div className="approach-problems">
          <h3>Problems:</h3>
          {paragraphs(guidance.problems)}
        </div>
      )}
    </section>
  )
}
