import { Routes, Route } from "react-router-dom";
import { Dashboard } from "./pages/Dashboard";
import { WizardShell } from "./components/WizardShell";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/project/:uuid" element={<WizardShell />} />
      <Route path="/project/:uuid/step/:stepNumber" element={<WizardShell />} />
    </Routes>
  );
}

export default App;
