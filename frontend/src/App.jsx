import { useState } from "react";
import Encargos from "./vistas/Encargos";
import Encargo from "./vistas/Encargo";

export default function App() {
  const [encargoId, setEncargoId] = useState(null);
  return encargoId
    ? <Encargo encargoId={encargoId} onVolver={() => setEncargoId(null)} />
    : <Encargos onAbrir={setEncargoId} />;
}
