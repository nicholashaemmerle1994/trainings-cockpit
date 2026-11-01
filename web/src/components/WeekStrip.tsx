const DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

function weekday(iso: string): string {
  const date = new Date(`${iso}T00:00:00`);
  return DAYS[(date.getDay() + 6) % 7];
}

export function WeekStrip({
  series,
  today,
}: {
  series: { date: string; load: number }[];
  today: string;
}) {
  const days = series.slice(-7);
  const peak = Math.max(...days.map((day) => day.load), 1);

  return (
    <div className="week-strip">
      <div className="week-bars">
        {days.map((day) => {
          const isToday = day.date === today;
          const isPeak = !isToday && day.load === peak && day.load > 0;
          const height = day.load > 0 ? Math.max(6, (day.load / peak) * 100) : 0;
          return (
            <i
              key={day.date}
              className={isToday ? "today" : isPeak ? "peak" : undefined}
              style={{ height: `${height}%` }}
              title={`${weekday(day.date)} ${Number(day.date.slice(8, 10))}: ${Math.round(day.load)} Belastung`}
            />
          );
        })}
      </div>
      <div className="week-days">
        {days.map((day) => (
          <span key={day.date} className={day.date === today ? "today" : undefined}>
            {weekday(day.date)} {Number(day.date.slice(8, 10))}
          </span>
        ))}
      </div>
    </div>
  );
}
