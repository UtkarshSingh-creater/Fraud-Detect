export default function SessionPlayback({ events }) {
  return (
    <div className="bg-white/10 p-4 rounded-xl">
      <h2 className="mb-2">Session Playback</h2>
      {events.map((e, i) => (
        <div key={i} className="text-sm">
          {e.message}
        </div>
      ))}
    </div>
  );
}