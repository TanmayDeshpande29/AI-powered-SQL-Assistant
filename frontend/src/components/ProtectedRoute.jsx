import { Navigate, Outlet, useLocation } from "react-router"
import { isLoggedIn } from "../lib/api"

// Layout route: renders the child page (<Outlet />) only when a token exists,
// otherwise redirects to /login and remembers where the user was going.
// This is a UX guard only. Real security is the backend rejecting bad tokens with 401.
export default function ProtectedRoute() {
  const location = useLocation()
  if (!isLoggedIn()) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}
