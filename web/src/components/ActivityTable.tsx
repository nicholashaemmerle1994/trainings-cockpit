import { fmtDate, fmtDuration, fmtKm, fmtPace, sportLabel } from "../format";
import type { Activity } from "../types";

export function ActivityTable({
  items,
  limit,
}: {
  items: Activity[];
  limit?: number;
}) {
  const rows = limit ? items.slice(0, limit) : items;

  return (
    <table className="list">
      <thead>
        <tr>
          <th className="col-date">Datum</th>
          <th>Einheit</th>
          <th className="r col-num">Dauer</th>
          <th className="r col-num hide-m">Strecke</th>
          <th className="r col-num">Belastung</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((activity) => (
          <tr key={`${activity.id}-${activity.start}`}>
            <td className="date">
              {fmtDate(activity.date, { weekday: "short", day: "numeric", month: "short" })}
            </td>
            <td>
              <span className="sport">{sportLabel(activity.sport)} · </span>
              {activity.name || activity.sport_label}
              {activity.pace_min_km ? (
                <span className="sport"> · {fmtPace(activity.pace_min_km)}</span>
              ) : null}
            </td>
            <td className="r num">{fmtDuration(activity.duration_min)}</td>
            <td className="r num hide-m">{fmtKm(activity.distance_km)}</td>
            <td className="r load">{activity.load == null ? "—" : Math.round(activity.load)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
