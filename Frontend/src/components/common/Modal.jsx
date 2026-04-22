export default function Modal({ children, isOpen }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center">
      <div className="bg-white/10 backdrop-blur-lg p-6 rounded-xl">
        {children}
      </div>
    </div>
  );
}