export default function WarningBanner({ message }) {
  if (!message) return null;

  return (
    <div className="bg-red-600 text-white p-2 text-center rounded">
      ⚠️ {message}
    </div>
  );
}