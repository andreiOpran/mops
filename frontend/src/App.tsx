import { useEffect, useState } from 'react'

type Health = { status: string; database: string }

function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((response) => response.json() as Promise<Health>)
      .then(setHealth)
      .catch((err: Error) => setError(err.message))
  }, [])

  return (
    <main>
      <h1>Monitorizare întârzieri STB</h1>
      <p>
        Backend:{' '}
        {error ? `indisponibil (${error})` : health ? `${health.status}, baza de date: ${health.database}` : 'se verifică...'}
      </p>
    </main>
  )
}

export default App
