import { IconBike, IconBolt, IconRun, IconSwim, IconWeights } from "./icons";

/** Ein Symbol je Sportart — an einer Stelle, weil Liste und Blatt dasselbe zeigen. */
const SPORT_ICONS: Record<string, typeof IconRun> = {
  Ride: IconBike,
  VirtualRide: IconBike,
  EBikeRide: IconBike,
  GravelRide: IconBike,
  MountainBikeRide: IconBike,
  Run: IconRun,
  VirtualRun: IconRun,
  TrailRun: IconRun,
  Swim: IconSwim,
  OpenWaterSwim: IconSwim,
  WeightTraining: IconWeights,
};

export function sportIcon(sport: string): typeof IconRun {
  return SPORT_ICONS[sport] ?? IconBolt;
}
