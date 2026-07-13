/** Soft animated gradient blobs behind everything — the app's warmth. */
export function AuroraBackground() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-brand-50 via-background to-accent/60" />
      <div className="absolute -top-32 -left-32 h-[55vmax] w-[55vmax] rounded-full bg-brand-200/50 blur-3xl animate-aurora" />
      <div
        className="absolute -right-40 top-1/4 h-[45vmax] w-[45vmax] rounded-full bg-sun-300/40 blur-3xl animate-aurora"
        style={{ animationDuration: '18s', animationDelay: '-6s' }}
      />
      <div
        className="absolute -bottom-40 left-1/4 h-[40vmax] w-[40vmax] rounded-full bg-brand-300/30 blur-3xl animate-aurora"
        style={{ animationDuration: '22s', animationDelay: '-12s' }}
      />
    </div>
  );
}
