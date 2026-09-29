import { Link } from "react-router-dom";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

export default function NotFound() {
  useDocumentTitle("Not found");
  return (
    <div className="grid place-items-center py-24 text-center">
      <p className="eyebrow">404</p>
      <h1 className="mt-3 font-display text-5xl font-bold tracking-tight">Cut. That scene doesn't exist.</h1>
      <p className="mt-3 text-muted">The page you're looking for isn't on the timeline.</p>
      <Link to="/" className="btn-primary mt-8">Back to a new mine</Link>
    </div>
  );
}
