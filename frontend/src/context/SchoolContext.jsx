import { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from './AuthContext'

const SchoolContext = createContext(null)

export function SchoolProvider({ children }) {
  const { user } = useAuth()
  const [school, setSchool] = useState(null)

  useEffect(() => {
    if (!user) {
      setSchool(null)
      return
    }
    api.get('/api/school').then(setSchool).catch(() => setSchool(null))
  }, [user])

  return <SchoolContext.Provider value={{ school, setSchool }}>{children}</SchoolContext.Provider>
}

export function useSchool() {
  return useContext(SchoolContext)
}
