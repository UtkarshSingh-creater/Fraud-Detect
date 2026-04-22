export default function Button({ children, onClick, className }) {
  return (
    <button
      onClick={onClick}
      className={`bg-blue-600 hover:bg-blue-700 transition px-4 py-2 rounded-lg text-white ${className}`}
    >
      {children}
    </button>
  );
}