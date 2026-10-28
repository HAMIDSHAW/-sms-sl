import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { SchoolProvider } from './context/SchoolContext'
import { ChildProvider } from './context/ChildContext'
import ProtectedRoute from './components/ProtectedRoute'
import RequirePermission from './components/RequirePermission'
import AppShell from './components/layout/AppShell'
import Login from './pages/auth/Login'
import ForgotPassword from './pages/auth/ForgotPassword'

// Each page is its own downloadable chunk, so a phone on a slow connection only fetches the screen it opens.
const ActivityLog = lazy(() => import('./pages/activity/ActivityLog'))
const NotFound = lazy(() => import('./pages/NotFound'))
const ChangePassword = lazy(() => import('./pages/auth/ChangePassword'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const StudentsList = lazy(() => import('./pages/students/StudentsList'))
const StudentProfile = lazy(() => import('./pages/students/StudentProfile'))
const StaffList = lazy(() => import('./pages/staff/StaffList'))
const GuardiansList = lazy(() => import('./pages/guardians/GuardiansList'))
const GuardianProfile = lazy(() => import('./pages/guardians/GuardianProfile'))
const AcademicsAdmin = lazy(() => import('./pages/academics/AcademicsAdmin'))
const MarkAttendance = lazy(() => import('./pages/attendance/MarkAttendance'))
const TimetableView = lazy(() => import('./pages/timetable/TimetableView'))
const AssignmentsList = lazy(() => import('./pages/assignments/AssignmentsList'))
const AssignmentDetail = lazy(() => import('./pages/assignments/AssignmentDetail'))
const MaterialsList = lazy(() => import('./pages/materials/MaterialsList'))
const ExamsList = lazy(() => import('./pages/exams/ExamsList'))
const ResultsForExam = lazy(() => import('./pages/exams/ResultsForExam'))
const ReportCard = lazy(() => import('./pages/exams/ReportCard'))
const FinanceOverview = lazy(() => import('./pages/finance/FinanceOverview'))
const StudentLedger = lazy(() => import('./pages/finance/StudentLedger'))
const MessagesInbox = lazy(() => import('./pages/messages/MessagesInbox'))
const Announcements = lazy(() => import('./pages/announcements/Announcements'))
const Discipline = lazy(() => import('./pages/discipline/Discipline'))
const LibraryPage = lazy(() => import('./pages/library/Library'))
const Analytics = lazy(() => import('./pages/analytics/Analytics'))
const Inventory = lazy(() => import('./pages/inventory/Inventory'))
const Profile = lazy(() => import('./pages/Profile'))
const Transport = lazy(() => import('./pages/transport/Transport'))
const DriverProfile = lazy(() => import('./pages/transport/DriverProfile'))
const PlatformAdmin = lazy(() => import('./pages/PlatformAdmin'))
const HR = lazy(() => import('./pages/hr/HR'))
const Settings = lazy(() => import('./pages/Settings'))

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <SchoolProvider>
        <ChildProvider>
          <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-sm text-slate" role="status">Loading...</div>}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route
              path="/change-password"
              element={
                <ProtectedRoute>
                  <ChangePassword />
                </ProtectedRoute>
              }
            />

            <Route
              path="/platform"
              element={
                <ProtectedRoute>
                  <PlatformAdmin />
                </ProtectedRoute>
              }
            />

            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <AppShell />
                </ProtectedRoute>
              }
            >
              <Route index element={<Dashboard />} />
              <Route path="students" element={<RequirePermission perm="students.view"><StudentsList /></RequirePermission>} />
              <Route path="students/:id" element={<RequirePermission perm="students.view"><StudentProfile /></RequirePermission>} />
              <Route path="staff" element={<RequirePermission perm="staff.view"><StaffList /></RequirePermission>} />
              <Route path="guardians" element={<RequirePermission perm="parents.view" orClassMaster><GuardiansList /></RequirePermission>} />
              <Route path="guardians/:id" element={<RequirePermission perm="parents.view" orClassMaster><GuardianProfile /></RequirePermission>} />
              <Route path="academics" element={<RequirePermission perm="academics.manage"><AcademicsAdmin /></RequirePermission>} />
              <Route path="attendance" element={<RequirePermission perm="attendance.view"><MarkAttendance /></RequirePermission>} />
              <Route path="timetable" element={<RequirePermission perm="timetable.view"><TimetableView /></RequirePermission>} />
              <Route path="assignments" element={<RequirePermission perm="assignments.view"><AssignmentsList /></RequirePermission>} />
              <Route path="assignments/:id" element={<RequirePermission perm="assignments.view"><AssignmentDetail /></RequirePermission>} />
              <Route path="materials" element={<RequirePermission perm="materials.view"><MaterialsList /></RequirePermission>} />
              <Route path="exams" element={<RequirePermission perm="exams.view"><ExamsList /></RequirePermission>} />
              <Route path="exams/:examId/results" element={<RequirePermission perm="exams.view"><ResultsForExam /></RequirePermission>} />
              <Route path="exams/:examId/report-card/:studentId" element={<RequirePermission perm="exams.view"><ReportCard /></RequirePermission>} />
              <Route path="finance" element={<RequirePermission perm="finance.view"><FinanceOverview /></RequirePermission>} />
              <Route path="finance/ledger/:studentId" element={<RequirePermission perm="finance.view"><StudentLedger /></RequirePermission>} />
              <Route path="messages" element={<MessagesInbox />} />
              <Route path="announcements" element={<Announcements />} />
              <Route path="discipline" element={<RequirePermission perm="discipline.view"><Discipline /></RequirePermission>} />
              <Route path="library" element={<RequirePermission perm="library.view"><LibraryPage /></RequirePermission>} />
              <Route path="analytics" element={<RequirePermission perm="analytics.view"><Analytics /></RequirePermission>} />
              <Route path="inventory" element={<RequirePermission perm="inventory.view"><Inventory /></RequirePermission>} />
              <Route path="profile" element={<Profile />} />
              <Route path="transport" element={<RequirePermission perm="transport.view"><Transport /></RequirePermission>} />
              <Route path="transport/drivers/:id" element={<RequirePermission perm="transport.view"><DriverProfile /></RequirePermission>} />
              <Route path="hr" element={<RequirePermission perms={['hr.leave.view', 'hr.leave.request', 'hr.payroll.view']}><HR /></RequirePermission>} />
              <Route path="activity" element={<RequirePermission perm="audit.view"><ActivityLog /></RequirePermission>} />
              <Route path="settings" element={<RequirePermission perm="school.settings.manage"><Settings /></RequirePermission>} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
          </Suspense>
        </ChildProvider>
        </SchoolProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
