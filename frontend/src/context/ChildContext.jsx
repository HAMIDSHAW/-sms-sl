import { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from './AuthContext'

const ChildContext = createContext(null)

export function ChildProvider({ children }) {
  const { user, hasRole } = useAuth()
  const [myChildren, setMyChildren] = useState([])
  const [selectedChildId, setSelectedChildId] = useState(null)

  useEffect(() => {
    if (!user || !hasRole('parent')) {
      setMyChildren([])
      setSelectedChildId(null)
      return
    }
    api.get('/api/students/my-children').then((kids) => {
      setMyChildren(kids)
      const saved = localStorage.getItem('selected_child_id')
      const initial = kids.find((k) => k.id === saved) || kids[0]
      if (initial) {
        api.setChildScope(initial.id)
        setSelectedChildId(initial.id)
      }
    })
  }, [user])

  // Choosing a child changes what every page loads, so reload the current page's
  // data by remounting through a full navigation to the same place.
  const chooseChild = (id) => {
    api.setChildScope(id)
    localStorage.setItem('selected_child_id', id)
    setSelectedChildId(id)
  }

  return (
    <ChildContext.Provider value={{ myChildren, selectedChildId, setSelectedChildId: chooseChild, selectedChild: myChildren.find((k) => k.id === selectedChildId) || null }}>
      {children}
    </ChildContext.Provider>
  )
}

export function useChildSelection() {
  return useContext(ChildContext)
}
