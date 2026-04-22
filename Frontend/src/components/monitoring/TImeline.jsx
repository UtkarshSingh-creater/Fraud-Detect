import { motion } from "framer-motion";

export default function Timeline({ events }) {
  return (
    <div className="mt-4 max-h-60 overflow-y-auto space-y-2">
      {events.map((e, i) => (
        <motion.div
          key={i}
          className="bg-white/10 p-2 rounded cursor-pointer"
          whileHover={{ scale: 1.02 }}
        >
          <p className="text-sm">{e.message}</p>
          <p className="text-xs text-gray-400">{e.time}</p>
        </motion.div>
      ))}
    </div>
  );
}