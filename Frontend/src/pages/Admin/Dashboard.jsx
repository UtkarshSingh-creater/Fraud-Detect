import CandidateList from "../../components/dashboard/CandidateList";
import RiskGraph from "../../components/dashboard/RiskGraph";

export default function Dashboard() {
  const candidates = [
    { name: "User 1", risk: 20, status: "Safe" },
    { name: "User 2", risk: 75, status: "Suspicious" },
  ];

  const graphData = [
    { time: 1, risk: 20 },
    { time: 2, risk: 50 },
    { time: 3, risk: 80 },
  ];

  return (
    <div className="p-6 text-white bg-black min-h-screen">

      <h1 className="text-2xl mb-6">Admin Dashboard</h1>

      <CandidateList candidates={candidates} />

      <div className="mt-8">
        <RiskGraph data={graphData} />
      </div>
    </div>
  );
}