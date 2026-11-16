// Line number on its route colour from the timetable (e.g. red for trams).
function LineBadge({ number, color }: { number: string; color: string | null }) {
  return (
    <span className="badge" style={color ? { background: `#${color}` } : undefined}>
      {number}
    </span>
  )
}

export default LineBadge
