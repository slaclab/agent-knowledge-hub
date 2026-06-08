export function togglePlatform(active: string[], platform: string): string[] {
  return active.includes(platform)
    ? active.filter((p) => p !== platform)
    : [...active, platform];
}

export function buildPlatformsParam(platforms: string[]): string | null {
  return platforms.length > 0 ? platforms.join(",") : null;
}
