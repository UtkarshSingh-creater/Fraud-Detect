export default function QuestionPanel({ question }) {
  return (
    <div className="bg-white/10 p-4 rounded-xl h-full">
      <h2 className="text-lg mb-4">Question</h2>
      <p>{question}</p>
    </div>
  );
}