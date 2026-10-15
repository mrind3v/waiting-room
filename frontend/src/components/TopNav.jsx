import { NavLink } from 'react-router-dom'

const links = [
  ['/', 'Board', '◫'],
  ['/schedule', 'Schedule', '▤'],
  ['/patients', 'Patients', '☺'],
  ['/doctors', 'Doctors', '✚'],
]

export default function TopNav() {
  return (
    <header className="topnav">
      <div className="brand">
        <span className="brand-mark" aria-hidden>
          ✚
        </span>
        <span>
          Waiting Room <small>clinic front desk</small>
        </span>
      </div>
      <nav className="navlinks" aria-label="Main">
        {links.map(([to, label, icon]) => (
          <NavLink key={to} to={to} end={to === '/'} className="navlink">
            <span aria-hidden>{icon}</span>
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </header>
  )
}
