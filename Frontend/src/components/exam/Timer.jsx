import { useEffect, useState } from "react";

export default function Timer({ duration = 600 }) {
  const [time, setTime] = useState(duration);

  useEffect(() => {
    const interval = setInterval(() => {
      setTime((t) => t - 1);
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="text-lg font-bold">
      ⏱ {Math.floor(time / 60)}:{time % 60}
    </div>
  );
}