import useWebRTC from "../../hooks/useWebRTC";
import useSocket from "../../hooks/useSocket";

import QuestionPanel from "../../components/exam/QuestionPanel";
import Timer from "../../components/exam/Timer";
import WarningBanner from "../../components/exam/WarningBanner";

import RiskBar from "../../components/monitoring/RiskBar";
import StatusPanel from "../../components/monitoring/StatusPanel";
import Timeline from "../../components/monitoring/Timeline";

export default function Exam() {
  const { videoRef } = useWebRTC();
  const { risk, events, status } = useSocket();

  return (
    <div className="h-screen flex bg-black text-white">

      {/* LEFT SIDE */}
      <div className="w-3/4 p-6 flex flex-col">

        <div className="flex justify-between mb-4">
          <h1 className="text-xl">Exam</h1>
          <Timer />
        </div>

        <WarningBanner message={risk > 70 ? "High suspicious activity" : ""} />

        <div className="flex-1 mt-4">
          <QuestionPanel question="Explain Artificial Intelligence." />
        </div>
      </div>

      {/* RIGHT SIDE */}
      <div className="w-1/4 p-4 bg-white/10 backdrop-blur-lg">

        <video
          ref={videoRef}
          autoPlay
          className="rounded-xl mb-4 w-full"
        />

        <RiskBar score={risk} />

        <div className="mt-4">
          <StatusPanel status={status} />
        </div>

        <Timeline events={events} />
      </div>
    </div>
  );
}