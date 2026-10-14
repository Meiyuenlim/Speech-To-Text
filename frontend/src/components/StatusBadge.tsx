import { stageLabels } from "../types";

export function StatusBadge({ status }: { status: string }) {
  return <span className={`status-badge status-${status}`}><span className="status-dot" />{stageLabels[status] ?? status}</span>;
}
