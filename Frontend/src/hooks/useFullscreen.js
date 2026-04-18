import { useEffect } from "react";

export default function useFullscreen() {
  useEffect(() => {
    document.documentElement.requestFullscreen();

    const handleVisibility = () => {
      if (document.hidden) {
        alert("⚠️ Tab switch detected!");
      }
    };

    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, []);
}