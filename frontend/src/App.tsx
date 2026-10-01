import './App.css'
import { ProfilesPage } from './features/profiles/ProfilesPage'
import { VacanciesPage } from './features/vacancies/VacanciesPage'

function App() {
  if (window.location.pathname === '/app/profiles') {
    return <ProfilesPage />
  }

  return <VacanciesPage />
}

export default App
