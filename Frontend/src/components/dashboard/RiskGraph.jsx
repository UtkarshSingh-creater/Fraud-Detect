import { LineChart, Line, XAxis, YAxis } from "recharts";

export default function RiskGraph({ data }) {
  return (
    <LineChart width={400} height={300} data={data}>
      <XAxis dataKey="time" />
      <YAxis />
      <Line dataKey="risk" stroke="#ff4d4f" />
    </LineChart>
  );
}