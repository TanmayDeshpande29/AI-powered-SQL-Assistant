import './App.css'
import LandingPage from './landingPage'
import { BrowserRouter, Routes, Route } from "react-router";
import LoginPage from "./loginPage";
import ContactPage from './site/contact';
import SignupPage from './signUpPage';
import QueryBuilderMainPage from './queryBuilder';
import DatabaseSetupPage from './DatabaseSetup';
import SQLAssistantsPage from './sql_assistants';
import AccountPage from './user_account';
import SettingsPage from './user_settings';
import DashboardOverview from './user_dashboard';
import ProtectedRoute from './components/ProtectedRoute';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public pages */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/platform" element={<h1>Platform Page</h1>} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/pricing" element={<div>Pricing Page</div>} />
        <Route path="/contact" element={<ContactPage />} />
        <Route path="/blog" element={<div>Blog Page</div>} />

        {/* App pages: only reachable when logged in */}
        <Route element={<ProtectedRoute />}>
          <Route path="/querybuilder" element={<QueryBuilderMainPage />} />
          <Route path="/database-setup" element={<DatabaseSetupPage />} />
          <Route path="/sql-assistants" element={<SQLAssistantsPage />} />
          <Route path="/account" element={<AccountPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/user-dashboard" element={<DashboardOverview />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
