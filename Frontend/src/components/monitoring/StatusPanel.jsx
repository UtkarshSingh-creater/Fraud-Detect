export default function StatusPanel({ status }) {
  const Item = ({ label, value }) => (
    <div className="bg-white/10 p-2 rounded text-xs">
      <p className="text-gray-400">{label}</p>
      <p className="text-green-400">{value || "N/A"}</p>
    </div>
  );

  return (
    <div className="grid grid-cols-2 gap-2">
      <Item label="Face" value={status.face} />
      <Item label="Multi Face" value={status.multiFace} />
      <Item label="Eye Gaze" value={status.gaze} />
      <Item label="Head Pose" value={status.head} />
      <Item label="Audio" value={status.audio} />
      <Item label="Behavior" value={status.behavior} />
    </div>
  );
}