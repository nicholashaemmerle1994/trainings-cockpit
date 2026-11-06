type IconProps = { size?: number; className?: string };

function svgProps(size: number) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
}

export function IconToday({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <path d="M4 10.6 12 4l8 6.6V20a1 1 0 0 1-1 1h-4.6v-6.2H9.6V21H5a1 1 0 0 1-1-1z" />
    </svg>
  );
}

export function IconTrends({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <path d="M3 17.5 9 11l4 3.6L21 6.5" />
      <path d="M15.5 6.5H21v5.2" />
    </svg>
  );
}

export function IconList({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <path d="M8 6h13M8 12h13M8 18h13" />
      <circle cx="3.6" cy="6" r="1" fill="currentColor" stroke="none" />
      <circle cx="3.6" cy="12" r="1" fill="currentColor" stroke="none" />
      <circle cx="3.6" cy="18" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function IconCalendar({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <rect x="3.5" y="5" width="17" height="15.5" rx="2.5" />
      <path d="M7.5 3v4M16.5 3v4M3.5 9.5h17" />
      <path d="M8 13h2M14 13h2M8 17h2M14 17h2" />
    </svg>
  );
}

export function IconFuel({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <path d="M9.2 3h5.6v3.4l1.4 2.3V19a2 2 0 0 1-2 2h-4.4a2 2 0 0 1-2-2V8.7l1.4-2.3z" />
      <path d="M9.2 8.7h5.6" />
      <path d="M10 14.5h4" />
    </svg>
  );
}

export function IconSync({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <path d="M20 11a8 8 0 0 0-14-4.5L4 9" />
      <path d="M4 4v5h5" />
      <path d="M4 13a8 8 0 0 0 14 4.5L20 15" />
      <path d="M20 20v-5h-5" />
    </svg>
  );
}

export function IconRun({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <circle cx="14.5" cy="4.2" r="1.7" />
      <path d="M13.4 7.4 10 11.2l3.2 2.3-2.1 5.2" />
      <path d="M13.4 7.4l4 1.9 1.8 3.1" />
      <path d="M10 11.2 5.8 12.4" />
    </svg>
  );
}

export function IconBike({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <circle cx="5.8" cy="17.2" r="3.2" />
      <circle cx="18.2" cy="17.2" r="3.2" />
      <path d="M5.8 17.2 9.4 9h4.2l4.6 8.2" />
      <path d="M9.4 9h5.6" />
      <path d="M12.2 9l-1.4 8.2" />
    </svg>
  );
}

export function IconSwim({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <path d="M3 9.5c1.6-1.4 3.1-1.4 4.7 0s3.1 1.4 4.7 0 3.1-1.4 4.7 0 2.3 1.1 3.9.2" />
      <path d="M3 14c1.6-1.4 3.1-1.4 4.7 0s3.1 1.4 4.7 0 3.1-1.4 4.7 0 2.3 1.1 3.9.2" />
      <path d="M3 18.5c1.6-1.4 3.1-1.4 4.7 0s3.1 1.4 4.7 0 3.1-1.4 4.7 0 2.3 1.1 3.9.2" />
    </svg>
  );
}

export function IconWeights({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <path d="M4 9v6M7 7v10M17 7v10M20 9v6" />
      <path d="M7 12h10" />
    </svg>
  );
}

/** Pulslinie: der ruhige Moment in der Mitte des Erholungsrings. */
export function IconPulse({ size = 24, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <path d="M2 12h4.4l2.4-6.8 4.4 13.6 2.4-6.8H22" />
    </svg>
  );
}

export function IconBolt({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <path d="M13 3 6 13.5h5L10.5 21 18 10.5h-5z" />
    </svg>
  );
}

export function SportIcon({ sport, size = 18 }: { sport: string; size?: number }) {
  if (sport === "Run" || sport === "VirtualRun") return <IconRun size={size} />;
  if (sport === "Ride" || sport === "VirtualRide") return <IconBike size={size} />;
  if (sport === "Swim" || sport === "OpenWaterSwim") return <IconSwim size={size} />;
  if (sport === "WeightTraining") return <IconWeights size={size} />;
  return <IconBolt size={size} />;
}

export function IconBack({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <path d="M19 12H5" />
      <path d="m12 19-7-7 7-7" />
    </svg>
  );
}

export function IconForward({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <path d="M5 12h14" />
      <path d="m12 5 7 7-7 7" />
    </svg>
  );
}

export function IconPlus({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function IconClose({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  );
}
