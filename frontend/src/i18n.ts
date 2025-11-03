import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

const resources = {
  en: {
    translation: {
      appName: 'Municipal Energy',
      login: 'Login',
      signup: 'Sign up',
      email: 'Email',
      password: 'Password',
      logout: 'Logout',
      citizenPortal: 'Citizen Portal',
      inspectorRoutes: "Inspector's Routes",
      managerDashboard: 'Manager Dashboard',
      map: 'Map',
      myComplaints: 'My Complaints',
      todayRoutes: "Today's Routes",
      cases: 'Cases',
      inspections: 'Inspections',
      reports: 'Reports',
      admin: 'Admin',
      language: 'العربية',
    }
  },
  ar: {
    translation: {
      appName: 'الطاقة البلدية',
      login: 'تسجيل الدخول',
      signup: 'إنشاء حساب',
      email: 'البريد الإلكتروني',
      password: 'كلمة المرور',
      logout: 'خروج',
      citizenPortal: 'بوابة المواطن',
      inspectorRoutes: 'مسارات المفتش',
      managerDashboard: 'لوحة المدير',
      map: 'الخريطة',
      myComplaints: 'شكاواي',
      todayRoutes: 'مسارات اليوم',
      cases: 'الحالات',
      inspections: 'التفتيشات',
      reports: 'التقارير',
      admin: 'الإدارة',
      language: 'English',
    }
  }
}

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: 'en',
    fallbackLng: 'en',
    interpolation: { escapeValue: false }
  })

export const toggleLang = () => {
  const next = i18n.language === 'en' ? 'ar' : 'en'
  i18n.changeLanguage(next)
  const root = document.documentElement
  if (next === 'ar') {
    root.classList.add('rtl')
  } else {
    root.classList.remove('rtl')
  }
}

export default i18n

