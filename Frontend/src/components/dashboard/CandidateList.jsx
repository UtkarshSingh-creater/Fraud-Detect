import CandidateCard from "./CandidateCard";

export default function CandidateList({ candidates }) {
  return (
    <div className="grid grid-cols-3 gap-4">
      {candidates.map((c, i) => (
        <CandidateCard key={i} candidate={c} />
      ))}
    </div>
  );
}