import { useEffect, useState } from 'react'
import LineStatsPage from './LineStatsPage.tsx'
import Search from './Search.tsx'

// Minimal hash routing: #/ = search, #/lines/<route_id> = line statistics.
function useHash(): string {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return hash
}

function App() {
  const hash = useHash()
  const line = /^#\/lines\/([^/]+)$/.exec(hash)

  return (
    <main>
      <h1>
        <a href="#/">Monitorizare întârzieri STB</a>
      </h1>
      {line ? <LineStatsPage key={line[1]} routeId={decodeURIComponent(line[1])} /> : <Search />}
    </main>
  )
}

export default App
