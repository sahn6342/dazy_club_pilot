const COLORS: Record<string, string> = {
  new: "#d8b456",
  pending: "#d8b456",
  handled: "#61d394",
  confirmed: "#61d394",
  cancelled: "#ff6b6b",
  approved: "#61d394",
  rejected: "#ff6b6b",
};

export function StatusBadge({ status }: { status: string }) {
  const color = COLORS[status] ?? "#a7a9b1";
  return (
    <span
      style={{
        display: "inline-block",
        padding: "0.2rem 0.6rem",
        borderRadius: "999px",
        fontSize: "0.75rem",
        fontWeight: 800,
        color,
        border: `1px solid ${color}`,
        background: `${color}18`,
        textTransform: "capitalize",
      }}
    >
      {status}
    </span>
  );
}
