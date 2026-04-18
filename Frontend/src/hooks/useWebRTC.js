import { useEffect, useRef } from "react";

export default function useWebRTC() {
  const videoRef = useRef();

  useEffect(() => {
    const start = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: true,
        });
        videoRef.current.srcObject = stream;
      } catch (err) {
        console.error("Camera access denied", err);
      }
    };

    start();
  }, []);

  return { videoRef };
}