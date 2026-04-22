import { motion } from "framer-motion";
import Input from "../common/Input";
import Button from "../common/Button";

export default function LoginCard({ onLogin }) {
  return (
    <motion.div
      className="bg-white/10 backdrop-blur-lg p-8 rounded-2xl w-96 text-white"
      initial={{ opacity: 0, y: 40 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <h2 className="text-2xl mb-6 font-semibold">Login</h2>

      <Input placeholder="Email" />
      <div className="h-3" />
      <Input placeholder="Password" type="password" />

      <div className="h-5" />

      <Button onClick={onLogin} className="w-full">
        Login
      </Button>
    </motion.div>
  );
}