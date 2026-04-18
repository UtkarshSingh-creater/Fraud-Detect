export default function GlassCard({ children }) {
  return (
    <div className="bg-white/10 backdrop-blur-lg border border-white/20 rounded-2xl p-4 shadow-xl">
      {children}
    </div>
  );
}