import { motion } from "framer-motion";

export default function RiskBar({ score }) {
  return (
    <div>
      <p>Risk: {score}</p>
      <div className="w-full bg-gray-700 h-4 rounded">
        <motion.div
          className="bg-red-500 h-4 rounded"
          animate={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
}