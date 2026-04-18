import { useNavigate } from "react-router-dom";
import LoginCard from "../../components/auth/LoginCard";

export default function Login() {
  const navigate = useNavigate();

  const handleLogin = () => {
    // temporary logic
    navigate("/exam");
  };

  return (
    <div className="h-screen flex items-center justify-center bg-gradient-to-br from-black to-gray-900">
      <LoginCard onLogin={handleLogin} />
    </div>
  );
}