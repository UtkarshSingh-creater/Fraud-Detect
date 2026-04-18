export default function FullscreenPrompt({ onEnter }) {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black text-white">
      <div className="text-center">
        <h1 className="mb-4">Enter Fullscreen to Start Exam</h1>
        <button
          onClick={onEnter}
          className="bg-blue-500 px-4 py-2 rounded"
        >
          Start
        </button>
      </div>
    </div>
  );
}