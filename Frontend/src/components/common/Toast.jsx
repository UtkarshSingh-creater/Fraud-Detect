export default function Toast({ message }) {
  return (
    <div className="fixed top-4 right-4 bg-red-500 text-white px-4 py-2 rounded shadow">
      {message}
    </div>
  );
}