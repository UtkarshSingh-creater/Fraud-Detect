export default function Input({ placeholder, type = "text" }) {
  return (
    <input
      type={type}
      placeholder={placeholder}
      className="w-full p-2 bg-black/40 border border-white/10 rounded-lg text-white focus:outline-none"
    />
  );
}