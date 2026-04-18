export default function CandidateCard({ candidate }) {
  return (
    <div className="bg-white/10 p-4 rounded-xl">
      <h3>{candidate.name}</h3>
      <p>Risk: {candidate.risk}</p>
      <p>Status: {candidate.status}</p>
    </div>
  );
}