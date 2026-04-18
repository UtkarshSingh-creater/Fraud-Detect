import { motion } from "framer-motion";

export default function DraggableVideo({ videoRef }) {
  return (
    <motion.video
      ref={videoRef}
      autoPlay
      drag
      className="fixed bottom-4 right-4 w-48 rounded-xl shadow-lg cursor-move"
    />
  );
}